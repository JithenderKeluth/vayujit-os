// Build a conservative, reproducible WP7A addendum, never alter WP7's decision.
import fs from 'node:fs/promises';
import { junitCases } from './wp7-quality.mjs';
const read = async (p) => JSON.parse(await fs.readFile(p, 'utf8'));
const exists = async (p) =>
  fs
    .access(p)
    .then(() => true)
    .catch(() => false);
const baseline = await read('tmp/qa-wp7a/baseline.json');
const browserRuns = [];
for (const folder of await fs.readdir('tmp/qa-seller-browser')) {
  const root = 'tmp/qa-seller-browser/' + folder;
  if (!(await exists(root + '/wp7a-run.json'))) continue;
  const r = await read(root + '/wp7a-browser.json').catch(() => null);
  const execution = (await read(`tmp/qa-wp7a/execution-${folder}.json`).catch(() => []))[0];
  browserRuns.push({
    token: folder,
    root,
    report: r,
    execution,
    passed: r?.checks.filter((c) => c.status === 'PASS').length || 0,
    failed: r?.checks.filter((c) => c.status === 'FAIL').length || 0,
  });
}
browserRuns.sort((a, b) =>
  (a.execution?.started_at || '').localeCompare(b.execution?.started_at || ''),
);
const full = browserRuns.filter((r) => r.report?.checks.length === 80);
const latest = full.at(-1);
const backend = [];
for (const token of await fs.readdir('tmp/qa-wp7a-backend')) {
  const root = `tmp/qa-wp7a-backend/${token}`;
  if (!(await exists(root + '/backend-results.xml'))) continue;
  const cases = junitCases(await fs.readFile(root + '/backend-results.xml', 'utf8'));
  backend.push({
    token,
    root,
    cases,
    completed_ms: (await fs.stat(root + '/backend-results.xml')).mtimeMs,
    runner: await read(root + '/runner.json'),
    cleanup: await read(root + '/cleanup.json'),
  });
}
backend.sort((a, b) => a.completed_ms - b.completed_ms);
const effectiveBackend = new Map(backend.flatMap((b) => b.cases).map((c) => [c.key, c.status]));
const quality = await read('tmp/qa-wp7a/quality-checks.json');
const audit = await read('tmp/qa-wp7a-final-audit.json');
if (
  !latest ||
  latest.report.status === 'RUNNING' ||
  latest.execution?.cleanup?.status !== 'CLEANED'
)
  throw Error('WP7A_COMPLETED_MATRIX_AND_CLEANUP_REQUIRED');
const targets = [
  {
    id: 'B',
    capability: 'Opportunity discovery and research',
    why: 'WP7 reviewed saved candidates but did not execute the full discovery/provider-failure/retry path.',
    evidence:
      'B-01–06; real UI goal/plan/start, local synthetic partial results, classified provider failure, retry/replay, committed response loss, original goal navigation, truthful unavailable-category result.',
    remaining:
      'Source-observation freshness/staleness under materially changed research inputs has not been exercised. B-05 proves goal/navigation identity, not this broader semantic gate.',
  },
  {
    id: 'G',
    capability: 'Inventory adjustment and recovery',
    why: 'Opening-stock and route review did not establish browser adjustment/recovery.',
    evidence:
      'G-01–05; actual positive/negative/zero/insufficient adjustments, response loss after commit, replay, stale version, double click, persisted ledger, sibling variant isolation, reload and unauthenticated denial.',
    remaining: null,
  },
  {
    id: 'H',
    capability: 'Marketplace authorization boundaries',
    why: 'Prior route checks did not prove missing/invalid/expired/revoked persisted authorization states and session recovery.',
    evidence:
      'H-01–04; Amazon/Flipkart credential-free accounts; missing/expired/invalid/revoked disabled UNVERIFIED states; UI error recovery; persisted session expiry/relogin; negative internal import requests rejected before dispatch.',
    remaining: null,
  },
  {
    id: 'L',
    capability: 'Video, Ads and creative workflow',
    why: 'Earlier empty reads/layout evidence did not establish populated queue/storyboard/caption flows.',
    evidence:
      'L-01–05; local queue and replay without worker output, pending-review caption validation/save/reload, draft row-version and stale-write rejection, read failure/retry, Ads wizard preparation and authoritative preview rejection, recovery catalog and 502 monitoring.',
    remaining:
      'Failed-generation worker/job retry and approved immutable storyboard version cloning were not exercised in the browser. Ads saved/observed campaign recovery is not covered by an empty campaign plus taxonomy catalog; no campaign confirmation was admitted.',
  },
];
for (const t of targets) {
  const rows = latest?.report.checks.filter((c) => c.matrix_id === t.id) || [];
  t.previous_status = baseline.targeted_matrix_ids.find((j) => j.id === t.id)?.status;
  t.executed = rows.length;
  t.passed = rows.filter((r) => r.status === 'PASS').length;
  t.failed = rows.filter((r) => r.status === 'FAIL').length;
  t.new_status = t.failed
    ? 'FAIL'
    : t.remaining || !t.executed
      ? 'PARTIAL / INCOMPLETE'
      : 'PASS — BOUNDED LOCAL SCOPE';
}
const defects = [
  {
    id: 'SE-WP7A-VIDEO-QUEUE-001',
    priority: 'P1',
    root: 'Migration 0030 explicitly supplied nullable=None for six ORM-optional AI job recovery fields, resulting in NOT NULL PostgreSQL columns. Normal queued jobs omitted them and failed.',
    fix: 'Migration 0150 drops only those NOT NULL constraints; verifies exact column types/defaults, retains every row/value and refuses unsafe downgrade.',
    files: [
      'apps/api/alembic/versions/20261207_0150_ai_job_optional_recovery.py',
      'apps/api/tests/test_seller_wp7a.py',
      'apps/api/tests/test_seller_wp6a_migration.py',
    ],
    test: 'Original 50/51 run retains NotNullViolation. Retest 56/56 includes empty roundtrip, NULL rollback refusal and historical non-NULL value preservation; L-01 browser queue/replay.',
  },
  {
    id: 'SE-WP7A-RESEARCH-EMPTY-001',
    priority: 'P1',
    root: 'An explicit category with no local fixture reached an uncaught LookupError in execute_run; HTTP 500 replaced a legitimate no-results outcome.',
    fix: 'Persist PARTIAL / NO_USEFUL_PRODUCT_CANDIDATES, failed discovery checkpoint and no external writes, matching the existing blocked-research architecture. Never relax the category or add fake candidates.',
    files: [
      'apps/api/vayujit_api/intelligence/business_agent_service.py',
      'apps/api/tests/test_seller_wp7a.py',
    ],
    test: 'Sanitized LookupError frames in 900ec8ca748fa174; two unavailable categories start/start/retry/reload and database zero opportunities; B-06 actual UI.',
  },
  {
    id: 'SE-WP7A-SELECTOR-CONTEXT-001',
    priority: 'P1',
    root: 'Business context selector loaded active-brand products only and changing its Brand did not reload products, so later brands could not choose their actual product.',
    fix: 'Request the explicit brand, clear old product/artifact/media identities on user brand change, ignore late superseded context responses. Backend ownership guards unchanged.',
    files: [
      'apps/web/src/app/shared/business-entity-selectors.component.ts',
      'apps/web/src/app/shared/business-entity-selectors.component.spec.ts',
    ],
    test: '0b083ed8209c786d mobile/Edge L-01 failure; two new Angular cases plus independent four-context browser retest.',
  },
  {
    id: 'SE-WP7A-CAPTION-FEEDBACK-001',
    priority: 'P2',
    root: 'addCaption retained previous error/success notices across a new request, so a persisted successful caption still displayed its previous rejection.',
    fix: 'Clear prior feedback at the next valid caption attempt, retain authoritative failure and pending HUMAN review semantics.',
    files: [
      'apps/web/src/app/ai/ai-video.component.ts',
      'apps/web/src/app/ai/ai-video.component.spec.ts',
    ],
    test: '900ec8ca748fa174 L-02 before evidence; invalid then valid actual caption save/reload, focused Angular failure/retry test.',
  },
  {
    id: 'SE-WP7A-STORYBOARD-CONTEXT-001',
    priority: 'P2',
    root: 'Storyboard cards showed version but no board/product identity; same-version drafts were ambiguous.',
    fix: 'Display exact board ID and product ID; no new selection/version authority.',
    files: [
      'apps/web/src/app/ai/ai-video.component.ts',
      'apps/web/src/app/ai/ai-video.component.spec.ts',
    ],
    test: '84b191290279edf4 L-03 before evidence; two same-version cards regression; actual editor save and stale row-version conflict.',
  },
  {
    id: 'SE-WP7A-RESEARCH-CONTRAST-001',
    priority: 'P1',
    root: 'Secondary-action anchors received a dark background but were omitted from the shared button foreground rule; axe measured blue #0000ee on #42616a at 1.4:1.',
    fix: 'Include action-link in the existing accessible foreground/padding/theme rule and responsive sizing; no rule suppression.',
    files: [
      'apps/web/src/app/intelligence/business-agent-workspace.css',
      'qa/unit/wp7a-safety.test.mjs',
    ],
    test: 'a2626483fc580c9f B-02/B-03/B-06 serious axe findings; later populated-state scans.',
  },
  {
    id: 'SE-WP7A-RESEARCH-HEADINGS-001',
    priority: 'P2',
    root: 'Decision brief embeds a shared H3 evidence card under an H4 section, followed by H5 summaries, skipping levels.',
    fix: 'Configurable semantic heading level with unchanged H3 default; this nested card requests H5.',
    files: [
      'apps/web/src/app/shared/evidence-card.component.ts',
      'apps/web/src/app/shared/evidence-card.component.spec.ts',
      'apps/web/src/app/intelligence/business-agent-workspace.component.ts',
    ],
    test: '0b083ed8209c786d B-03 heading-order findings in all four contexts; explicit heading regression and actual axe rescans.',
  },
];
const unresolved = defects.filter((d) =>
  latest?.report.checks.some(
    (c) =>
      c.status !== 'PASS' &&
      (
        {
          B: [
            'SE-WP7A-RESEARCH-EMPTY-001',
            'SE-WP7A-RESEARCH-CONTRAST-001',
            'SE-WP7A-RESEARCH-HEADINGS-001',
          ],
          L: [
            'SE-WP7A-VIDEO-QUEUE-001',
            'SE-WP7A-SELECTOR-CONTEXT-001',
            'SE-WP7A-CAPTION-FEEDBACK-001',
            'SE-WP7A-STORYBOARD-CONTEXT-001',
          ],
        }[c.matrix_id] || []
      ).includes(d.id),
  ),
);
for (const d of defects)
  d.status = unresolved.includes(d)
    ? 'RETEST_NOT_GREEN'
    : latest?.report.status === 'PASS' && backend.some((b) => b.runner.exit_code === 0)
      ? 'RESOLVED_IN_SCOPED_INDEPENDENT_RETEST'
      : 'IMPLEMENTED / RETEST_PENDING';
const incomplete = targets
  .filter((t) => t.remaining)
  .map((t) => ({ matrix_id: t.id, status: 'NOT_FULLY_DEMONSTRATED', reason: t.remaining }));
const gate = {
  package: 'WP7A',
  date: new Date().toISOString(),
  status: 'INCOMPLETE',
  application_certification: 'INCOMPLETE / WP7 ORIGINAL FAIL UNCHANGED',
  parent_finding: baseline.parent_finding,
  scope:
    'Offline synthetic critical-journey coverage addendum; no live integration or release certification',
  original_baseline: 'tmp/qa-wp7a/baseline.json',
  baseline_unchanged: audit.original_baseline_unchanged,
  targeted_matrix: targets,
  subcase_contracts: [
    ...new Map(
      (latest?.report.checks || []).map((c) => [
        c.id,
        {
          id: c.id,
          existing_matrix_id: c.matrix_id,
          expected_seller_behavior: c.name,
          why_wp7_did_not_close: targets.find((t) => t.id === c.matrix_id).why,
          required_environment:
            'Approved signed disposable PostgreSQL, actual authenticated Chrome/Edge at desktop/mobile, synthetic owner and owned exact-context artifacts',
          evidence_required:
            'Real UI actions and persistence/negative assertions; exact check and ORM snapshots in wp7a-browser.json, screenshots/network/trace in context directory',
          safety:
            'No live provider/worker; HUMAN and ownership controls unchanged; unknown evidence stays unknown',
        },
      ]),
    ).values(),
  ],
  accepted_full_browser_run: latest?.token || null,
  browser_runs: browserRuns.map((r) => ({
    token: r.token,
    evidence: r.root + '/wp7a-browser.json',
    passed: r.passed,
    failed: r.failed,
    status: r.report?.status || 'NOT_EXECUTED',
    cleanup: r.execution?.cleanup?.status || 'UNKNOWN',
  })),
  backend_runs: backend.map((b) => ({
    token: b.token,
    evidence: b.root + '/backend-results.xml',
    tests: b.cases.length,
    passed: b.cases.filter((c) => c.status === 'PASS').length,
    failed: b.cases.filter((c) => c.status === 'FAIL').length,
    skipped: b.cases.filter((c) => c.status === 'SKIPPED').length,
    runner_exit: b.runner.exit_code,
    cleanup: b.cleanup.status,
  })),
  quality,
  backend_distinct_last_observed: {
    tests: effectiveBackend.size,
    passed: [...effectiveBackend.values()].filter((s) => s === 'PASS').length,
    failed: [...effectiveBackend.values()].filter((s) => s === 'FAIL').length,
    overlapping_retests_not_added: true,
  },
  defects,
  remaining_critical_coverage: incomplete,
  cleanup: audit,
  accessibility: {
    scans: latest?.report.scans.length || 0,
    violation_instances: latest?.report.scans.reduce((n, s) => n + s.violations.length, 0) || 0,
    incomplete_rule_instances:
      latest?.report.scans.reduce((n, s) => n + (s.incomplete?.length || 0), 0) || 0,
    manual_assistive_technology: 'NOT_CERTIFIED',
    wcag_compliance: 'NOT_CLAIMED',
  },
  historical_ads_502: 'UNREPRODUCED / CAUSE UNCLASSIFIED / NOT RESOLVED',
  backup_restore: 'PARKED',
  wp7b_started: false,
  wp7c_started: false,
  wp8_started: false,
  no_live_provider_calls: true,
  no_permanent_database_modifications: true,
  no_approval_bypass: true,
  no_commits_pushes_or_branches: true,
};
const root = 'docs/qa/seller-experience/';
const table = (heads, rows) =>
  '| ' +
  heads.join(' | ') +
  ' |\n| ' +
  heads.map(() => '---').join(' | ') +
  ' |\n' +
  rows
    .map(
      (r) =>
        '| ' +
        r
          .map((x) =>
            String(x ?? '')
              .replaceAll('|', '/')
              .replaceAll('\n', ' '),
          )
          .join(' | ') +
        ' |',
    )
    .join('\n') +
  '\n';
const commands =
  '```powershell\npowershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/qa-postgres.ps1 -Action Status\npowershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a.ps1 -Action Backend\nnpm.cmd run build --workspace @vayujit/web -- --configuration production\npowershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a.ps1 -Action Browser\n# Optional diagnostic Chrome-only run: append -Focused\nnode qa/wp7a-checks.mjs\n.\\apps\\api\\.venv\\Scripts\\python.exe -m qa.wp7a_final_audit\nnode qa/wp7a-report.mjs\n```';
await fs.writeFile(root + 'wp7a-gate.json', JSON.stringify(gate, null, 2));
await fs.writeFile(
  root + 'wp7a-coverage-closure.md',
  '# WP7A — critical journey coverage closure\n\n**Decision: INCOMPLETE. Full WP7 remains INCOMPLETE; no application or production certification.**\n\nThe executed subset is materially stronger; broad unexecuted states are not promoted into PASS. Original WP7/WP6A/WP6B evidence is hash-witnessed in `tmp/qa-wp7a/baseline.json`; the read-only audit checks all 12 original files remain unchanged. Existing parent finding `SE-WP7-COVERAGE-001` remains open for the remaining scope. New B-01–06, G-01–05, H-01–04 and L-01–05 IDs are addendum children, not IDs invented retroactively in WP7.\n\n## Targeted matrix\n\n' +
    table(
      ['Existing ID', 'Previous', 'New scope status', 'Actual coverage', 'Remaining'],
      targets.map((t) => [
        t.id,
        t.previous_status,
        t.new_status,
        t.evidence,
        t.remaining || 'No outstanding scenario in this bounded local matrix',
      ]),
    ) +
    '\n## Test evidence\n\n' +
    table(
      ['Backend run', 'Tests', 'Pass', 'Fail', 'Skipped', 'Cleanup'],
      gate.backend_runs.map((r) => [r.token, r.tests, r.passed, r.failed, r.skipped, r.cleanup]),
    ) +
    '\n' +
    table(
      ['Quality check', 'Status', 'Executed count'],
      quality.map((r) => [r.name, r.status, r.tests ?? r.passed ?? 'not a test count']),
    ) +
    '\nFinal four-context browser evidence: ' +
    (latest?.token || 'NONE') +
    '; ' +
    (latest?.passed || 0) +
    ' passed / ' +
    (latest?.failed || 0) +
    ' failed; 20 independently recorded groups per context, not a whole-application census. Production build was executed successfully (422.71 kB initial). See browser report for traces, screenshots and all attempts.\n\n## Safety and architecture\n\nReattested dedicated `vayujit-qa-postgres`, PostgreSQL17.10, 127.0.0.1:55432, non-superuser `vayujit_qa_admin`, instance389b97d2-a4cd-4d9b-972e-6bb2bf5785eb, container a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23. Scope only `vayujit_qa<16-hex>_test`. Each creation/drop uses existing instance/role/token/OID/marker/signed lifecycle/active-session guards; read-only final audit independently confirms absence. No arbitrary URL inference, forced drop or new orphan-recovery permission. Original WP7 recovery retained.\n\nTest-only `wp7a_fixture.py` requires exact owned database token plus authenticated owner and x-qa-token. Fault wrappers throw offline provider-unavailable errors through normal orchestration; synthetic account sentinels are never usable credentials or verified accounts. Session expiry changes only the exact test cookie hash record. No worker executes and no Video output is fabricated. Same-origin/egress guard and global external-write deny remain. `ck_users_single_owner` unchanged.\n\n## Remaining work / stop boundary\n\n' +
    incomplete.map((r) => '- ' + r.matrix_id + ': ' + r.reason).join('\n') +
    '\n\nThese are NOT_EXECUTED/NOT_FULLY_DEMONSTRATED critical scenarios, not green tests or claims that real provider credentials are needed for every remaining local case. Further bounded offline test work is needed before a WP7A PASS; no new milestone was started. For any later WP7B/C review: complete remaining supported artifact/recovery and changed-input lineage cases, then whole-application manual accessibility and original release-risk dispositions. Historical Ads502 remains unreproduced/cause unclassified, not resolved by repeat200s.\n\n## Historical quality debt\n\nOriginal repository-wide strict mypy219 diagnostics and main.py Ruff I001 are retained, not silently fixed or counted as new passing checks. This run executes focused strict mypy on migration0150 with follow-imports=skip, not whole-repository typing certification. Web lint retains2 warnings. Such nullability/index/type debt can affect production paths not exercised here; runtime subset PASS does not dismiss it. No UNKNOWN monetary input is changed or coerced. Manual/conditional axe findings remain; no complete WCAG compliance claim. Backup/restore, real provider contracts, live registration and production activation remain separate and uncertified.\n\n## Reproduce\n\n' +
    commands +
    '\n\nFocused strict mypy also passed for the changed research service with follow-imports=skip. A final local variable annotation/name correction was rerun through the focused persisted module; its cases overlap the full backend matrix and are not added as distinct tests.\n' +
    '\n\nCommands require the already approved protected local QA profile; never substitute production/golden credentials. Do not run this in parallel with PC-first backup certification. Stop after WP7A for review.\n',
);
await fs.writeFile(
  root + 'wp7a-browser-evidence.md',
  '# WP7A — actual browser evidence\n\n' +
    table(
      ['Run token', 'PASS', 'FAIL', 'Status', 'Guarded cleanup'],
      gate.browser_runs.map((r) => [r.token, r.passed, r.failed, r.status, r.cleanup]),
    ) +
    '\nAll attempts are retained, including startup/locator/fixture mistakes. They are not added together as unique acceptance cases. The latest complete four-context run is shown below; API helpers prepare or inspect persisted state, they are not counted as user interactions.\n\n' +
    table(
      ['Context', 'Case', 'Existing matrix', 'Result', 'Actual interaction/assertion'],
      (latest?.report.checks || []).map((c) => [c.context, c.id, c.matrix_id, c.status, c.name]),
    ) +
    '\n## Browser and evidence locations\n\n' +
    JSON.stringify(latest?.report.versions || {}, null, 2) +
    '\n\nChrome and Edge at1440x900 and390x900 with fresh browser contexts; isolated cookies/storage, same synthetic owner/installation, separate brand/product fixtures. The non-active-brand cases deliberately reveal context substitution. Authenticated UI setup/login, keyboard Enter on storyboard Save, reload/back/forward, repeated clicks and exact server/database assertions are in each trace. No manual screen-reader or exhaustive keyboard certification claimed.\n\n' +
    (latest
      ? [...new Set(latest.report.checks.map((c) => c.context))]
          .map(
            (c) =>
              '- `' +
              latest.root +
              '/' +
              c +
              '/browser-evidence.json`: exact routes, visible states, network/status/console signals, captures. `' +
              latest.root +
              '/' +
              c +
              '/trace.zip`: real actions/network; screenshots in same folder.',
          )
          .join('\n')
      : 'No accepted complete matrix.') +
    '\n\n`' +
    (latest?.root || '') +
    '/wp7a-browser.json` records ORM snapshot evidence and injected failures. B-04/G-03 call the real server and abort only the committed response; canonical reload/replay prevents duplicate runs/movements. Research failure injection is test-only, marketplace invalid/expired/revoked states are synthetic, H-03/L-04 transport503s test UI response/recovery—not proof of an actual provider outage.\n\n## Accessibility\n\n' +
    JSON.stringify(gate.accessibility, null, 2) +
    '\n\nNo axe rule disabled or difficult node excluded. Detailed violations/incomplete targets remain in per-context evidence. Zero automated violations, when observed, does not close incomplete rules, full keyboard/manual/assistive testing or WCAG certification. Earlier a2626483fc580c9f color-contrast and 0b083ed8209c786d heading-order findings remain preserved.\n\n## Historical Ads502\n\nRecovery taxonomy, campaigns, overview and comparison are requested during actual browser journeys; repeat success does not explain the historical account-list502. Disposition remains UNREPRODUCED / CAUSE UNCLASSIFIED. No real ads/provider request or campaign dispatch occurred. Traces include synthetic sessions and must remain private pending sharing review.\n',
);
await fs.writeFile(
  root + 'wp7a-defect-resolution.md',
  '# WP7A — bounded defect remediation\n\n' +
    defects
      .map(
        (d) =>
          '## ' +
          d.id +
          ' — ' +
          d.priority +
          '\n\nRoot cause: ' +
          d.root +
          '\n\nCorrection: ' +
          d.fix +
          '\n\nEvidence: ' +
          d.test +
          '\n\nStatus: ' +
          d.status +
          '\n\nFiles:\n\n' +
          d.files.map((f) => '- `' + f + '`').join('\n'),
      )
      .join('\n\n') +
    '\n\n## Harness corrections, not production defects\n\nQA snapshot incorrectly read nonexistent VideoGeneration.output_media_id; it now queries owner/generation-scoped VideoOutput. Early goal creator and label locators raced lazy loading or assumed exact label text despite select options; canonical body/IDs and actual accessible names are now used. Draft storyboard editing increments row_version, not immutable version: assertion corrected to the actual contract while stale409, exactscene persistence and draft state remain required. Ads Next is a navigation control, not validation: Back preserves entered values and the real server preview rejects missing fields422. Initial Angular selector tests failed because they invoked a selection before allowing ngOnInit to settle; they now flush the initial lifecycle read before testing changes, without relaxing any assertion. Failed-run evidence is retained.\n\nThe subprocess coordinator clears its owned completed cleanup timer; SQL timeouts and deletion guards are unchanged. Safe exception telemetry records only path/type/SQLSTATE/metadata-column allowlist/source frames, never SQL, bound parameters or raw output. The read-only audit scans generated metadata and trace contents for current protected credential values/encodings. No key/credential is printed or copied into these reports.\n\n## Changed-file scope\n\nProduction changes are limited to the files above. QA foundation additions: `qa/wp7a-baseline.mjs`, `qa/wp7a-browser.mjs`, `qa/wp7a-checks.mjs`, `qa/wp7a-preserve-run.mjs`, `qa/wp7a-report.mjs`, `qa/wp7a-safety.mjs`, `qa/wp7a_fixture.py`, `qa/wp7a_probe.py`, `qa/wp7a_final_audit.py`, `qa/unit/wp7a-safety.test.mjs`, `scripts/test-seller-wp7a.ps1`. Existing QA lifecycle/proxy/launcher integration: `qa/fixture_server.py`, `qa/server.mjs`, `qa/safety.mjs`, `qa/seller-browser-explore.mjs`, `qa/seller-browser-session.mjs`, `qa/wp7-run.mjs`, `qa/wp4_final_audit.py` (read-only package scope only). Other pre-existing dirty repository files do not belong to this work package. No commit/push/branch.\n',
);
await fs.writeFile(
  root + 'wp7-journey-coverage-matrix-wp7a-addendum.md',
  '# WP7 journey matrix — WP7A addendum\n\nParent: `wp7-journey-coverage-matrix.md`; original SHA256 ' +
    baseline.files.find((f) => f.file.endsWith('wp7-journey-coverage-matrix.md')).sha256 +
    '. No original row or result rewritten. Parent finding SE-WP7-COVERAGE-001.\n\n' +
    table(
      [
        'Existing ID',
        'Prior',
        'Addendum result',
        'Executed / passed / failed',
        'Required environment',
        'Evidence',
        'Still unverified',
      ],
      targets.map((t) => [
        t.id,
        t.previous_status,
        t.new_status,
        `${t.executed} / ${t.passed} / ${t.failed}`,
        'Approved signed disposable PostgreSQL; synthetic owner; actual authenticated Chrome+Edge desktop/mobile; API+ORM reads; no external provider',
        t.evidence,
        t.remaining || 'None within the stated local case matrix',
      ]),
    ) +
    '\nAll new child case IDs and actual results are enumerated in `wp7a-browser-evidence.md`; no API-only or route-render coverage is mislabeled as completed browser action coverage. Status INCOMPLETE remains mandatory for B/L remaining critical states. This addendum does not reopen or resolve unrelated WP7 findings, manual accessibility scope, live provider certification or parked backup certification.\n',
);
console.log(
  JSON.stringify({
    status: gate.status,
    latest_browser: latest?.token,
    browser_passed: latest?.passed,
    backend_runs: gate.backend_runs,
    defects: defects.length,
  }),
);
