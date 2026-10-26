import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import net from 'node:net';
import path from 'node:path';
import crypto from 'node:crypto';
import { audit } from './audit.mjs';
import { serve } from './server.mjs';
import { writeReport } from './report.mjs';
import { registeredOperations } from './runtime-inventory.mjs';
import { certificationStatus, phase2ApiComplete, phase3ApiComplete } from './safety.mjs';
import { archiveQaReports } from './archive-reports.mjs';

const output = path.resolve('tmp/qa-agent');
const phase2 = process.argv.includes('--phase2');
const phase3 = process.argv.includes('--phase3');
const phase4a = process.argv.includes('--phase4a');
const phase4b = process.argv.includes('--phase4b');
const phase4c = process.argv.includes('--phase4c');
const phase4 = process.argv.includes('--phase4') || phase4a || phase4c;
const focusIndex = process.argv.indexOf('--focus');
const phase4Focus = focusIndex >= 0 ? process.argv[focusIndex + 1] : null;
if (focusIndex >= 0 && (!phase4 || !phase4Focus || phase4Focus.length > 200))
  throw new Error('QA_FOCUS_ARGUMENT_DENIED');
if (phase4Focus) new RegExp(phase4Focus);
if ([phase2, phase3, phase4, phase4b].filter(Boolean).length > 1)
  throw new Error('QA_PHASE_CONFLICT');
await fs.mkdir(output, { recursive: true });
await archiveQaReports();
const inventory = await audit({
  write: !phase4 && !phase4b && !process.argv.includes('--preserve-inventory'),
});
if (phase4)
  await fs.writeFile(
    `docs/qa/${phase4c ? 'phase-4c' : 'phase-4'}-source-inventory.json`,
    JSON.stringify(inventory, null, 2),
  );
if (!process.env.QA_DATABASE_ADMIN_URL)
  throw new Error(
    'Set QA_DATABASE_ADMIN_URL to the disposable PostgreSQL admin connection on 127.0.0.1, database postgres. No .env is read by this runner.',
  );
const python = process.env.QA_PYTHON || path.resolve('apps/api/.venv/Scripts/python.exe');
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function freePort() {
  const server = net.createServer();
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  return port;
}
async function command(exe, args, env = process.env) {
  const child = spawn(exe, args, {
    env,
    stdio: ['ignore', 'inherit', 'inherit'],
    windowsHide: true,
  });
  return new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('exit', (code) => resolve(code ?? 1));
  });
}
const remediationBaseline =
  phase4 || phase4b
    ? await fs
        .readFile(
          phase4b ? 'docs/qa/phase-4b-baseline.json' : 'docs/qa/phase-4a-baseline.json',
          'utf8',
        )
        .then(JSON.parse)
        .catch(() => null)
    : null;
const testedSourcePaths = remediationBaseline
  ? [
      ...new Set([
        ...Object.keys(remediationBaseline.source_sha256),
        'apps/web/src/app/ai/ai.css',
        ...(phase4a ? ['qa/tests/phase4a.spec.mjs'] : []),
        ...(phase4b
          ? [
              'qa/tests/phase4b.spec.mjs',
              'apps/web/src/app/marketplaces/opening-stock.component.ts',
              'apps/web/src/app/marketplaces/opening-stock.css',
            ]
          : []),
        'qa/safety.mjs',
        'qa/server.mjs',
      ]),
    ]
  : [];
const testedSourceHashes = Object.fromEntries(
  await Promise.all(
    testedSourcePaths.map(async (file) => [
      file,
      crypto
        .createHash('sha256')
        .update(await fs.readFile(file))
        .digest('hex'),
    ]),
  ),
);
// Always build current source: never accidentally certify stale dist files.
const buildChild = spawn(
  process.execPath,
  [path.resolve('node_modules/@angular/cli/bin/ng.js'), 'build'],
  {
    cwd: path.resolve('apps/web'),
    stdio: 'inherit',
    windowsHide: true,
    env: { ...process.env, NG_CLI_ANALYTICS: 'false' },
  },
);
const buildCode = await new Promise((resolve) => {
  buildChild.once('error', () => resolve(1));
  buildChild.once('exit', resolve);
});
if (buildCode !== 0) throw new Error('QA_PRODUCTION_BUILD_FAILED');
const reports = [];
const cleanup = [];
for (const project of ['desktop', 'mobile']) {
  const token = crypto.randomBytes(8).toString('hex');
  const apiPort = await freePort();
  const webPort = await freePort();
  const origin = `http://127.0.0.1:${webPort}`;
  const runDir = path.join(output, token);
  await fs.mkdir(runDir, { recursive: true });
  const reportPath = path.join(runDir, 'report.json');
  const env = {
    ...process.env,
    QA_ORIGIN: origin,
    QA_PHASE: phase4c
      ? '4C'
      : phase4b
        ? '4B'
        : phase4a
          ? '4A'
          : phase4
            ? '4'
            : phase3
              ? '3'
              : phase2
                ? '2'
                : '1',
    QA_RUN_DIR: runDir,
    QA_TOKEN: token,
    QA_REPORT_PATH: reportPath,
    QA_ARTIFACT_DIR: path.join(runDir, 'browser-artifacts'),
    PYTHONPATH: [process.cwd(), path.resolve('apps/api')].join(path.delimiter),
  };
  let web;
  let exited = false;
  const child = spawn(
    python,
    ['qa/fixture_server.py', '--port', String(apiPort), '--output', runDir, '--token', token],
    {
      env: phase4 ? { ...env, QA_PHASE: '3' } : env,
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    },
  );
  // Child diagnostics are kept private; report only fixed safe codes on launch failure.
  let bytes = 0;
  child.stdout.on('data', (data) => {
    bytes += data.length;
  });
  child.stderr.on('data', (data) => {
    bytes += data.length;
  });
  child.once('error', () => {
    exited = true;
  });
  const ended = new Promise((resolve) =>
    child.once('exit', (code) => {
      exited = true;
      resolve(code);
    }),
  );
  try {
    let ready = false;
    const startupBegan = Date.now();
    // Windows disposable schema + supervisor + cold API startup was measured at
    // 63.6s, beyond the old 150*400ms polling budget. This is not an application
    // request SLA: token/marker/auth/business assertions are unchanged.
    while (Date.now() - startupBegan < 120000 && !exited) {
      try {
        const response = await fetch(`http://127.0.0.1:${apiPort}/__qa/witness`, {
          signal: AbortSignal.timeout(2000),
        });
        const witness = await response.json();
        if (response.ok && witness.token === token && witness.disposable) {
          ready = true;
          break;
        }
      } catch {
        /* Wait for this newly spawned installation only. */
      }
      await delay(400);
    }
    await fs.writeFile(
      path.join(runDir, 'startup-diagnostic.json'),
      JSON.stringify(
        { ready, elapsed_ms: Date.now() - startupBegan, diagnostic_bytes: bytes },
        null,
        2,
      ),
    );
    if (!ready) throw new Error(`QA_FIXTURE_START_FAILED_DIAGNOSTIC_BYTES_${bytes}`);
    web = await serve(
      webPort,
      apiPort,
      phase4b ? '4B' : phase4 ? '4' : phase3 ? '3' : phase2 ? '2' : '1',
      phase3
        ? {
            token,
            async restart() {
              const began = Date.now();
              const journal = { status: 'STARTED', elapsed_ms: 0 };
              const save = async () =>
                fs.writeFile(
                  path.join(runDir, 'owned-restart-diagnostic.json'),
                  JSON.stringify({ ...journal, elapsed_ms: Date.now() - began }, null, 2),
                );
              await save();
              const before = await (await fetch(`http://127.0.0.1:${apiPort}/__qa/witness`)).json();
              journal.before_process = before.process_id;
              journal.status = 'RESTART_REQUESTED';
              await save();
              child.stdin.write(`restart:${token}\n`);
              for (let attempt = 0; attempt < 100 && !exited; attempt++) {
                await delay(300);
                try {
                  const after = await (
                    await fetch(`http://127.0.0.1:${apiPort}/__qa/witness`)
                  ).json();
                  if (after.token === token && after.process_id !== before.process_id) {
                    journal.status = 'READY';
                    journal.after_process = after.process_id;
                    await save();
                    return {
                      before_process: before.process_id,
                      after_process: after.process_id,
                      token,
                      disposable: true,
                    };
                  }
                } catch {
                  /* Owned child is restarting; never access another runtime. */
                }
              }
              journal.status = 'NOT_READY';
              await save();
              throw new Error('QA_OWNED_RESTART_FAILED');
            },
          }
        : null,
    );
    let apiResult;
    if (phase2 || phase3 || phase4) {
      const apiExit = await command(
        python,
        [phase3 || phase4 ? 'qa/phase3_api.py' : 'qa/phase2_api.py'],
        phase4 ? { ...env, QA_PHASE: '3' } : env,
      );
      apiResult = JSON.parse(await fs.readFile(path.join(runDir, 'api-results.json'), 'utf8'));
      apiResult.process_exit_code = apiExit;
    }
    if (phase4c) {
      const { prepareAuditArtifacts } = await import('./phase4c-fixtures.mjs');
      await prepareAuditArtifacts({ apiPort, origin, token, runDir });
    }
    const code = await command(
      process.execPath,
      [
        'node_modules/@playwright/test/cli.js',
        'test',
        '--config',
        'qa/playwright.config.mjs',
        '--project',
        project,
        ...(phase4Focus ? ['--grep', phase4Focus] : []),
      ],
      env,
    );
    const report = JSON.parse(await fs.readFile(reportPath, 'utf8'));
    if (apiResult) report.api_results = apiResult;
    report.process_exit_code = code;
    const openapi = JSON.parse(await fs.readFile(path.join(runDir, 'openapi.json'), 'utf8'));
    const runtimeInventory = registeredOperations(openapi, inventory.api_declarations);
    await fs.writeFile(
      phase4c
        ? `docs/qa/phase-4c-runtime-api-inventory-${project}.json`
        : phase4 || phase4b
          ? `docs/qa/phase-4-runtime-api-inventory-${project}.json`
          : 'docs/qa/runtime-api-inventory.json',
      JSON.stringify(runtimeInventory, null, 2),
    );
    report.runtime_api_operations = Object.values(openapi.paths).reduce(
      (count, item) =>
        count +
        Object.keys(item).filter((key) =>
          ['get', 'post', 'put', 'patch', 'delete', 'head', 'options'].includes(key),
        ).length,
      0,
    );
    reports.push(report);
  } catch (error) {
    const diagnostic = await fs
      .readFile(path.join(runDir, 'fixture-failure.json'), 'utf8')
      .then(JSON.parse)
      .catch(() => null);
    reports.push({
      status: 'BLOCKED',
      tests: [],
      findings: [],
      fixture_diagnostic: diagnostic,
      blocker: error.message.startsWith('QA_') ? error.message : 'QA_RUNNER_OPERATION_FAILED',
    });
  } finally {
    if (web) await new Promise((resolve) => web.close(resolve));
    child.stdin.end();
    const exit = await Promise.race([ended, delay(45000).then(() => 'TIMEOUT')]);
    const proof = await fs
      .readFile(path.join(runDir, 'cleanup.json'), 'utf8')
      .then(JSON.parse)
      .catch(() => null);
    cleanup.push({
      project,
      database: `vayujit_qa${token}_test`,
      status: proof?.status === 'PASS' && proof.database_absent ? 'PASS' : 'BLOCKED',
      child_exit: exit,
      proof,
    });
    if (exit === 'TIMEOUT') child.kill(); // Only this child; preserve database for guarded HUMAN cleanup.
  }
}
const tests = reports.flatMap((r) => r.tests);
const result = {
  generated_at: new Date().toISOString(),
  tested_source_sha256: testedSourceHashes,
  phase: phase4b
    ? 'QA_AGENT_PHASE_4B'
    : phase4a
      ? 'QA_AGENT_PHASE_4A'
      : phase4
        ? 'QA_AGENT_PHASE_4'
        : phase3
          ? 'QA_AGENT_PHASE_3'
          : phase2
            ? 'QA_AGENT_PHASE_2'
            : 'QA_AGENT_PHASE_1',
  status:
    certificationStatus(reports, cleanup, phase3 ? 9 : 4) === 'PASS_BOUNDED_SMOKE' &&
    (!phase2 || reports.every((r) => phase2ApiComplete(r.api_results))) &&
    (!phase3 || reports.every((r) => phase3ApiComplete(r.api_results)))
      ? 'PASS_BOUNDED_SMOKE'
      : 'INCOMPLETE',
  executive_summary: {
    passed: tests.filter((r) => r.status === 'passed').length,
    failed: tests.filter((r) => !['passed', 'skipped'].includes(r.status)).length,
    total: tests.length,
    full_application_coverage: false,
  },
  coverage: {
    inventoried_routes: inventory.routes.length,
    api_declarations: inventory.api_declarations.length,
    runtime_api_operations: reports.map((r) => r.runtime_api_operations),
    models: inventory.models.length,
    existing_backend_test_files: inventory.backend_tests.length,
    existing_angular_spec_files: inventory.frontend_specs.length,
    historical_tests_rerun: false,
  },
  reports,
  cleanup,
  findings: reports.flatMap((r) => r.findings),
  confirmed_bugs: reports.flatMap((r) => r.confirmed_bugs || []),
  usability_findings: reports.flatMap((r) => r.usability_findings || []),
  next_phase:
    'Risk-first persisted seller journey, financial oracle and foreign-ID matrices; no autonomous production fixes.',
};
if (phase4c) {
  result.phase = 'QA_AGENT_PHASE_4C';
  result.full_application_certification = 'INCOMPLETE';
  result.status =
    certificationStatus(reports, cleanup, 4) === 'PASS_BOUNDED_SMOKE' &&
    reports.every((r) => phase3ApiComplete(r.api_results))
      ? 'PASS_BOUNDED_AUDIT_CHECKS'
      : 'INCOMPLETE';
  await fs.writeFile('docs/qa/phase-4c-execution.json', JSON.stringify(result, null, 2));
  console.log(
    JSON.stringify({ phase: '4C', status: result.status, ...result.executive_summary, cleanup }),
  );
  if (result.status !== 'PASS_BOUNDED_AUDIT_CHECKS') process.exitCode = 1;
} else if (phase4b) {
  const { openingStockComplete } = await import('./phase4b-status.mjs');
  result.full_application_certification = 'INCOMPLETE';
  result.status = openingStockComplete(result) ? 'PASS_BOUNDED_OPENING_STOCK' : 'INCOMPLETE';
  await fs.writeFile('docs/qa/phase-4b-report.json', JSON.stringify(result, null, 2));
  console.log(
    JSON.stringify({ phase: '4B', status: result.status, ...result.executive_summary, cleanup }),
  );
  if (result.status !== 'PASS_BOUNDED_OPENING_STOCK') process.exitCode = 1;
} else if (phase4) {
  const { writePhase4Report, expectedPhase4Ids, phase4CleanupComplete } = await import(
    './phase4-report.mjs'
  );
  if (phase4a) {
    result.full_application_certification = 'INCOMPLETE';
    result.status =
      phase4CleanupComplete(cleanup) &&
      certificationStatus(reports, cleanup, 3) === 'PASS_BOUNDED_SMOKE' &&
      reports.every((r) =>
        ['QA-P4A-01', 'QA-P4A-02', 'QA-P4A-03'].every(
          (id) => r.tests.filter((t) => t.id === id && t.status === 'passed').length === 1,
        ),
      ) &&
      reports.every((r) => phase3ApiComplete(r.api_results))
        ? 'PASS_FOCUSED_ACCESSIBILITY_RETEST'
        : 'INCOMPLETE';
    await fs.writeFile('docs/qa/phase-4a-retest-report.json', JSON.stringify(result, null, 2));
  } else if (phase4Focus) {
    const selected = expectedPhase4Ids(inventory.routes).filter((id) =>
      new RegExp(phase4Focus).test(id),
    );
    result.focus = phase4Focus;
    result.full_application_certification = 'INCOMPLETE';
    result.status =
      selected.length &&
      phase4CleanupComplete(cleanup) &&
      certificationStatus(reports, cleanup, selected.length) === 'PASS_BOUNDED_SMOKE' &&
      reports.every((r) => phase3ApiComplete(r.api_results))
        ? 'PASS_FOCUSED_EXPLORATION'
        : 'INCOMPLETE';
    await fs.writeFile('docs/qa/phase-4-focused-report.json', JSON.stringify(result, null, 2));
  } else await writePhase4Report(result, inventory);
  console.log(
    JSON.stringify({ phase: 4, ...result.executive_summary, status: result.status, cleanup }),
  );
  if (!['PASS_BOUNDED_EXPLORATION', 'PASS_FOCUSED_ACCESSIBILITY_RETEST'].includes(result.status))
    process.exitCode = 1;
} else if (phase3) {
  const { writePhase3Report } = await import('./phase3-report.mjs');
  await writePhase3Report(result);
  console.log(
    JSON.stringify({ phase: 3, status: result.status, ...result.executive_summary, cleanup }),
  );
  if (result.status !== 'PASS_BOUNDED_SMOKE') process.exitCode = 1;
} else if (phase2) {
  const { writePhase2Report } = await import('./phase2-report.mjs');
  await writePhase2Report(result);
  console.log(
    JSON.stringify({ phase: 2, status: result.status, ...result.executive_summary, cleanup }),
  );
  if (result.status !== 'PASS_BOUNDED_SMOKE') process.exitCode = 1;
} else {
  const executedCoverage = inventory.routes.map((route) => {
    const pattern = new RegExp(
      `^${route.route
        .split('/')
        .map((part) =>
          part.startsWith(':') ? '[^/]+' : part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'),
        )
        .join('/')}$`,
    );
    const matches = tests.filter((test) =>
      test.signals?.visited_routes.some((visited) => pattern.test(visited)),
    );
    return {
      route: route.route,
      kind: route.kind,
      status: matches.length ? 'VISITED_NOT_COMPLETE_FEATURE_COVERAGE' : 'NOT_EXECUTED',
      tests: matches.map((test) => ({ id: test.id, project: test.project, status: test.status })),
    };
  });
  const retest = process.argv.includes('--retest');
  await fs.writeFile(
    `docs/qa/${retest ? 'phase-1-retest-coverage' : 'executed-coverage'}.json`,
    JSON.stringify(executedCoverage, null, 2),
  );
  await writeReport(result, retest ? 'phase-1-retest-report' : 'initial-report');
  console.log(JSON.stringify({ status: result.status, ...result.executive_summary, cleanup }));
  if (result.status !== 'PASS_BOUNDED_SMOKE') process.exitCode = 1;
}
