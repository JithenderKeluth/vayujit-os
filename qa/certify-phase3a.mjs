import fs from 'node:fs/promises';
import { archiveQaReports } from './archive-reports.mjs';
import { writePhase3Report } from './phase3-report.mjs';
import {
  remediationCases,
  originalTests,
  resolvedIds,
  verifyTargetedEvidence,
} from './phase3a-resolution.mjs';

const token = process.argv[process.argv.indexOf('--token') + 1];
const evidence = await verifyTargetedEvidence(token);
if (!evidence.verified) throw new Error('QA_PHASE3A_TARGETED_EVIDENCE_NOT_VERIFIED');
const report = JSON.parse(await fs.readFile('docs/qa/phase-3-report.json', 'utf8'));
const ids = resolvedIds(report, evidence);
if (ids.length !== 5) throw new Error('QA_PHASE3A_ORIGINAL_RETEST_NOT_COMPLETE');
const reviewed = JSON.parse(await fs.readFile('docs/qa/phase-3-reviewed-findings.json', 'utf8'));
const fixes = {
  'QA-P3-FIN-001': {
    cause:
      'UNKNOWN rows were removed before latest-applicable revision selection; truthiness also conflated known zero with missing cost.',
    fix: 'Select latest effective revision first, retain UNKNOWN as a blocker in summary and both profitability paths, prevent legacy product fallback from overriding it, record cost IDs in current snapshot lineage.',
  },
  'QA-P3-IDEM-001': {
    cause: 'Stock adjustment replay matched only item/key, not the original movement intent.',
    fix: 'Under the existing inventory row lock compare delta, reason, HUMAN actor and captured expected version before returning the persisted movement; return 409 on conflict.',
  },
  'QA-P3-IDEM-002': {
    cause:
      'Financial event preflight and uniqueness-recovery both returned a source-event match without semantic comparison.',
    fix: 'Use the same normalized event-identity comparison in both paths, including rounded amount, explicit timestamp, references, source, status and payload. Preserve omitted server timestamps and durable unique-key concurrency.',
  },
  'QA-P3-IDEM-003': {
    cause:
      'Signal transition replay ignored signal, target, note and snooze expiry; replay could reapply an old snooze to a later state.',
    fix: 'Compare owner-scoped HUMAN intent and expiry, serialize derivation/transition transactions, return the old transition without changing current state on valid replay.',
  },
  'QA-P3-SIGNAL-001': {
    cause:
      'Scans upserted current matches but never retired recovered stock evidence; stock fingerprints lacked current inventory version.',
    fix: 'Revalidate stock snapshots on scan/read/transition; append SYSTEM STALE history while preserving original evidence; version new stock fingerprints and reject new actions against stale sources. Serialize derived signal transactions without adding inventory locks that invert canonical multi-line order lock order.',
  },
};
await archiveQaReports();
const ledger = {
  generated_at: new Date().toISOString(),
  status: 'BOUNDED_REMEDIATION_VALIDATED_APPLICATION_INCOMPLETE',
  scope:
    'Five explicitly named roots: four P1 and one P2. Excluded synthetic provenance P1 remains open; severity was not relabelled.',
  targeted_evidence: evidence,
  retested_test_contract_sha256: originalTests,
  original_retest: report.cleanup.map((c, index) => ({
    project: c.project,
    database: c.database,
    cleanup: c,
    api_tests: report.reports[index].api_results.tests,
  })),
  resolutions: ids.map((id) => ({
    id,
    priority: reviewed.find((f) => f.id === id).priority,
    status: 'RESOLVED',
    retest_status: 'PASS',
    original_assertion: remediationCases[id],
    ...fixes[id],
    historical_finding: reviewed.find((f) => f.id === id),
  })),
  preserved_open: reviewed.filter((f) => !ids.includes(f.id)).map((f) => f.id),
  exclusions: [
    'Six inherited usability recommendations remain open.',
    'Six original caption occurrences and four financial-screen nodes still require manual accessibility review.',
    'No full application, migration, real-provider or Docker backup certification is inferred.',
  ],
};
await fs.writeFile('docs/qa/phase-3a-resolution.json', JSON.stringify(ledger, null, 2));
await writePhase3Report(report);
const phase1 = JSON.parse(await fs.readFile('docs/qa/phase-1-retest-report.json', 'utf8'));
const phase2 = JSON.parse(await fs.readFile('docs/qa/phase-2-report.json', 'utf8'));
await fs.writeFile(
  'docs/qa/phase-3a-report.json',
  JSON.stringify(
    {
      generated_at: ledger.generated_at,
      classification: ledger.status,
      phase3: { status: report.status, ...report.executive_summary, cleanup: report.cleanup },
      phase2: { status: phase2.status, ...phase2.executive_summary, cleanup: phase2.cleanup },
      phase1: { status: phase1.status, ...phase1.executive_summary, cleanup: phase1.cleanup },
      targeted_evidence: evidence,
      resolved: ids,
      remaining: ledger.preserved_open,
      full_application_certification: 'INCOMPLETE',
      limits: ledger.exclusions,
    },
    null,
    2,
  ),
);
const coverage = await fs.readFile('docs/qa/coverage-matrix.md', 'utf8');
await fs.writeFile(
  'docs/qa/coverage-matrix.md',
  coverage +
    '\n## Phase 3A independently verified remediation\n\n' +
    '| Root | Priority | Original assertion, both installations | Targeted regression | Result |\n| --- | --- | --- | --- | --- |\n' +
    ledger.resolutions
      .map((r) => `| ${r.id} | ${r.priority} | ${r.original_assertion}: PASS | PASS | RESOLVED |`)
      .join('\n') +
    '\n\nThe synthetic-provenance P1, resolved-filter P2, three missing workflows, six usability recommendations and ten manual accessibility occurrences remain open. See [Phase 3A validation](phase-3a-validation.md). This is not comprehensive application certification.\n',
);
console.log(JSON.stringify({ status: ledger.status, resolved: ids, evidence }));
