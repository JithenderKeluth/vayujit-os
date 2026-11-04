import fs from 'node:fs/promises';
import path from 'node:path';
import { rollup, requiredContexts } from './wp7a4-rollup.mjs';
import { wp7a4Gate } from './wp7a4-gate.mjs';
import { saveEvidence } from './wp7a4-evidence.mjs';
const dir = 'docs/qa/seller-experience/';
const ledger = JSON.parse(await fs.readFile(dir + 'wp7a4-coverage-ledger.json', 'utf8'));
const source = JSON.parse(await fs.readFile(dir + 'wp7a3-required-coverage.json', 'utf8'));
const requiredIds = source.entries.filter((e) => !e.full_closure).map((e) => e.id);
const defects = JSON.parse(await fs.readFile('qa/wp7a4-defects.json', 'utf8'));
defects.application.push(...defects.additional_application);
const exists = async (file) =>
  Boolean(file) &&
  (await fs
    .stat(file)
    .then((s) => s.isFile())
    .catch(() => false));
const reports = [];
for (const folder of await fs.readdir('tmp/qa-seller-browser', { withFileTypes: true })) {
  if (!folder.isDirectory()) continue;
  const file = path.join('tmp/qa-seller-browser', folder.name, 'wp7a4-browser.json');
  if (await exists(file)) reports.push({ ...JSON.parse(await fs.readFile(file, 'utf8')), file });
}
reports.sort((a, b) => (a.checks[0]?.at || '').localeCompare(b.checks[0]?.at || ''));
for (const e of ledger.entries) {
  Object.assign(e, rollup(e));
  const latest = requiredContexts
    .map((context) => e.attempts.findLast((a) => a.context === context))
    .filter(Boolean);
  e.evidence_integrity = latest.length === 4;
  for (const attempt of latest)
    if (!(await exists(attempt.screenshot)) || !(await exists(attempt.trace)))
      e.evidence_integrity = false;
  if (e.status === 'PASS' && !e.evidence_integrity) {
    e.status = 'PARTIAL';
    e.full_closure = false;
    e.final_disposition = 'REQUIRED_EVIDENCE_ARTIFACT_MISSING';
  }
  e.wp7a4_remaining_evidence = e.status === 'PASS' ? [] : [e.final_disposition];
}
ledger.counts = Object.fromEntries(
  ['PASS', 'FAIL', 'BLOCKED', 'PARTIAL', 'NOT_TESTED', 'NOT_SUPPORTED'].map((k) => [
    k,
    ledger.entries.filter((e) => e.status === k).length,
  ]),
);
ledger.status = 'INCOMPLETE';
for (const defect of defects.application) {
  defect.status = defect.entries.every((id) =>
    requiredContexts.every((context) =>
      ['PASS', 'PARTIAL'].includes(
        ledger.entries.find((e) => e.id === id)?.attempts.findLast((a) => a.context === context)
          ?.status,
      ),
    ),
  )
    ? 'FIX_ASSERTIONS_RETESTED'
    : 'IMPLEMENTED_RETEST_INCOMPLETE';
}
ledger.defects = {
  application_discovered: defects.application.length,
  fix_assertions_retested: defects.application.filter((d) => d.status === 'FIX_ASSERTIONS_RETESTED')
    .length,
  workflow_gaps: defects.workflow_gaps.length,
  harness_findings: defects.harness.length,
};
ledger.updated_at = new Date().toISOString();
ledger.checkpoint.last_replay_ids ||= ledger.checkpoint.completed_ids;
ledger.checkpoint.completed_ids = ledger.entries
  .filter((e) => e.attempts.length > 0)
  .map((e) => e.id);
ledger.checkpoint.remaining_ids = ledger.entries.filter((e) => !e.full_closure).map((e) => e.id);
ledger.checkpoint.retained_fixture_records = reports.map((r) => r.file);
ledger.checkpoint.remaining_is =
  'Remaining required closure evidence, not unattempted IDs. All prior attempts retained.';
const cleanup = JSON.parse(await fs.readFile('tmp/qa-wp7a4-final-audit.json', 'utf8'));
const regressions = JSON.parse(await fs.readFile('tmp/qa-wp7a4/quality-results.json', 'utf8'));
const blockers = ledger.entries
  .filter((e) => e.status !== 'PASS')
  .map((e) => ({ id: e.id, status: e.status, reason: e.final_disposition }));
const gate = wp7a4Gate({ requiredIds, entries: ledger.entries, cleanup, regressions, blockers });
gate.counts = ledger.counts;
gate.historical_risks = [
  'Historical Ads 502 unclassified',
  'Historical PostgreSQL lifecycle timestamps unattributed; no container restart used to explain them',
  'Ads-router typing debt (not the focused changed-module mypy result)',
  'Axe incomplete/manual checks',
  'Financial-history/reconciliation limitations',
  'PC-first backup/restore remains parked',
];
await saveEvidence(dir + 'wp7a4-coverage-ledger.json', ledger);
await saveEvidence(dir + 'wp7a4-gate.json', gate);
const esc = (s) =>
  String(s ?? '')
    .replaceAll('|', '/')
    .replaceAll('\n', ' ');
const table =
  '| Original ID | Route | Outcome | Exact remaining disposition |\n|---|---|---|---|\n' +
  ledger.entries
    .map((e) => `| ${e.id} | \`${e.route}\` | ${e.status} | ${esc(e.final_disposition)} |`)
    .join('\n');
const total = reports.reduce((n, r) => n + r.checks.length, 0),
  scans = reports.flatMap((r) => r.scans);
const historicalAttempts = Object.fromEntries(
  ['PASS', 'PARTIAL', 'FAIL', 'BLOCKED'].map((status) => [
    status,
    reports.flatMap((r) => r.checks).filter((c) => c.status === status).length,
  ]),
);
const latestAttempts = ledger.entries.flatMap((e) =>
  requiredContexts.map((context) => e.attempts.findLast((a) => a.context === context)),
);
const latestAttemptCounts = Object.fromEntries(
  ['PASS', 'PARTIAL', 'FAIL', 'BLOCKED'].map((status) => [
    status,
    latestAttempts.filter((a) => a?.status === status).length,
  ]),
);
const latestScans = ledger.entries.flatMap((e) =>
  requiredContexts.flatMap((context) => {
    const attempt = e.attempts.findLast((a) => a.context === context);
    const scan = reports
      .find((r) => r.token === attempt?.token)
      ?.scans.findLast((s) => s.id === e.id && s.context === context);
    return scan ? [scan] : [];
  }),
);
const finalAccessibility = `${latestScans.length} latest per-entry/context scans; ${latestScans.reduce((n, s) => n + s.violations.length, 0)} violation occurrences; ${latestScans.reduce((n, s) => n + s.incomplete.length, 0)} incomplete-rule occurrences. Incomplete rule IDs: ${[...new Set(latestScans.flatMap((s) => s.incomplete.map((i) => i.id)))].join(', ') || 'none'}. Incomplete nodes remain manual-review requirements, not passes.`;
const changedFiles = [
  'apps/api/vayujit_api/ai/schemas.py',
  'apps/api/vayujit_api/ai/service.py',
  'apps/api/vayujit_api/ads/marketing.py',
  'apps/api/vayujit_api/intelligence/portfolio_integration.py',
  'apps/api/tests/test_seller_wp7a4.py',
  'packages/shared/src/index.ts',
  'apps/web/src/app/ai/ai-artifact.component.ts',
  'apps/web/src/app/ai/ai.css',
  'apps/web/src/app/ai/ai-video-bulk.component.ts',
  'apps/web/src/app/ai/ai-image-bulk.component.ts',
  'apps/web/src/app/ai/brand-voice-workspace.component.ts',
  'apps/web/src/app/ai/preset-workspace.component.ts',
  'apps/web/src/app/publishing/destination-form.component.ts',
  'apps/web/src/app/publishing/publishing.css',
  'apps/web/src/app/workflows/workflow-timeline.component.ts',
  'apps/web/src/app/marketplaces/flipkart-workspace.component.ts',
  'apps/web/src/app/marketplaces/meesho-workspace.component.ts',
  'apps/web/src/app/ads/marketing-plan.component.ts',
  'apps/web/src/app/intelligence/trend-intelligence-workspace.component.ts',
  'apps/web/src/app/intelligence/supplier-portfolio-workspace.component.ts',
];
const browserTable =
  '| Run | Result | Entry attempts | Browser versions |\n|---|---|---:|---|\n' +
  reports
    .map(
      (r) =>
        `| ${r.token} | ${r.status === 'RUNNING' ? 'INTERRUPTED_UNFINALIZED (stored RUNNING)' : r.status} | ${r.checks.length} | ${esc(JSON.stringify(r.versions))} |`,
    )
    .join('\n');
await fs.writeFile(
  dir + 'wp7a4-browser-evidence.md',
  `# WP7A-4 — Actual browser evidence\n\n${browserTable}\n\n${total} retained entry attempts, not unique coverage closures. ${scans.length} actual axe scans; ${scans.reduce((n, s) => n + s.violations.length, 0)} violation occurrences and ${scans.reduce((n, s) => n + s.incomplete.length, 0)} incomplete-rule occurrences across all baseline/retest states. Historical violations are not erased when fixed. Automated scans are not a WCAG certification.\n\nEvidence for each attempt is linked in the canonical ledger: viewport/full-page PNG, state JSON, context browser-evidence JSON (safe console/page/network signals), and trace.zip where successfully finalized. The first interrupted run lacks a complete trace; its screenshots/checkpoint remain and cannot replace later passing evidence. Browser requests, API assertions and read-only ORM snapshots are distinct. Only canonical in-process deterministic mock/fake transports were used; no live provider success is asserted.\n\nFinal mobile contexts use 390px touch/mobile emulation; earlier width-only runs are retained as such. Desktop is 1440px, viewport height900. These are installed Chrome/Edge, not physical Android/iOS devices. Bounded focus/Tab/Shift+Tab checks are not an exhaustive keyboard/trap audit.\n\nApplication HEAD and dirty source/build/lock hashes are in tmp/qa-wp7a4/revision-*.json. Exact per-entry latest evidence and earlier failures:\n\n${table}\n`,
);
const rows = defects.application
  .map(
    (d) =>
      `| ${d.id} | ${d.severity} | ${d.entries.join(', ')} | ${esc(d.root)} | ${esc(d.fix)} | ${d.status}; this does not close missing broader workflow coverage |`,
  )
  .join('\n');
await fs.writeFile(
  dir + 'wp7a4-defect-register.md',
  `# WP7A-4 — Defects and scope limits\n\n| ID | Severity | Original entries | Root cause/evidence | Minimal correction | Resolution rule |\n|---|---|---|---|---|---|\n${rows}\n\n## Remaining workflow gaps\n\n${defects.workflow_gaps.map((d) => `- ${d.id} (${d.severity}; ${d.entries.join(', ')}): ${d.finding} ${d.disposition}`).join('\n')}\n\n## Harness/environment findings (not automatically application defects)\n\n${defects.harness.map((d) => `- ${d.id}: ${d.finding} ${d.fix}`).join('\n')}\n\nA new maintenance GET502 in the 346ac65c280b5d93 Edge1440 context was observed during Brand Voice work. It is retained as a transport/runtime failure, not falsely attributed to Brand Voice persistence or used to close the historical Ads502. No unrelated container was restarted.\n\nThe budget defect persisted blocked local plans only; no real spend or provider call occurred. Explicit allocations remain human-entered, and blank unknowns are omitted. The existing validator is reused; no marketplace fee schedule or new financial authority is invented.\n\n${table}\n`,
);
await fs.writeFile(
  dir + 'wp7a4-coverage-closure.md',
  `# WP7A-4 — Coverage closure\n\n**WP7A ${gate.status}. Application certification remains INCOMPLETE.**\n\nExactly48 original outstanding entries reconciled; L-11 remains its prior scoped closure and is not counted anew. ${ledger.counts.PASS} newly closed, ${ledger.counts.FAIL} failed, ${ledger.counts.BLOCKED} blocked, ${ledger.counts.PARTIAL} partial, ${ledger.counts.NOT_TESTED} untested, ${ledger.counts.NOT_SUPPORTED} unsupported exclusions. Partial evidence is never PASS. All48 were attempted; required sub-scenarios listed below remain incomplete where applicable.\n\n## Regression evidence\n\n${Object.entries(
    regressions,
  )
    .map(([k, v]) => `- ${k}: ${v.status}; ${v.evidence}`)
    .join(
      '\n',
    )}\n\n## Database, source and environment integrity\n\nRead-only final audit: ${cleanup.database_absence_status}; ${cleanup.databases.length} task-owned database identities. Historical report hashes unchanged: ${cleanup.historical_baseline_unchanged}. Protected secret matches: ${cleanup.extended_secret_scan?.matches}; trace CRC/secret checks: ${cleanup.extended_secret_scan?.traces}. Docker preservation status: ${cleanup.docker_preservation?.status}; preserve its exact historical runtime timestamp discrepancy, rather than claiming strict historical equality. Detailed proof: tmp/qa-wp7a4-final-audit.json. No permanent/golden database, real provider, public deployment, external publishing, supplier contact, procurement/payment or marketplace mutation was authorized or performed. Backup remains parked; no branch/commit/push.\n\n## Complete original-ID ledger\n\n${table}\n\n## Reproduction and safe resumption\n\n\`powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a4.ps1 -Action Browser\`\n\nFor exact selected-ID replay set QA_WP7A4_IDS to the comma-separated original IDs before this command; four contexts remain required. Backend: same runner -Action Backend; focused post-budget marketing validation: -Action BackendMarketing. QA: node --test qa/unit/*.test.mjs and apps/api/.venv/Scripts/python.exe -m pytest qa/unit -q. Independent audit: apps/api/.venv/Scripts/python.exe -m qa.wp7a4_final_audit. All new DB runs must use the existing attested protected QA profile and a new signed token; never reuse an absent DB, bypass a guard, or generalize exact recovery approval.\n\nThe live checkpoint retains completed IDs, remaining closure IDs and fixture identities. Interrupted attempts and scope gaps are not erased. This work stops at WP7A-4; no WP7B/C/WP8 or application PASS.\n`,
);
await fs.appendFile(
  dir + 'wp7a4-browser-evidence.md',
  `\n## Latest accessibility evidence\n\n${finalAccessibility}\n\nThe first run's RUNNING report is an interrupted, unfinalized historical artifact, not an active test. Its execution record reports failure and cleanup. Run 412436d33a219d5f retains its original CLEANUP_BLOCKED result; the separately approved exact guarded recovery and the independent final absence audit establish its later disposition. Neither historical result was rewritten.\n\nFinal two-entry replay: 691dde19ec6337de, eight actual PASS attempts, Chrome156.0.8078.76 and Edge156.0.4314.50. Mobile destination edits used normal pointer clicks, not force-click or keyboard substitution. Its viewport and full-page screenshots preserve the contained form and saved value. Bulk-image checks include a canonical missing-source blocked preview, valid queue, injected local failure, Retry, deterministic completion and reload. No real provider certification is inferred.\n`,
);
await fs.appendFile(
  dir + 'wp7a4-browser-evidence.md',
  `\n## Attempt counts versus closure counts\n\nAll retained baseline/interrupted/retest attempts: ${JSON.stringify(historicalAttempts)}; total ${total}. These are not unique tests or final failures. Latest per-entry/context outcomes: ${JSON.stringify(latestAttemptCounts)} across 48 IDs by four contexts. Only all-four-context functional closure contributes to the ${ledger.counts.PASS} closed IDs.\n`,
);
await fs.appendFile(
  dir + 'wp7a4-coverage-closure.md',
  `\n## Changed implementation files\n\n${changedFiles.map((f) => `- \`${f}\``).join('\n')}\n\nFocused Angular regressions are in ai-wp7a4.spec.ts, ai-wp7a3.spec.ts, ai-image-bulk.component.spec.ts, marketing-plan.component.spec.ts, the existing Flipkart/Meesho workspace specs, and trend-intelligence-workspace.component.spec.ts. QA foundation changes are the wp7a4-* modules, wp7a4_fixture.py, wp7a4_final_audit.py, five wp7a4 unit-test modules and scripts/test-seller-wp7a4.ps1. Shared harness extensions are in safety.mjs, server.mjs, seller-browser-session.mjs, seller-browser-explore.mjs, wp7-run.mjs, fixture_server.py, wp7a_fixture.py, wp7a2_fixture.py, wp7a3_fixture.py and wp4_final_audit.py. Other dirty-worktree edits are pre-existing and are not claimed as this package. No migration or new business authority was introduced.\n\n## Final accessibility and remaining risks\n\n${finalAccessibility}\n\nThe 16 partial IDs are required local evidence gaps, not approved exclusions or claims that live authorization prevents their execution. Three documented product gaps (activity-specific Video route, durable bulk-Video controls and complete SEO management UI) are retained separately. Unexecuted local permutations require further bounded work inside this same workstream; test totals do not establish them. The historical Ads502, unattributed PostgreSQL runtime timestamp discrepancy, unrelated Ads-router typing debt, incomplete/manual accessibility checks, financial-history/reconciliation limitations and parked backup certification remain open. Focused changed-module checks passed; they do not certify repository-wide typing or operational live readiness.\n`,
);
await fs.appendFile(
  dir + 'wp7a4-coverage-closure.md',
  `\n## Independent cleanup proof and audit caveat\n\nOverall audit classification: ${cleanup.status}. The audit deliberately exits nonzero for the preserved historical Docker timestamp drift; only its database-absence subcheck is PASS. The original container's identity/image/mount/network structure remains unchanged. This does not establish who caused its old StartedAt/FinishedAt difference. No unrelated resource was restarted or removed.\n\n| Exact task token | Signed lifecycle state | Database independently absent | Guarded recovery recorded |\n|---|---|---|---|\n${cleanup.databases.map((d) => `| ${d.token} | ${d.state} | ${d.absent} | ${d.guarded_recovery} |`).join('\n')}\n`,
);
await fs.writeFile(
  dir + 'wp7-journey-coverage-matrix-wp7a4-addendum.md',
  `# Canonical WP7 coverage addendum — WP7A-4\n\nAdditive evidence only; original matrix/addenda and historical caveats remain unchanged. Source: wp7a3-required-coverage.json minus its already closed L-11. Gate: ${gate.status}.\n\n${table}\n\nSee wp7a4-browser-evidence.md, wp7a4-defect-register.md, wp7a4-coverage-closure.md and the machine-readable ledger/gate. No whole-application certification is inferred.\n`,
);
console.log(
  JSON.stringify({
    required: 48,
    counts: ledger.counts,
    attempts: total,
    scans: scans.length,
    gate: gate.status,
  }),
);
