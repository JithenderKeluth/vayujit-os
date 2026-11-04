// Evidence census only. Does not run application actions, repair databases or infer live certification.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { junitCases } from './wp7-quality.mjs';
import { gate, contexts } from './wp7a5-gate.mjs';
import { rollup } from './wp7a4-rollup.mjs';
const root = 'docs/qa/seller-experience/';
const read = async (p) => JSON.parse(await fs.readFile(p, 'utf8'));
const exists = async (p) => {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
};
const ledger = await read(root + 'wp7a5-coverage-ledger.json');
const audit = await read('tmp/qa-wp7a5-final-audit.json');
const quality = await read('tmp/qa-wp7a5/quality.json');
const baseline = await read('tmp/qa-wp7a5/baseline.json');
if (
  !(
    await Promise.all(
      baseline.files.map(
        async (r) =>
          crypto
            .createHash('sha256')
            .update(await fs.readFile(r.file))
            .digest('hex') === r.sha256,
      ),
    )
  ).every(Boolean)
)
  throw Error('HISTORICAL_BASELINE_CHANGED');
const reports = [];
for (const name of await fs.readdir('tmp/qa-seller-browser')) {
  const file = `tmp/qa-seller-browser/${name}/wp7a5-browser.json`;
  if (await exists(file)) reports.push({ file, ...(await read(file)) });
}
const runs = [];
for (const token of await fs.readdir('tmp/qa-wp7a5-backend')) {
  const folder = `tmp/qa-wp7a5-backend/${token}`;
  if (!(await exists(folder + '/runner.json'))) continue;
  const runner = await read(folder + '/runner.json');
  const cases = junitCases(await fs.readFile(folder + '/backend-results.xml', 'utf8'));
  runs.push({
    token,
    file: folder + '/backend-results.xml',
    at: (await fs.stat(folder + '/runner.json')).mtime.toISOString(),
    exit_code: runner.exit_code,
    tests: cases.length,
    passed: cases.filter((c) => c.status === 'PASS').length,
    failed: cases.filter((c) => c.status === 'FAIL').length,
    skipped: cases.filter((c) => c.status === 'SKIPPED').length,
    cases,
  });
}
runs.sort((a, b) => a.at.localeCompare(b.at));
const effective = new Map();
for (const run of runs) for (const c of run.cases) effective.set(c.key, { ...c, token: run.token });
const cases = [...effective.values()];
const backend = {
  complete: cases.length > 0,
  tests: cases.length,
  failures: cases.filter((c) => c.status === 'FAIL').length,
  errors: 0,
  skipped: cases.filter((c) => c.status === 'SKIPPED').length,
  cases,
  runs: runs.map(({ cases: _, ...r }) => r),
};
// Manual acceptance review is deliberately separate from a green scenario outcome.
// Routes/actions below still lack a named required permutation; no exclusion or denominator reduction.
const missing = {
  'R-55e822d5':
    'Configured-only overview checked; connected/revoked/expired account projections not fully exercised.',
  'R-551d2f8c':
    'Exact draft/reload checked; full prerequisite correction and missing/expired/revoked/stale HUMAN authorization permutations unexecuted.',
  'R-db243c36':
    'Exact draft/reload checked; supported manual preparation/readiness/review permutations incomplete. No invented Meesho OAuth or dispatch.',
  'R-d6a495d5':
    'Exact draft/reload checked; full readiness and HUMAN authorization permutations incomplete. Authorization/readiness guard requires separate focused reproduction.',
  'R-3feda36d':
    'Video draft with exact thumbnail/metadata is targeted; separate image-only draft and stale review permutations remain incomplete.',
  'L-16':
    'Exact binding and disabled-destination recovery tested; artifact-version replacement and dependency ordering still require browser evidence.',
  'L-17':
    'Local fake account/wizard checked; content/image creative and missing/expired/disabled authorization permutations remain unexecuted.',
};
for (const e of ledger.entries) {
  const latest = contexts.map((c) => e.attempts.findLast((a) => a.context === c)).filter(Boolean);
  const scenarioPass = latest.length === 4 && latest.every((a) => a.status === 'PASS');
  e.scenario_status = rollup(e, contexts).status;
  e.status = e.scenario_status;
  e.evidence_integrity =
    latest.length === 4 &&
    (
      await Promise.all(
        latest.map(
          async (a) =>
            !!a.screenshot && !!a.trace && (await exists(a.screenshot)) && (await exists(a.trace)),
        ),
      )
    ).every(Boolean);
  e.evidence_integrity =
    e.evidence_integrity &&
    latest.every((a) => {
      const report = reports.find((r) => r.token === a.token);
      return (
        report &&
        !report.setup_failure &&
        !report.trace_failure &&
        report.database?.some((d) => d.context === a.context)
      );
    });
  e.acceptance_review = {
    complete: scenarioPass && !missing[e.id],
    remaining:
      missing[e.id] ||
      (scenarioPass
        ? null
        : latest.find((a) => a.status !== 'PASS')?.reason ||
          'Four passing browser contexts required'),
    basis:
      'Exact original A4 missing condition, A5 browser interactions, canonical API assertions and owned ORM snapshots; not route rendering alone.',
  };
  if (scenarioPass && (missing[e.id] || !e.evidence_integrity)) e.status = 'PARTIAL';
  e.full_closure = e.acceptance_review.complete && e.evidence_integrity;
  e.current_status = e.status;
  e.final_disposition = e.full_closure
    ? 'VERIFIED_LOCAL_SUPPORTED_ACCEPTANCE'
    : e.acceptance_review.remaining ||
      'Required screenshot/trace/owned database snapshot integrity is incomplete';
}
ledger.status = 'INCOMPLETE';
ledger.counts = Object.fromEntries(
  ['PASS', 'PARTIAL', 'FAIL', 'BLOCKED', 'NOT_TESTED'].map((s) => [
    s,
    ledger.entries.filter((e) => e.status === s).length,
  ]),
);
ledger.updated_at = new Date().toISOString();
const blockers = ledger.entries
  .filter((e) => !e.full_closure)
  .map((e) => `${e.id}: ${e.final_disposition}`);
const result = gate({ entries: ledger.entries, audit, quality, backend, blockers });
ledger.status = result.status;
const scans = reports.flatMap((r) => r.scans || []);
const lastScans = new Map();
for (const report of reports.sort((a, b) =>
  (a.checks[0]?.at || '').localeCompare(b.checks[0]?.at || ''),
))
  for (const scan of report.scans || []) lastScans.set(scan.id + ':' + scan.context, scan);
const latestScans = [...lastScans.values()];
const accessibility = {
  executed_scans: scans.length,
  latest_scans: latestScans.length,
  violations: latestScans.reduce((n, s) => n + (s.violations?.length || 0), 0),
  incomplete: latestScans.reduce((n, s) => n + (s.incomplete?.length || 0), 0),
  manual_review:
    'Automated axe and focus/Tab/Shift+Tab checks do not certify complete WCAG compliance; incomplete nodes and full screen-reader/keyboard workflows remain manual review.',
};
await fs.writeFile(root + 'wp7a5-coverage-ledger.json', JSON.stringify(ledger, null, 2));
await fs.writeFile(
  root + 'wp7a5-gate.json',
  JSON.stringify(
    { ...result, backend, quality, accessibility, generated_at: new Date().toISOString() },
    null,
    2,
  ),
);
const matrix = [
  '| Original ID | A4 | Latest scenario | Acceptance | Remaining / disposition |',
  '|---|---|---|---|---|',
  ...ledger.entries.map(
    (e) =>
      `| ${e.id} | PARTIAL | ${e.scenario_status} | ${e.full_closure ? 'CLOSED' : e.status} | ${String(e.final_disposition).replaceAll('|', '/')} |`,
  ),
].join('\n');
const browser = [
  '# WP7A-5 browser evidence',
  '',
  matrix,
  '',
  '## Retained executions',
  '',
  '| Run | Selected IDs | Checks | PASS | FAIL | PARTIAL | BLOCKED | Owned ORM snapshots |',
  '|---|---|---|---|---|---|---|---|',
  ...reports.map(
    (r) =>
      `| ${r.token} | ${(r.selected_ids || []).length} | ${r.checks.length} | ${r.checks.filter((c) => c.status === 'PASS').length} | ${r.checks.filter((c) => c.status === 'FAIL').length} | ${r.checks.filter((c) => c.status === 'PARTIAL').length} | ${r.checks.filter((c) => c.status === 'BLOCKED').length} | ${(r.database || []).length} |`,
  ),
  '',
  'Each run is under `tmp/qa-seller-browser/<token>/`: `wp7a5-browser.json`, four context directories, viewport/full-page PNGs, state JSON and trace.zip. Per-entry exact references and chronological failures/retests are retained in the coverage ledger. EXECUTED means attempted, not assertions passed.',
  '',
  'Installed Chrome/Edge were used, at 1440×900 and 390×900. Every fixture is disposable and synthetic. Canonical APIs prepare fixtures; real UI interactions and reload assertions are recorded separately. No live provider certification or external execution is inferred.',
  '',
  '## Accessibility',
  '',
  `Latest scans: ${accessibility.latest_scans}; violation-rule occurrences: ${accessibility.violations}; incomplete-rule occurrences: ${accessibility.incomplete}. ${accessibility.manual_review}`,
  '',
  '## Reproduction',
  '',
  '```powershell',
  'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a5.ps1 -Action Browser',
  '# Optional exact-ID replay: set $env:QA_WP7A5_IDS to comma-separated original IDs.',
  '# Four contexts remain mandatory; -Focused is debugging only, not certification.',
  '```',
  '',
].join('\n');
await fs.writeFile(root + 'wp7a5-browser-evidence.md', browser);
const passing = (required) =>
  required.every((id) =>
    contexts.every(
      (context) =>
        ledger.entries.find((e) => e.id === id)?.attempts.findLast((a) => a.context === context)
          ?.status === 'PASS',
    ),
  );
const defects = [
  [
    'A5-D01',
    'P2',
    'Exact activity route used overview instead of activity detail; long unwrapped JSON obstructed mobile navigation.',
    'CampaignVideoComponent now uses existing videoDetail, clears stale views and ignores superseded async responses; JSON wraps. Exact generation deep link is consumed by AI Video.',
    ['R-794214d7'],
  ],
  [
    'A5-D02',
    'P2',
    'Bulk Video could queue work but lacked durable reopen/recovery controls.',
    'Existing operation/history/retry/cancel APIs are exposed with exact query identity, busy guards and reload. No worker or execution authority duplicated.',
    ['L-21'],
  ],
  [
    'A5-D03',
    'P2',
    'SEO metadata lacked scoped edit/reload and safe duplicate-name conflict handling; success used an error banner.',
    'Canonical GET/PUT sets, keyword revision selection and scoped history; save feedback is separate. Unique violations map to 409, unavailable FK to 422, other database failures are not suppressed.',
    ['L-15'],
  ],
  [
    'A5-D04',
    'P1',
    'Video composer sent a generation ID to legacy text-post creation, losing the intended Video handoff contract.',
    'Reuses canonical Video channel preview/prepare and explicit HUMAN confirmation to create a draft only. Exact output/thumbnail/metadata/version are pinned. Confirm response exposes durable social_post_id, including replay.',
    ['L-22'],
  ],
  [
    'A5-D05',
    'P1',
    'Failed image job left ImageOutput queued, hiding canonical recovery. Retry success also left its attempt observation incomplete.',
    'finish_ai_job persists image state and failure count once across projections; recovery resets exact unprocessed output. Success records current attempt checkpoint/completion without rewriting failed attempts. No output is auto-approved.',
    ['L-12'],
  ],
  [
    'A5-D06',
    'P1',
    'Bulk-text status polling and concurrent retry acquired conflicting projection locks (observed SQLSTATE 40P01).',
    'Status/retry/cancel serialize on the same owned parent before touching children. Eight-request regression preserves two exact jobs and artifact identities.',
    ['L-13'],
  ],
  [
    'A5-D07',
    'P1',
    'Bulk-Video status polling and retry similarly deadlocked (observed SQLSTATE 40P01).',
    'Status/retry/cancel/projection routes lock the owned parent before children; mixed poll/retry regression and real-browser concurrent replay added.',
    ['L-21'],
  ],
  [
    'A5-D08',
    'P1',
    'Populated observation list returned ORM instances inside list[Any], causing PydanticSerializationError; verification/provenance were not visible.',
    'List validates rows with existing TrendObservationResponse before serialization. UI shows exact verification or UNKNOWN, synthetic flag and provenance. Decimal API values and arithmetic remain unchanged.',
    ['R-184826c3'],
  ],
  [
    'A5-D09',
    'P2',
    'Persisted marketing-plan version/budget review lacked a discoverable supported update path.',
    'Existing detail/recommendation/history and budget preview/HUMAN confirmation are exposed; Decimal input remains text, expected version/fingerprint and idempotency remain canonical.',
    ['L-23'],
  ],
  [
    'A5-D10',
    'P2',
    'Long Social account options widened the mobile fieldset and put Next outside the usable viewport.',
    'Fieldsets/grid tracks and native controls now allow shrinking within the viewport; long bound identifiers wrap. Browser assertions check actual document width without force-clicks.',
    ['L-22'],
  ],
];
await fs.writeFile(
  root + 'wp7a5-defect-register.md',
  [
    '# WP7A-5 defect and limitation register',
    '',
    'Earlier failed screenshots, traces and JUnit are retained. Scoped RETESTED means the linked correction passed its latest four browser contexts; it does not close other acceptance conditions or certify the application.',
    '',
    '| ID | Priority | Confirmed cause | Correction | Retest | Evidence IDs |',
    '|---|---|---|---|---|---|',
    ...defects.map(
      ([id, priority, cause, fix, targets]) =>
        `| ${id} | ${priority} | ${cause} | ${fix} | ${passing(targets) ? 'RETESTED — scoped' : 'OPEN / retest incomplete'} | ${targets.join(', ')} |`,
    ),
    '',
    '## Harness corrections (not application defects)',
    '',
    'The first backend run exposed missing seeded AI templates, disabled intelligence metadata and absent ephemeral credential encryption in isolated test fixtures. Fixtures now opt into only the local metadata/fake transport configuration they test. Real mutation remains disabled and socket egress remains blocked. Amazon/Flipkart fake positive controls temporarily exercise their explicit emergency-stop negative cases; production settings were not relaxed.',
    '',
    'Browser assumptions corrected: lowercase marketplace enums; exact supported content types; server-pinned Activity artifact version; unchanged SEO fingerprint reuses the analysis ID; implicit select labels include option text; Video approval waits for the selected generation. Decimal values are compared using Decimal rather than incidental fixed-scale string formatting. These corrections are not counted as production defect resolutions.',
    '',
    '## Remaining local coverage and inspection concerns',
    '',
    ...Object.entries(missing).map(([id, reason]) => `- ${id}: ${reason}`),
    '',
    'Amazon authorization/readiness inspection concern: issue_listing_execution_authorization validates approved review/fingerprint but does not invoke listing_readiness. This needs a narrowly scoped negative runtime reproduction and contract review before any guard change; it is not represented as a reproduced external-write vulnerability. Existing submission/worker gates remain in force; no submission was attempted.',
    '',
    'Historical Ads502, unattributed PostgreSQL timestamp drift, financial history/reconciliation limitations, repository-wide static debt, manual/incomplete accessibility and parked PC-first backup are not closed by this package.',
    '',
  ].join('\n'),
);
const regressionTable = [
  '| Backend token | Tests | Passed | Failed | Skipped | Exit |',
  '|---|---|---|---|---|---|',
  ...backend.runs.map(
    (r) =>
      `| ${r.token} | ${r.tests} | ${r.passed} | ${r.failed} | ${r.skipped} | ${r.exit_code} |`,
  ),
].join('\n');
const qualityTable = [
  '| Check | Status | Passed tests |',
  '|---|---|---|',
  ...quality.checks.map((c) => `| ${c.id} | ${c.status} | ${c.passed ?? '—'} |`),
].join('\n');
const report = [
  '# WP7A-5 closure report',
  '',
  `Decision: **WP7A ${result.status}**. Application certification and real-business launch remain INCOMPLETE / NOT CERTIFIED. Stop at WP7A-5.`,
  '',
  `Original denominator: 48. Historical closures preserved: 32. Exact targets: 16. Newly closed: ${result.newly_closed}. Still open: ${result.open_entries.length}. No denominator reduction, nearby-route substitution or live-provider exclusion.`,
  '',
  matrix,
  '',
  '## Actual regression evidence',
  '',
  regressionTable,
  '',
  `Latest unique-case census: ${backend.tests} tests, ${backend.tests - backend.failures - backend.skipped} passed, ${backend.failures} failed, ${backend.skipped} skipped (overlapping retests are not added). JUnit preserves each earlier failure; see wp7a5-gate.json for case identities and run references.`,
  '',
  qualityTable,
  '',
  'Commands and sanitized exit codes are retained in `tmp/qa-wp7a5/quality.json`; earlier quality failures are preserved in timestamped quality reports. Backend commands: `scripts/test-seller-wp7a5.ps1 -Action Backend`, `-Action Backend -Focused` (Studio/image adjacency), and `-Action BackendRemaining` (image/core, bulk-Video and populated trends). No static-check pass is a substitute for browser acceptance.',
  '',
  '## Isolation and recovery',
  '',
  `Read-only audit: ${audit.status}. Database absence: ${audit.database_absence_status}; historical report/matrix hashes unchanged: ${audit.historical_baseline_unchanged}. Exact run states and independent absence are in tmp/qa-wp7a5-final-audit.json.`,
  '',
  'The exact HUMAN-approved recovery for 11e7601f51503966 / OID 11877071 used existing signed guards, attested instance/container, QA-role ownership, zero sessions and no matching test processes, then non-FORCE resume_drop. Recovery took 2.312 seconds; independent absence was checked. It grants no recovery authority for any other database.',
  '',
  '## Architecture / files',
  '',
  'No migration, ownership-model change or new consequential business authority. The fixes reuse exact Campaign Video detail, Studio/image recovery, existing SEO sets, canonical Video channel preparation/HUMAN draft confirmation, and marketing budget preview/confirmation. Touched files may include pre-existing worktree edits; no unrelated changes are claimed.',
  '',
  'Production: ai/{bulk_service,studio_worker,studio_router,seo_router}.py; video/{bulk,channels}.py; intelligence/trend_router.py; Angular Campaign Video, AI Video/bulk/image review/SEO/service, Social service/workspace, Marketing plan, Trend service/workspace and their focused specs. QA: wp7a5-* modules, scripts/test-seller-wp7a5.ps1, scoped shared harness phase extensions, fixture snapshots and read-only audit reuse. Backend regression/fixture repairs are in test_seller_wp7a5.py, test_ai_video_bulk_e2e.py, test_trend_analysis_api.py, test_social_video_acceptance.py and Amazon/Flipkart control fixtures.',
  '',
  '## Remaining risks and scope',
  '',
  'Marketplace authorization/readiness and Ads creative permutations remain explicit local gaps, not certified real integrations. Canonical HUMAN approvals, emergency stops, owner isolation, UNKNOWN and provenance are preserved. Historical Ads502 remains unreproduced/unclassified; PostgreSQL StartedAt/FinishedAt drift remains unattributed even when database cleanup passes. Historical typing/lint debt, financial reconciliation/history requirements, incomplete/manual accessibility and parked PC-first backup remain open. Focused static success does not establish repository-wide typing or production readiness.',
  '',
  'No permanent/golden database initialization/modification, real credentials/provider calls, marketplace mutation, supplier/RFQ/payment/procurement, unrelated Docker lifecycle action, branch, commit or push was performed. No WP7B/C/WP8 work was started.',
  '',
].join('\n');
const changedFiles = [
  ...[
    'ai/bulk_service.py',
    'ai/studio_worker.py',
    'ai/studio_router.py',
    'ai/seo_router.py',
    'video/bulk.py',
    'video/channels.py',
    'intelligence/trend_router.py',
  ].map((v) => 'apps/api/vayujit_api/' + v),
  ...[
    'test_seller_wp7a5.py',
    'test_ai_video_bulk_e2e.py',
    'test_trend_analysis_api.py',
    'test_social_video_acceptance.py',
    'test_pr_sos_02_amazon_controls.py',
    'test_pr_sos_03_flipkart_controls.py',
  ].map((v) => 'apps/api/tests/' + v),
  ...[
    'campaigns/campaign-video.component.ts',
    'ai/ai.service.ts',
    'ai/ai-video.component.ts',
    'ai/ai-video-bulk.component.ts',
    'ai/ai-image-review.component.ts',
    'ai/ai-seo.component.ts',
    'social/social.service.ts',
    'social/social-workspace.component.ts',
    'ads/marketing-plan.component.ts',
    'intelligence/trend-intelligence.service.ts',
    'intelligence/trend-intelligence-workspace.component.ts',
    'ai/ai-wp7a5.spec.ts',
    'ai/ai-image-review.component.spec.ts',
    'social/social-workspace.component.spec.ts',
    'ads/marketing-plan.component.spec.ts',
    'intelligence/trend-intelligence-workspace.component.spec.ts',
  ].map((v) => 'apps/web/src/app/' + v),
  ...[
    'wp7a5-register.mjs',
    'wp7a5-safety.mjs',
    'wp7a5-scenarios.mjs',
    'wp7a5-revision.mjs',
    'wp7a5-quality.mjs',
    'wp7a5-gate.mjs',
    'wp7a5-report.mjs',
    'wp7a5_snapshot.py',
    'wp7a5_lifecycle_status.py',
    'wp7a5_recover_approved.py',
    'wp7a5_final_audit.py',
    'unit/wp7a5-safety.test.mjs',
    'unit/wp7a5-gate.test.mjs',
    'wp7a4-browser.mjs',
    'wp7a4-rollup.mjs',
    'wp7-run.mjs',
    'safety.mjs',
    'server.mjs',
    'seller-browser-session.mjs',
    'seller-browser-explore.mjs',
    'wp7a_fixture.py',
    'wp7a2_fixture.py',
    'wp7a3_fixture.py',
    'wp7a4_fixture.py',
    'fixture_server.py',
    'wp4_final_audit.py',
    'wp7a4_final_audit.py',
  ].map((v) => 'qa/' + v),
  'scripts/test-seller-wp7a5.ps1',
];
await fs.writeFile(
  root + 'wp7a5-closure-report.md',
  report +
    '\n## Scoped touched-file inventory\n\n' +
    changedFiles.map((f) => '- `' + f + '`').join('\n') +
    '\n\nThe seven A5 documents/addendum in this directory are additional deliverables. Other dirty-worktree files are not attributed to this work.\n',
);
await fs.writeFile(
  root + 'wp7-journey-coverage-matrix-wp7a5-addendum.md',
  [
    '# WP7 matrix — WP7A-5 additive evidence',
    '',
    'The frozen canonical matrix and previous addenda remain unchanged. This additive register refers to the original 48 entries, preserving 32 prior closures and the exact 16 A5 targets. It does not certify unrelated routes.',
    '',
    matrix,
    '',
    'See wp7a5-coverage-ledger.json, wp7a5-browser-evidence.md, wp7a5-defect-register.md and wp7a5-gate.json.',
    '',
  ].join('\n'),
);
console.log(
  JSON.stringify({
    status: result.status,
    newly_closed: result.newly_closed,
    remaining: result.open_entries.length,
    backend_tests: backend.tests,
    backend_failures: backend.failures,
    accessibility,
  }),
);
