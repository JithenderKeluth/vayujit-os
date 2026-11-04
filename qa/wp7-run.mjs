// Reuse original assertions, real browsers and guarded fixture lifecycle unchanged.
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { browserDiagnostic } from './wp7a7-diagnostic.mjs';
const choices = {
  wp7a7: ['WP7A7', 'qa/wp7a4-browser.mjs'],
  wp7a6: ['WP7A6', 'qa/wp7a4-browser.mjs'],
  wp7a5: ['WP7A5', 'qa/wp7a4-browser.mjs'],
  wp7a4: ['WP7A4', 'qa/wp7a4-browser.mjs'],
  wp7a3: ['WP7A3', 'qa/wp7a3-browser.mjs'],
  wp7a2: ['WP7A2', 'qa/wp7a2-browser.mjs'],
  wp7a: ['WP7A', 'qa/wp7a-browser.mjs'],
  wp1: ['WP6B', 'qa/wp1-browser-retest.mjs'],
  wp2: ['WP6B', 'qa/wp2-browser-retest.mjs'],
  wp3: ['WP6B', 'qa/wp3-browser-retest.mjs'],
  wp4: ['WP6B', 'qa/wp4-browser-retest.mjs'],
  wp5: ['WP5', 'qa/wp5-browser-retest.mjs'],
  wp6: ['WP6', 'qa/wp6-browser-retest.mjs'],
  wp6a: ['WP6A', 'qa/wp6a-browser-retest.mjs'],
  wp6b: ['WP6B', 'qa/wp6b-browser-retest.mjs'],
  surface: ['WP6B', 'qa/wp7-browser.mjs'],
  layout: ['WP6B', 'qa/wp7-layout.mjs'],
};
const selected = process.argv.slice(2);
const packageName =
  selected.length === 1 && ['wp7a', 'wp7a2', 'wp7a3', 'wp7a4', 'wp7a5', 'wp7a6', 'wp7a7'].includes(selected[0])
    ? selected[0]
    : 'wp7';
const evidenceRoot = 'tmp/qa-' + packageName;
if (!selected.length || selected.some((k) => !choices[k])) throw Error('EXACT_WP7_SUITE_REQUIRED');
if (!process.env.QA_DATABASE_ADMIN_URL || !process.env.QA_POSTGRES_INSTANCE_MANIFEST)
  throw Error('APPROVED_QA_REQUIRED');
const delay = (ms) => new Promise((r) => setTimeout(r, ms));
await fs.mkdir(evidenceRoot, { recursive: true });
const records = [];
for (const key of selected) {
  const [phase, script] = choices[key];
  const runtime = spawn(process.execPath, ['qa/seller-browser-session.mjs'], {
    env: {
      ...process.env,
      QA_PHASE: '2',
      QA_MIGRATE: '1',
      QA_BROWSER_PHASE: phase,
      QA_DATABASE_DROP_TIMEOUT_MS: '90000',
    },
    windowsHide: true,
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  let session,
    buffer = '',
    bytes = 0,
    exited = false;
  runtime.stdout.on('data', (d) => {
    buffer += d;
    for (const line of buffer.split(/\r?\n/)) {
      try {
        const v = JSON.parse(line);
        if (v.status === 'READY' && v.synthetic) session = v;
      } catch {
        /* never persist raw output */
      }
    }
  });
  runtime.stderr.on('data', (d) => (bytes += d.length));
  const done = new Promise((r) =>
    runtime.on('exit', (code) => {
      exited = true;
      r(code);
    }),
  );
  const record = {
    suite: key,
    started_at: new Date().toISOString(),
    status: 'BLOCKED',
    raw_output_persisted: false,
  };
  try {
    for (let n = 0; n < 900 && !session && !exited; n++) await delay(400);
    if (!session) throw Error('OWNED_RUNTIME_NOT_READY');
    record.token = session.token;
    await fs.writeFile(
      path.join(session.folder, `${packageName}-run.json`),
      JSON.stringify({ suite: key, token: session.token, synthetic: true }),
    );
    console.log(JSON.stringify({ suite: key, token: session.token, status: 'RUNNING' }));
    const test = spawn(
      process.execPath,
      [
        script,
        path.join(session.folder, 'session.json'),
        ...(['wp7a', 'wp7a2', 'wp7a3', 'wp7a4', 'wp7a5', 'wp7a6', 'wp7a7'].includes(packageName) &&
        process.env.QA_WP7A_FOCUSED === '1'
          ? ['--focused']
          : []),
      ],
      {
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    );
    let testOutput = '';
    const capturedTestOutput = (d) => { bytes += d.length; if (testOutput.length < 64000) testOutput += d; };
    test.stdout.on('data', capturedTestOutput);
    test.stderr.on('data', capturedTestOutput);
    record.browser_exit = await new Promise((r) => test.on('exit', r));
    if(record.browser_exit !== 0) record.browser_diagnostic = browserDiagnostic(testOutput);
    record.status = record.browser_exit === 0 ? 'EXECUTED' : 'FAILED';
  } catch {
    record.status = 'BLOCKED';
  } finally {
    if (session)
      await fs.writeFile(path.join(session.folder, 'stop.request'), 'WP7 suite complete');
    else runtime.stdin.end();
    record.runtime_exit = await done;
    if (session) {
      record.cleanup = JSON.parse(
        await fs.readFile(path.join(session.folder, 'session-final.json'), 'utf8'),
      );
    }
    record.captured_output_bytes = bytes;
    record.completed_at = new Date().toISOString();
    records.push(record);
    await fs.writeFile(
      `${evidenceRoot}/execution-${['wp7a', 'wp7a2', 'wp7a3', 'wp7a4', 'wp7a5', 'wp7a6', 'wp7a7'].includes(packageName) ? record.token || 'startup-' + Date.now() : selected.join('-')}.json`,
      JSON.stringify(records, null, 2),
    );
    console.log(
      JSON.stringify({
        suite: key,
        token: record.token,
        status: record.status,
        browser_exit: record.browser_exit,
        runtime_exit: record.runtime_exit,
        cleanup: record.cleanup?.status,
      }),
    );
  }
  if (record.cleanup && record.cleanup.status !== 'CLEANED') break;
}
process.exitCode =
  records.length === selected.length &&
  records.every(
    (r) => r.status === 'EXECUTED' && r.runtime_exit === 0 && r.cleanup?.status === 'CLEANED',
  )
    ? 0
    : 1;
