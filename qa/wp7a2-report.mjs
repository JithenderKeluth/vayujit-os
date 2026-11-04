// Evidence-derived report. Never converts an unexecuted or failed gate to PASS.
import fs from 'node:fs/promises';
const [browserToken, backendToken] = process.argv.slice(2);
if (![browserToken, backendToken].every((t) => /^[a-f0-9]{16}$/.test(t)))
  throw Error('EXACT_EVIDENCE_TOKENS_REQUIRED');
const read = async (p) => JSON.parse(await fs.readFile(p, 'utf8'));
const folder = `tmp/qa-seller-browser/${browserToken}`;
const browser = await read(folder + '/wp7a2-browser.json');
const cleanup = await read(folder + '/session-final.json');
const backendFolder = `tmp/qa-wp7a2-backend/${backendToken}`;
const backend = await read(backendFolder + '/runner.json');
const xml = await fs.readFile(backendFolder + '/backend-results.xml', 'utf8');
const attr = (k) => Number(xml.match(new RegExp(`<testsuite\\b[^>]*\\b${k}="(\\d+)"`))?.[1] ?? -1);
const backendCounts = {
  tests: attr('tests'),
  failures: attr('failures'),
  errors: attr('errors'),
  skipped: attr('skipped'),
};
const qualityFile = (await fs.readdir('tmp/qa-wp7a2'))
  .filter((f) => /^quality-\d+\.json$/.test(f))
  .sort()
  .at(-1);
const quality = await read('tmp/qa-wp7a2/' + qualityFile);
const postAuditFile = (await fs.readdir('tmp/qa-wp7a2'))
  .filter((f) => /^post-audit-\d+\.json$/.test(f))
  .sort()
  .at(-1);
if (postAuditFile) {
  for (const row of await read('tmp/qa-wp7a2/' + postAuditFile)) {
    const index = quality.findIndex((q) => q.name === row.name);
    if (index >= 0) quality[index] = row;
    else quality.push(row);
  }
}
const audit = await read('tmp/qa-wp7a2-final-audit.json');
const typing = await read('tmp/qa-wp7a2/typing-baseline-review.json');
const baseline = await read('tmp/qa-wp7a2/baseline.json');
const cases = [
  ['A', 'B-07', 'Changed-input research freshness'],
  ['B', 'L-06', 'Failed creative-job retry'],
  ['C', 'L-07', 'Approved storyboard cloning'],
  ['D', 'L-08', 'Persisted Ads recovery'],
].map(([id, matrix_id, name]) => {
  const checks = browser.checks.filter((c) => c.id === id);
  return {
    id,
    matrix_id,
    name,
    executed: checks.length,
    passed: checks.filter((c) => c.status === 'PASS').length,
    status: checks.length === 4 && checks.every((c) => c.status === 'PASS') ? 'PASS' : 'INCOMPLETE',
  };
});
const unverified = [
  'Original WP7 matrix L: other supported AI/image/content/campaign preparation and artifact-review actions remain unexecuted; route rendering is not functional certification.',
];
const newChecksPass =
  cases.every((c) => c.status === 'PASS') &&
  backend.exit_code === 0 &&
  backendCounts.failures === 0 &&
  backendCounts.errors === 0 &&
  cleanup.status === 'CLEANED' &&
  audit.database_absence_status === 'PASS';
const gate = {
  package: 'WP7A-2',
  date: new Date().toISOString(),
  status: 'INCOMPLETE',
  bounded_four_scenarios: newChecksPass ? 'PASS' : 'INCOMPLETE',
  application_certification: 'INCOMPLETE / original WP7 decision unchanged',
  reason:
    'The four named WP7A scenarios are bounded additions; the authoritative original L row also retains unexecuted supported creative/artifact workflows. No whole-family or application PASS is inferred.',
  targeted_matrix_ids: ['B', 'L'],
  scenarios: cases,
  additional_required_gaps: unverified,
  environment_gate: audit.status,
  quality_evidence: { full: qualityFile, post_audit: postAuditFile },
  browser: {
    token: browserToken,
    status: browser.status,
    checks: browser.checks.length,
    passed: browser.checks.filter((c) => c.status === 'PASS').length,
    failed: browser.checks.filter((c) => c.status === 'FAIL').length,
    versions: browser.versions,
    evidence: folder,
  },
  backend: {
    token: backendToken,
    exit_code: backend.exit_code,
    ...backendCounts,
    evidence: backendFolder,
  },
  quality,
  typing_debt: typing,
  accessibility: {
    scans: browser.scans.length,
    violations: browser.scans.reduce((n, s) => n + s.violations.length, 0),
    incomplete_rule_instances: browser.scans.reduce((n, s) => n + s.incomplete.length, 0),
    manual_wcag_compliance: 'NOT_CLAIMED',
  },
  lifecycle_audit: audit,
  historical_ads_502: 'UNREPRODUCED / CAUSE UNCLASSIFIED / NOT RESOLVED',
  backup_certification: 'PARKED',
  wp7b_started: false,
  wp7c_started: false,
  wp8_started: false,
  no_live_provider_calls: true,
  no_permanent_database_modifications: true,
  no_commits_pushes_or_branches: true,
  historical_baseline_preserved: baseline.files,
};
const dest = 'docs/qa/seller-experience';
await fs.writeFile(dest + '/wp7a2-gate.json', JSON.stringify(gate, null, 2));
const caseTable =
  '| Scenario | Existing matrix / addendum ID | Contexts passed | Result |\n| --- | --- | --- | --- |\n' +
  cases
    .map(
      (c) =>
        `| ${c.id} — ${c.name} | ${c.matrix_id[0]} / ${c.matrix_id} | ${c.passed}/4 | ${c.status} |`,
    )
    .join('\n');
const qualityTable =
  '| Check | Actual outcome |\n| --- | --- |\n' +
  quality
    .map(
      (q) =>
        `| ${q.name} | ${q.status}${q.passed ? ' — ' + q.passed + ' tests' : ''}${q.tests ? ' — ' + q.tests + ' tests' : ''}${q.warnings ? ' / ' + q.warnings + ' warnings' : ''} |`,
    )
    .join('\n');
const recoveryText =
  'Two interrupted-run lifecycle files were found null-filled. `67abc9a3296a0694` was independently absent; its original signature could not be validated and its new record is explicitly an absence-only attestation. `325de41be0b7492f` was an interrupted-DROP tombstone, OID8996294, owned by the QA role. After separate explicit HUMAN approvals, the exact instance/name/OID was rechecked, damaged records quarantined, task processes/sessions excluded and non-FORCE DROP used. The inaccessible tombstone marker was NOT claimed as reread. This is a two-token exception, never an automatic deletion fallback. The OS-level cause of null-filled files is unknown.';
await fs.writeFile(
  dest + '/wp7a2-coverage-closure.md',
  `# WP7A-2 — Coverage closure\n\nBounded four-scenario result: **${gate.bounded_four_scenarios}**. **WP7A INCOMPLETE; application certification INCOMPLETE.**\n\n## Authority and remaining scope\n\nRead the WP7A reports/gate, original WP7 matrix/defect register and relevant WP6A/WP6B reports. The named follow-ups are B and L; prior bounded G/H evidence is retained. Seven original historical files have frozen SHA256s in tmp/qa-wp7a2/baseline.json. They are not overwritten. ${unverified[0]} This task does not silently turn route review into action coverage or start WP7B/C/WP8.\n\n${caseTable}\n\n## Actual execution\n\nFinal browser token: ${browserToken}; ${gate.browser.passed} PASS / ${gate.browser.failed} FAIL, Chrome and Edge at1440/390. Final backend token: ${backendToken}; ${backendCounts.tests - backendCounts.failures - backendCounts.errors - backendCounts.skipped} PASS / ${backendCounts.failures} FAIL / ${backendCounts.errors} ERROR / ${backendCounts.skipped} SKIP. These are not added to overlapping earlier runs as unique coverage.\n\n${qualityTable}\n\n## Correctness boundaries\n\nA uses the supported immutable-goal revision workflow, not a mutation of historical observations. Goals, runs, candidates, timestamps and provenance are retained. Independent QA SHA256s bind inspected input/profile snapshots; the plan hash describes the step graph and is NOT falsely represented as an input fingerprint. A historical category-mismatched product is reference-only; no selection control is available in the new goal. Commercial claims remain unverified/partial.\n\nB drives the normal local queue and canonical worker into a real recorded provider failure. The owner uses the existing generation recovery API through the newly discoverable UI. Retries preserve job/attempt identity and historical evidence, clear only current error/scheduling fields and record one audit intention. The second attempt is correctly failed, not a fabricated success; no output or approval is created.\n\nC obtains genuine owner approval in the browser, then edits the approved storyboard through the supported Save-to-draft-clone contract. Duplicate/concurrent edits reuse one clone intent. The approved original remains unchanged; the new draft has explicit source audit lineage and no inherited approval. The clone is edited and reopened. The backend still rejects an unapproved clone for governed generation.\n\nD prepares and confirms a LOCAL SYNTHETIC campaign using a non-real credential marker. Exact previewed inputs/fingerprint are retained; material changes require a new preview/review. Canonical fake-connector workers record failures; repeated retries share one job, stale new intentions are409, a second observed failure gets a new recovery identity. A fresh Python application instance authenticates the persisted browser session through normal auth and Ads APIs in a read-only transaction. The owner's normal API/service is not stopped, no provider is enabled and no remote campaign is created.\n\n## Safety and recovery\n\nApproved instance389b97d2-a4cd-4d9b-972e-6bb2bf5785eb, container a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23, loopback127.0.0.1:55432, non-superuser vayujit_qa_admin, exact scope vayujit_qa<16-hex>_test. Canonical markers/tokens/role/OID/signed lifecycle and session guards remain. ${recoveryText}\n\nFinal read-only audit: ${audit.status}; ${audit.databases.length} task databases independently absent; historical baseline unchanged=${audit.historical_baseline_unchanged}; protected credential matches=${audit.extended_secret_scan.matches}. Docker preservation and trace CRC details are in wp7a2-gate.json and tmp/qa-wp7a2-final-audit.json.\n\n## Limitations and stop decision\n\nAxe: ${gate.accessibility.scans} scans, ${gate.accessibility.violations} violation instances, ${gate.accessibility.incomplete_rule_instances} incomplete-rule instances requiring review. No full WCAG/manual assistive-technology certification. Strict mypy passes for Video and Ads services; the Ads router's pre-existing diagnostics remain, with a source-baseline comparison showing ${typing.added_diagnostic_count} added diagnostic messages. This is not repository-wide typing certification. Nullable/dynamic endpoint types remain a production risk outside the executed subset. Existing web warnings are retained. Historical Ads502 remains unreproduced/cause unclassified, not resolved by repeat200s. No real integration, production activation, backup certification, publishing or marketplace write is certified.\n\n## Reproduce\n\n\`\`\`powershell\npowershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/qa-postgres.ps1 -Action Status\npowershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a2.ps1 -Action Backend\npowershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a2.ps1 -Action Browser\nnode qa/wp7a2-checks.mjs\n.\\apps\\api\\.venv\\Scripts\\python.exe -m qa.wp7a2_final_audit\nnode qa/wp7a2-report.mjs ${browserToken} ${backendToken}\n\`\`\`\n\nRequires the already approved protected QA profile, never business/golden credentials. One-time recovery commands are not normal startup/test instructions and must not be generalized. Stop after WP7A-2.\n`,
);
const contexts = [...new Set(browser.checks.map((c) => c.context))];
let attempts = [];
for (const token of await fs.readdir('tmp/qa-seller-browser')) {
  try {
    const r = await read(`tmp/qa-seller-browser/${token}/wp7a2-browser.json`);
    attempts.push({
      token,
      status: r.status,
      pass: r.checks.filter((c) => c.status === 'PASS').length,
      fail: r.checks.filter((c) => c.status === 'FAIL').length,
    });
  } catch {
    /* Not a WP7A2 browser result. */
  }
}
await fs.writeFile(
  dest + '/wp7a2-browser-evidence.md',
  `# WP7A-2 — Real browser evidence\n\nFinal evidence: ${folder}/wp7a2-browser.json. Versions: ${JSON.stringify(browser.versions)}. Each context has browser-evidence.json (route/status/console/failed-request metadata), screenshots and trace.zip. Actual Chrome/Edge binaries, not a substituted browser engine.\n\n${caseTable}\n\n| Context | Checks | Trace and screenshots |\n| --- | --- | --- |\n${contexts.map((c) => `| ${c} | ${browser.checks.filter((x) => x.context === c && x.status === 'PASS').length}/4 PASS | ${folder}/${c}/trace.zip; PNGs and browser-evidence.json in the same directory |`).join('\n')}\n\nA creates a revised goal through UI, delays the old response across navigation, replays research requests, reloads and checks historical reference-only selection boundaries. B queues, observes failure, focuses and presses Enter for retry, repeats concurrent requests, reloads queued/failed states and proves no output. C approves with keyboard Enter, edits/clones, repeats clone requests concurrently, uses Tab/Shift+Tab and Space-save for draft edits, reloads both versions and checks immutable source authority. D navigates accounts → wizard → server preview → explicit confirmation → campaigns → recovery; reloads and authenticates a fresh application process against the same persisted state, repeats recovery and observes a second failure. Synthetic provenance and UNKNOWN remain explicit. Keyboard assertions are bounded checks, not an application-wide manual accessibility claim.\n\nAxe scans=${gate.accessibility.scans}; violations=${gate.accessibility.violations}; incomplete rules=${gate.accessibility.incomplete_rule_instances}. Full rule IDs, targets, HTML and failure summaries are preserved in each browser-evidence.json and the main report scans. Incomplete checks are not suppressed or reported as WCAG success.\n\n## Failure history (not added to final unique counts)\n\n| Token | Recorded status | PASS | FAIL |\n| --- | --- | --- | --- |\n${attempts.map((a) => `| ${a.token} | ${a.status} | ${a.pass} | ${a.fail} |`).join('\n')}\n\nEarly runs include harness selector assumptions, serving a pre-rebuild Angular distribution, unbounded old-response wait (owned browser stopped; guarded cleanup retained), nested reconstruction timeout, and parsing app telemetry as one JSON document. Diagnostic details are sanitized; outcomes remain. A mid-development full run cannot certify final harness source. The accepted final run is the explicit token above. Header-bearing error logs were mechanically redacted; raw copies were not retained. Trace assets contain only disposable synthetic sessions, never permanent marketplace credentials.\n\nHistorical Ads502: UNREPRODUCED / CAUSE UNCLASSIFIED, not resolved. No502 cause is invented. Parent execution manifests under tmp/qa-wp7a2 record runtime exits and cleanup, including interrupted attempts.\n`,
);
await fs.writeFile(
  dest + '/wp7a2-defect-resolution.md',
  `# WP7A-2 — Root causes and bounded repairs\n\n| Stable ID | Root cause | Smallest correction / evidence |\n| --- | --- | --- |\n| SE-WP7A2-VIDEO-RECOVERY-001 / P1 | Existing recovery API was undiscoverable; retries kept current job errors and read stale state before locking; no retry audit. | Owner-facing Recovery/retry uses existing API, pins state/attempt, suppresses in-flight duplicates. Server serializes before validation, clears only current scheduling/error fields and appends audit. Before persisted tests fail; final B and focused regressions verify queued → second failure with no output. |\n| SE-WP7A2-STORYBOARD-CLONE-001 / P1 | Repeated edit of an approved source created another version each time; source lineage was absent from update audit. | Under source lock, normalized intent hash replays the one draft identity; canonical audit records source ID/version and approval_inherited=false. Original approval immutable; new draft not approved. Before two persisted tests and browser C fail; final C passes. |\n| SE-WP7A2-ADS-CONFIRM-001 / P1 | UI read preview_fingerprint although API returns fingerprint, and rebuilt idempotency keys/payload on confirmation. | Preserve exact preview payload/fingerprint and stable confirmation key; changed inputs invalidate review. Angular regression and D use real server preview/confirm. Early proxy403 reflected the invalid undefined-fingerprint payload, not an invented provider failure. |\n| SE-WP7A2-ADS-RECOVERY-001 / P1 | Replay ignored different target/intent; queue_job committed before recovery record, releasing concurrency lock; retries selected old failed jobs despite newer queued work. | Bind replay to owner/scope/action/failure, serialize owned campaign, queue+record atomically via optional commit=false (other callers unchanged), reject stale409. Initial persisted failures retained; final concurrency/scope/replay regressions pass. |\n| SE-WP7A2-ADS-LATEST-001 / P2 | Descending failure rows were overwritten in a dict, leaving oldest per-code observation; UI reused one key forever. | Keep first/newest observation; derive retry key from observed failure correlation. D proves second failure produces a new recovery while same-intent replay remains stable. |\n\nApplication production changes: apps/api/vayujit_api/video/service.py; apps/api/vayujit_api/ads/router.py; apps/api/vayujit_api/ads/service.py; apps/web/src/app/ai/ai-video.component.ts; apps/web/src/app/ads/ads-workspace.component.ts. Regression files: apps/api/tests/test_seller_wp7a2.py; apps/web/src/app/ai/ai-video.component.spec.ts; apps/web/src/app/ads/ads-workspace.component.spec.ts. No migration, monetary arithmetic, provider authorization or ownership-model change.\n\n## QA-specific corrections\n\nNew scoped harness: qa/wp7a2-browser.mjs, wp7a2-safety.mjs, wp7a2_fixture.py, wp7a2_reconstruct.py, wp7a2_recover.py, wp7a2_final_audit.py, wp7a2-baseline.mjs, wp7a2-checks.mjs, wp7a2-typing-review.py, wp7a2-sanitize-evidence.mjs, wp7a2-report.mjs; qa/unit/wp7a2-safety.test.mjs and test_wp7a2_recovery.py; scripts/test-seller-wp7a2.ps1. Reused central integration files: qa/fixture_server.py, qa/server.mjs, qa/safety.mjs, qa/seller-browser-explore.mjs, qa/seller-browser-session.mjs, qa/wp7-run.mjs, qa/wp7a_fixture.py, qa/wp4_final_audit.py. Other dirty files are not attributed to this package.\n\nThe earlier84-test regression result was83 PASS/1 FAIL: a legacy taxonomy test retried an entity with no failed job. Its fixture now queues a canonical local job and executes a controlled connector failure before retry; original200/scope/privacy assertions are unchanged. Final counts are in the gate. This does not permit invented production failures or real external actions. File: apps/api/tests/test_ads_failure_acceptance.py.\n\n${recoveryText}\n\nHistorical run failures are preserved. No P0/P1 application defect identified here is considered resolved solely from unit tests; final browser/persisted evidence is required. Broader original-L workflow gaps remain INCOMPLETE. Strict router typing debt is not silently fixed or dismissed: focused CLI and same-source baseline review are recorded separately. Original WP7 findings, Ads502 and full application release decision remain untouched.\n`,
);
await fs.writeFile(
  dest + '/wp7-journey-coverage-matrix-wp7a2-addendum.md',
  `# WP7 matrix — WP7A-2 traceable addendum\n\nPreserves the original matrix and previous WP7A addendum byte-for-byte. This is the current additional evidence reference, not a rewrite of original NOT_TESTED results.\n\n${caseTable}\n\nEvidence: ${folder}/wp7a2-browser.json; ${backendFolder}/backend-results.xml; wp7a2-gate.json. Prior G/H scoped closure is unchanged. B's revision/input-lineage case and L's three named cases have only the bounded outcomes shown. Original L's other supported AI/image/content/campaign preparation/artifact-review actions remain NOT_TESTED; no route-render result counts as an executed action. Full family L and WP7A remain INCOMPLETE under the conservative completion gate. Manual accessibility and real provider certification are not claimed.\n`,
);
console.log(
  JSON.stringify({
    status: gate.status,
    bounded_four_scenarios: gate.bounded_four_scenarios,
    browser: gate.browser.passed,
    backend: backendCounts.tests,
    cleanup: audit.status,
  }),
);

await fs.appendFile(
  dest + '/wp7a2-coverage-closure.md',
  `\n## Exact environment and static-check dispositions\n\nThe strict historical Docker preservation check remains **FAIL**: only the start/finish timestamps of /infrastructure-postgres-1 differ. All10 original container identities/images/mounts/networks remain structurally unchanged, and no original network or volume is missing or added. The restart cause is UNATTRIBUTED; this work does not restore/backdate the owner's container state to force PASS. Database absence is independently **${audit.database_absence_status}**. Overall environment audit is **${audit.status}**.\n\nThe raw focused Ads-router strict-mypy CLI check retains ${quality.find((q) => q.name === 'mypy-ads/router.py')?.diagnostics?.length ?? 'recorded'} diagnostics. A separate same-source, nonincremental baseline comparison records ${typing.baseline_errors} baseline versus ${typing.current_errors} current messages and ${typing.added_diagnostic_count} additions. Different analysis entry points are not summed or called identical test counts. No diagnostic is suppressed; the baseline review is not a substitute for an all-green typing gate. Web lint retains2 existing warnings.\n`,
);
await fs.appendFile(
  dest + '/wp7a2-browser-evidence.md',
  `\n## Incomplete accessibility checks — still open\n\nAll14 incomplete rule instances are color-contrast checks. Desktop Video states include textareas; mobile states additionally include research callout and horizontally constrained Video table cells/statuses. Exact HTML/targets are in the scan JSON. These nodes are not removed from scope, and incomplete is not PASS. Manual scrolling/focus/contrast review remains required.\n\n| Context | State | Rule | Affected node count |\n| --- | --- | --- | --- |\n${browser.scans.flatMap((s) => s.incomplete.map((i) => `| ${s.context} | ${s.state} | ${i.id} | ${i.nodes.length} |`)).join('\n')}\n`,
);
