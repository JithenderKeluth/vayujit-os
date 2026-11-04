import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import Ajv2020 from 'ajv/dist/2020.js';
import { openingStockComplete } from './phase4b-status.mjs';
import { phase4Status, phase4CleanupComplete } from './phase4-report.mjs';
import { certificationStatus, phase2ApiComplete, phase3ApiComplete } from './safety.mjs';

const read = async (p) => JSON.parse(await fs.readFile(p, 'utf8'));
const hash = (data) => crypto.createHash('sha256').update(data).digest('hex');
const baseline = await read('docs/qa/phase-4b-baseline.json');
const stock = await read('docs/qa/phase-4b-report.json');
const full = await read('docs/qa/phase-4-report.json');
const p3 = await read('docs/qa/phase-3-report.json');
const p2 = await read('docs/qa/phase-2-report.json');
const p1 = await read('docs/qa/phase-1-retest-report.json');
const quality = await read('docs/qa/phase-4b-quality.json');
const inventory = await read('docs/qa/phase-4-source-inventory.json');
const backendDir = process.argv[2];
if (!/^tmp\/qa-agent\/[a-f0-9]{16}$/.test(backendDir || ''))
  throw new Error('QA_BACKEND_EVIDENCE_PATH_DENIED');
const xml = await fs.readFile(`${backendDir}/backend-results.xml`, 'utf8');
const cases = [...xml.matchAll(/<testcase\b[^>]*>/g)].map((m) => m[0]);
const counts = Object.fromEntries(
  [
    'test_qa_phase4b_opening_stock',
    'test_qa_phase3a_remediation',
    'test_qa_phase3b_remediation',
    'test_pr_sos_06_action_center',
    'test_pr_sos_04_inventory_orders',
  ].map((name) => [
    name,
    cases.filter((c) => c.includes(`classname="${name}"`) || c.includes(`.${name}"`)).length,
  ]),
);
const backendCleanup = await read(`${backendDir}/cleanup.json`);
const backendPassed =
  cases.length === 81 &&
  Object.values(counts).join(',') === '36,17,16,4,8' &&
  !/<(?:failure|error|skipped)\b/.test(xml) &&
  backendCleanup.status === 'PASS' &&
  backendCleanup.marker_verified === true &&
  backendCleanup.database_absent === true;
const checkedHashes = { ...stock.tested_source_sha256, ...quality.tested_source_sha256 };
// Both independent execution witnesses must match, not just the last map entry.
const hashesCurrent = (
  await Promise.all(
    [stock, quality].flatMap((r) =>
      Object.entries(r.tested_source_sha256 || {}).map(
        async ([file, expected]) => hash(await fs.readFile(file)) === expected,
      ),
    ),
  )
).every(Boolean);
const original = await fs.readFile('qa/tests/phase4.spec.mjs', 'utf8');
const targeted = [];
for (const project of stock.reports)
  for (const test of project.tests)
    for (const e of test.evidence.filter((e) => e.name.startsWith('node-review-stock-')))
      targeted.push({
        ...(await read(e.path)),
        name: e.name,
        project: test.project,
        evidence: e.path,
      });
const targetNames = ['stock-ledger-caption', 'stock-damaged-header', 'stock-quantity-help'];
const targetsPassed =
  targeted.length === 6 &&
  ['desktop', 'mobile'].every((project) =>
    targetNames.every(
      (name) =>
        targeted.filter(
          (r) =>
            r.project === project &&
            r.name === 'node-review-' + name &&
            r.text_horizontally_in_view &&
            !r.violations.length &&
            !r.incomplete.length &&
            r.passes.includes('color-contrast'),
        ).length === 1,
    ),
  );
const originalChangeBounded =
  hash(original.replace('No matching inventory', 'No canonical inventory yet')) ===
  baseline.source_sha256['qa/tests/phase4.spec.mjs'];
const unchangedModels = (
  await Promise.all(
    [
      'apps/api/vayujit_api/commerce/models.py',
      'apps/api/vayujit_api/products/models.py',
      'apps/api/vayujit_api/catalog/models.py',
    ].map(async (p) => hash(await fs.readFile(p)) === baseline.source_sha256[p]),
  )
).every(Boolean);
const adjacent = [
  [p3, 9, phase3ApiComplete],
  [p2, 4, phase2ApiComplete],
  [p1, 4, null],
].every(
  ([r, n, api]) =>
    phase4CleanupComplete(r.cleanup) &&
    certificationStatus(r.reports, r.cleanup, n) === 'PASS_BOUNDED_SMOKE' &&
    (!api || r.reports.every((project) => api(project.api_results))),
);
const qualityPassed =
  quality.status === 'PASS_WITH_KNOWN_WARNING' &&
  quality.unchanged_during_checks &&
  quality.checks.every(
    (c) =>
      c.status === 'PASS' ||
      (c.name === 'schema-mypy-historical' && c.status === 'HISTORICAL_WARNING'),
  );
// Independent read-only catalog query, including failed intermediate targets.
// It cannot create, update, drop or terminate anything.
const disposableTargets = [];
for (const dir of await fs.readdir('tmp/qa-agent', { withFileTypes: true })) {
  if (!dir.isDirectory() || !/^[a-f0-9]{16}$/.test(dir.name)) continue;
  const folder = `tmp/qa-agent/${dir.name}`;
  if ((await fs.stat(folder)).birthtimeMs < Date.parse(baseline.generated_at)) continue;
  const normal = await read(`${folder}/cleanup.json`).catch(() => null);
  const recovered = await read(`${folder}/recovery-cleanup.json`).catch(() => null);
  disposableTargets.push({
    token: dir.name,
    database: `vayujit_qa${dir.name}_test`,
    normal,
    recovered,
  });
}
const names = disposableTargets.map((t) => t.database);
const query = String.raw`
import json, os, sys, re
from sqlalchemy import create_engine, text, bindparam
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
url = make_url(os.environ['QA_DATABASE_ADMIN_URL'])
assert url.host == '127.0.0.1' and url.database == 'postgres'
names = json.loads(sys.argv[1])
assert names and all(re.fullmatch(r'vayujit_qa[a-f0-9]{16}_test', n) for n in names)
engine = create_engine(url, poolclass=NullPool)
with engine.connect() as db:
    remaining = list(db.scalars(text('select datname from pg_database where datname in :names').bindparams(bindparam('names', expanding=True)), {'names': names}))
engine.dispose()
print(json.dumps({'checked': len(names), 'remaining': remaining}))
`;
const databaseProof = JSON.parse(
  execFileSync(
    path.resolve('apps/api/.venv/Scripts/python.exe'),
    ['-c', query, JSON.stringify(names)],
    { encoding: 'utf8', windowsHide: true },
  ),
);
const processes = JSON.parse(
  execFileSync(
    'powershell.exe',
    [
      '-NoProfile',
      '-Command',
      "@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|node' -and $_.CommandLine -match 'qa/run.mjs|qa[\\\\/]fixture_server.py|qa.phase3_runtime' } | Select-Object ProcessId,Name) | ConvertTo-Json -Compress",
    ],
    { encoding: 'utf8', windowsHide: true },
  ) || '[]',
);
const cleanupProof = {
  generated_at: new Date().toISOString(),
  read_only_verification: true,
  ...databaseProof,
  matching_qa_processes: Array.isArray(processes) ? processes : processes ? [processes] : [],
  targets: disposableTargets,
};
await fs.writeFile(
  'docs/qa/phase-4b-cleanup-verification.json',
  JSON.stringify(cleanupProof, null, 2),
);
const cleanupPassed =
  databaseProof.checked === names.length &&
  !databaseProof.remaining.length &&
  !cleanupProof.matching_qa_processes.length &&
  disposableTargets.every(
    (t) =>
      (t.normal?.status === 'PASS' &&
        t.normal.database === t.database &&
        t.normal.marker_verified &&
        t.normal.database_absent) ||
      (t.recovered?.status === 'PASS' &&
        t.recovered.database === t.database &&
        t.recovered.database_absent),
  );
const gates = {
  seller_ui_and_persistence: openingStockComplete(stock),
  audited_movement_replay_concurrency_and_security: backendPassed,
  desktop_mobile_accessibility: openingStockComplete(stock),
  exposed_stock_help_and_header_contrast: targetsPassed,
  original_phase4_regression: phase4Status(full, inventory.routes) === 'PASS_BOUNDED_EXPLORATION',
  phase3_phase2_phase1_regressions: adjacent,
  quality_checks_no_new_failures: qualityPassed,
  current_execution_hashes: hashesCurrent,
  original_assertion_change_only_expected_empty_message: originalChangeBounded,
  canonical_models_unchanged_no_migration: unchangedModels,
  independent_all_target_cleanup: cleanupPassed,
};
const passed = Object.values(gates).every(Boolean);
const allTests = stock.reports.flatMap((r) => r.tests);
const scans = allTests.flatMap((t) =>
  t.axe.map((s) => ({ ...s, project: t.project, test_id: t.id, evidence: t.evidence })),
);
const surfaces = [];
for (const t of allTests)
  for (const e of t.evidence.filter((e) => e.name.startsWith('stock-surface-')))
    surfaces.push({ ...(await read(e.path)), project: t.project, test_id: t.id, evidence: e.path });
await fs.writeFile(
  'docs/qa/phase-4b-route-control-coverage.json',
  JSON.stringify(
    {
      generated_at: new Date().toISOString(),
      surfaces,
      status: passed ? 'PASS_BOUNDED_STOCK_WORKFLOW' : 'INCOMPLETE',
      note: 'Only explicit Phase 4B assertions are functional coverage; DOM control presence is not a PASS.',
    },
    null,
    2,
  ),
);
await fs.writeFile(
  'docs/qa/phase-4b-accessibility.json',
  JSON.stringify({ scans, targeted, full_wcag_conformance: false }, null, 2),
);
const closeIds = new Set(['QA-P3-GAP-003', 'QA-P4-UX-STOCK-EMPTY']);
const current = await read('docs/qa/defect-backlog.json');
const legacyDecisions = new Map();
for (const file of ['docs/qa/remediation-retest.json', 'docs/qa/phase-3b-resolution.json']) {
  for (const decision of (await read(file)).resolutions)
    legacyDecisions.set(decision.id, { file, decision });
}
// Older report writers reintroduce their historical findings. Preserve them in
// full, but do not mistake a previously resolved record for a new observation.
const historical = current.filter(
  (f) =>
    !baseline.findings.some((b) => b.id === f.id) &&
    legacyDecisions.get(f.id)?.decision.status === 'RESOLVED' &&
    adjacent &&
    phase4Status(full, inventory.routes) === 'PASS_BOUNDED_EXPLORATION' &&
    !stock.findings.some((r) => r.id === f.id),
);
const archived = await read('docs/qa/phase-4b-historical-records.json').catch(() => ({
  records: [],
}));
const historicalRecords = [
  ...new Map(
    [
      ...archived.records,
      ...historical.map((finding) => ({
        finding,
        prior_resolution: legacyDecisions.get(finding.id),
        disposition:
          'Historical record regenerated by older report writers; already resolved before Phase 4B, current adjacent/full regressions pass. Not a new finding or a new Phase 4B closure.',
      })),
    ].map((r) => [r.finding.id, r]),
  ).values(),
];
await fs.writeFile(
  'docs/qa/phase-4b-historical-records.json',
  JSON.stringify({ generated_at: new Date().toISOString(), records: historicalRecords }, null, 2),
);
const retainedCurrent = current.filter((f) => !historical.some((h) => h.id === f.id));
const ledger = [
  ...new Map([...retainedCurrent, ...baseline.findings].map((f) => [f.id, f])).values(),
].map((f) =>
  passed && closeIds.has(f.id)
    ? {
        ...f,
        retest_status: 'PASS',
        evidence: [
          ...f.evidence,
          {
            name: 'Independent Phase 4B stock resolution',
            path: 'docs/qa/phase-4b-resolution.json',
          },
          { name: 'Phase 4B browser execution', path: 'docs/qa/phase-4b-report.json' },
          {
            name: 'Persisted canonical stock regressions',
            path: `${backendDir}/backend-results.xml`,
          },
        ],
      }
    : f,
);
const validateFinding = new Ajv2020({ allErrors: true }).compile(
  await read('qa/finding.schema.json'),
);
if (passed && scans.some((s) => s.incomplete.length)) {
  const manual = ledger.find((f) => f.id === 'QA-P4A-A11Y-MANUAL-001');
  if (manual && !manual.evidence.some((e) => e.path === 'docs/qa/phase-4b-accessibility.json'))
    manual.evidence.push({
      name: 'Additional stock workflow incomplete results retained for manual review',
      path: 'docs/qa/phase-4b-accessibility.json',
    });
}
if (!ledger.every((f) => validateFinding(f)))
  throw new Error('QA_RESOLUTION_FINDING_SCHEMA_INVALID');
if (passed) await fs.writeFile('docs/qa/defect-backlog.json', JSON.stringify(ledger, null, 2));
const resolution = {
  generated_at: new Date().toISOString(),
  status: passed
    ? 'INITIAL_STOCK_ENTRY_VALIDATED_BOUNDED_LOCAL_SCOPE'
    : 'IMPLEMENTED_CERTIFICATION_PENDING',
  application_certification: 'INCOMPLETE',
  gates,
  backend: {
    counts,
    passed: cases.length,
    evidence: `${backendDir}/backend-results.xml`,
    cleanup: backendCleanup,
  },
  source_hashes: checkedHashes,
  baseline_findings: baseline.findings.length,
  previously_resolved_historical_records_preserved_separately: historicalRecords.length,
  finding_decisions: baseline.findings.map((f) => ({
    id: f.id,
    original_status: f.retest_status,
    status: passed && closeIds.has(f.id) ? 'PASS' : f.retest_status,
    changed: passed && closeIds.has(f.id),
  })),
  resolved: ledger.filter((f) => f.retest_status === 'PASS').length,
  open: ledger
    .filter((f) => f.retest_status !== 'PASS')
    .map((f) => ({ id: f.id, priority: f.priority, type: f.type, status: f.retest_status })),
  scans: scans.length,
  violations: scans.flatMap((s) => s.violations).length,
  incomplete_rule_state_occurrences: scans.flatMap((s) => s.incomplete).length,
  independent_cleanup: [
    ...stock.cleanup,
    ...full.cleanup,
    ...p3.cleanup,
    ...p2.cleanup,
    ...p1.cleanup,
  ],
};
await fs.writeFile('docs/qa/phase-4b-resolution.json', JSON.stringify(resolution, null, 2));
await fs.writeFile(
  'docs/qa/phase-4b-resolution.md',
  `# Phase 4B finding resolution ledger\n\n${resolution.status}. Application certification **INCOMPLETE**.\n\n| Finding | Previous | Current | Changed |\n| --- | --- | --- | --- |\n${resolution.finding_decisions.map((f) => `| ${f.id} | ${f.original_status} | ${f.status} | ${f.changed} |`).join('\n')}\n\n${resolution.resolved} resolved records; ${resolution.open.length} open. Original evidence retained. Only the two named stock findings can close from this work.\n`,
);
await fs.writeFile(
  'docs/qa/phase-4b-report.md',
  `# Phase 4B executed stock-entry browser report\n\n${stock.status}; final combined decision: **${resolution.status}**. Application certification **INCOMPLETE**.\n\n| Scenario | Context | Result | Duration ms |\n| --- | --- | --- | --- |\n${allTests.map((t) => `| ${t.id}: ${t.title.slice(t.id.length + 1)} | ${t.project} | ${t.status} | ${t.duration_ms} |`).join('\n')}\n\n${scans.length} axe scans, ${resolution.violations} violations, ${resolution.incomplete_rule_state_occurrences} incomplete rule/state occurrences (not PASS). See [exact scans](phase-4b-accessibility.json), [JSON network/screenshot references](phase-4b-report.json), [control captures](phase-4b-route-control-coverage.json), and [validation](phase-4b-validation.md).\n`,
);
const marker = '\n<!-- PHASE4B -->';
const coverage = await fs.readFile('docs/qa/coverage-matrix.md', 'utf8');
await fs.writeFile(
  'docs/qa/coverage-matrix.md',
  coverage.split(marker)[0] +
    marker +
    `\n## Phase 4B initial stock entry\n\n${resolution.status}. Opening stock browser: ${stock.executive_summary.passed}/16 pass; API: ${counts.test_qa_phase4b_opening_stock}/36 pass, adjacent API: ${cases.length - counts.test_qa_phase4b_opening_stock}/45 pass. See [stock validation](phase-4b-validation.md), [route/control evidence](phase-4b-route-control-coverage.json), [finding ledger](phase-4b-resolution.md). ${resolution.resolved} resolved, ${resolution.open.length} open; whole application INCOMPLETE. Prior sections remain historical evidence.\n`,
);
const routeCoverage = await fs.readFile('docs/qa/phase-4-coverage.md', 'utf8');
const stockAssessment = passed
  ? 'SUPPORTED BOUNDED LOCAL WORKFLOW: explicit review/confirm, persisted stock/ledger/audit, replay/concurrency and desktop/mobile evidence in Phase 4B'
  : 'IMPLEMENTED / CERTIFICATION PENDING: opening-stock handoff exists; do not infer functional success from route visits';
const journeys = await read('docs/qa/phase-4-journeys.json');
for (const j of journeys)
  if (j.journey === 'Initial inventory entry') {
    j.assessment = stockAssessment;
    j.functional_evidence = 'docs/qa/phase-4b-report.json';
  }
await fs.writeFile('docs/qa/phase-4-journeys.json', JSON.stringify(journeys, null, 2));
await fs.writeFile(
  'docs/qa/phase-4-coverage.md',
  routeCoverage
    .split(marker)[0]
    .replace(/- Initial inventory entry: [^\n]*/, '- Initial inventory entry: ' + stockAssessment) +
    marker +
    `\n## Functional stock-entry overlay\n\nThe new /marketplaces/inventory/opening route and Inventory handoff have explicit desktop/mobile functional evidence, beyond the read-only route visits above. Review/confirm, validation, saved ledger, replay, competing stock, archived products, error recovery, owner/auth denial, filters/history and reload are asserted. [Exact states and controls](phase-4b-route-control-coverage.json). No other route gains functional coverage from this overlay. Application INCOMPLETE.\n`,
);
console.log(
  JSON.stringify({
    status: resolution.status,
    gates,
    backend: counts,
    resolved: resolution.resolved,
    open: resolution.open.length,
    axe_scans: scans.length,
  }),
);
if (!passed) process.exitCode = 1;
