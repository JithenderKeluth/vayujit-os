import fs from 'node:fs/promises';
import { archiveQaReports } from './archive-reports.mjs';
import { writePhase3Report } from './phase3-report.mjs';
import { phase3bResolvedIds, verifyPhase3bEvidence } from './phase3b-resolution.mjs';

const token = process.argv[process.argv.indexOf('--token') + 1];
const evidence = await verifyPhase3bEvidence(token);
const report = JSON.parse(await fs.readFile('docs/qa/phase-3-report.json', 'utf8'));
const ids = phase3bResolvedIds(report, evidence);
if (ids.length !== 8) throw new Error('QA_PHASE3B_REQUIRED_RETESTS_NOT_VERIFIED');
await archiveQaReports();
const reviewed = JSON.parse(await fs.readFile('docs/qa/phase-3-reviewed-findings.json', 'utf8'));
const ledger = {
  generated_at: new Date().toISOString(),
  classification: 'QA_PHASE_3B_BOUNDED_GATES_VALIDATED_APPLICATION_INCOMPLETE',
  targeted_evidence: evidence,
  resolutions: ids.map((id) => ({
    id,
    status: 'RESOLVED',
    retest_status: 'PASS',
    scope:
      id === 'QA-UX-NAV-CURRENT-001'
        ? 'Low-risk navigation recommendation'
        : id === 'QA-P3-SOURCE-001' || id === 'QA-P3-UX-001'
          ? 'Phase 3B correctness'
          : 'Phase 3A revalidation against current source',
    historical_finding:
      reviewed.find((f) => f.id === id) || report.inherited_open_findings.find((f) => f.id === id),
  })),
  retained: reviewed.filter((f) => !ids.includes(f.id)).map((f) => f.id),
  accessibility:
    'Manual tasks remain open unless separately reviewed; browser success is not complete WCAG compliance.',
};
await fs.writeFile('docs/qa/phase-3b-resolution.json', JSON.stringify(ledger, null, 2));
await writePhase3Report(report);
const phase2 = JSON.parse(await fs.readFile('docs/qa/phase-2-report.json', 'utf8'));
const phase1 = JSON.parse(await fs.readFile('docs/qa/phase-1-retest-report.json', 'utf8'));
const assessment = JSON.parse(await fs.readFile('docs/qa/phase-3b-assessment.json', 'utf8'));
await fs.writeFile(
  'docs/qa/phase-3b-report.json',
  JSON.stringify(
    {
      generated_at: ledger.generated_at,
      classification: ledger.classification,
      phase3: { ...report.executive_summary, status: report.status, cleanup: report.cleanup },
      phase2: { ...phase2.executive_summary, status: phase2.status, cleanup: phase2.cleanup },
      phase1: { ...phase1.executive_summary, status: phase1.status, cleanup: phase1.cleanup },
      targeted_evidence: evidence,
      resolutions: ledger.resolutions,
      retained: ledger.retained,
      assessment,
      full_application_certification: 'INCOMPLETE',
    },
    null,
    2,
  ),
);
console.log(JSON.stringify({ classification: ledger.classification, resolved: ids, evidence }));
