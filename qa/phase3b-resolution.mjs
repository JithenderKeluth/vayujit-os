import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import { resolvedIds, verifyTargetedEvidence } from './phase3a-resolution.mjs';

export async function verifyPhase3bEvidence(token) {
  const common = await verifyTargetedEvidence(token);
  if (!common.verified) return { verified: false };
  const folder = `tmp/qa-agent/${token}`;
  const xml = await fs.readFile(`${folder}/backend-results.xml`, 'utf8');
  const count = [...xml.matchAll(/<testcase\s[^>]*>/g)].filter((m) =>
    /classname="[^"]*test_qa_phase3b_remediation"/.test(m[0]),
  ).length;
  const hashes = JSON.parse(
    await fs.readFile(`${folder}/tested-phase3b-source-sha256.json`, 'utf8'),
  );
  const required = [
    'apps/api/vayujit_api/commerce/financial_router.py',
    'apps/api/vayujit_api/operations/action_center_router.py',
    'apps/api/tests/test_qa_phase3b_remediation.py',
    'apps/web/src/app/operations/action-center.component.ts',
    'apps/web/src/app/marketplaces/financial-workspace.component.ts',
    'apps/web/src/app/marketplaces/marketplace.service.ts',
    'apps/web/src/app/shared/seller-navigation.component.ts',
    'qa/tests/phase3b.spec.mjs',
  ];
  const match = await Promise.all(
    required.map(
      async (file) =>
        hashes[file] ===
        crypto
          .createHash('sha256')
          .update(await fs.readFile(file))
          .digest('hex'),
    ),
  );
  return {
    ...common,
    verified: count === 16 && match.every(Boolean),
    phase3b_tests: count,
    phase3b_source_sha256: hashes,
  };
}

export function phase3bResolvedIds(report, evidence) {
  const inherited = resolvedIds(report, evidence);
  if (inherited.length !== 5) return [];
  const complete = report.reports.every(
    (r) =>
      r.process_exit_code === 0 &&
      r.tests.length === 9 &&
      r.tests.every((t) => t.status === 'passed') &&
      r.api_results?.process_exit_code === 0 &&
      r.api_results.tests.length === 18 &&
      r.api_results.tests.every((t) => t.status === 'PASS') &&
      ['QA-P3-04', 'QA-P3B-01', 'QA-P3B-02', 'QA-P3B-03'].every(
        (id) => r.tests.filter((t) => t.id === id && t.status === 'passed').length === 1,
      ) &&
      r.api_results?.tests?.filter(
        (t) =>
          t.id === 'test_17_canonical_order_synthetic_provenance_and_state_change' &&
          t.status === 'PASS',
      ).length === 1,
  );
  return complete
    ? [...inherited, 'QA-P3-SOURCE-001', 'QA-P3-UX-001', 'QA-UX-NAV-CURRENT-001']
    : [];
}

export async function verifiedPhase3bLedger(report) {
  try {
    const ledger = JSON.parse(await fs.readFile('docs/qa/phase-3b-resolution.json', 'utf8'));
    const evidence = await verifyPhase3bEvidence(ledger.targeted_evidence?.token);
    if (
      evidence.junit_sha256 !== ledger.targeted_evidence?.junit_sha256 ||
      JSON.stringify(evidence.phase3b_source_sha256) !==
        JSON.stringify(ledger.targeted_evidence?.phase3b_source_sha256)
    )
      return { ids: [], evidence: { verified: false } };
    return { ids: phase3bResolvedIds(report, evidence), evidence };
  } catch {
    return { ids: [], evidence: { verified: false, code: 'QA_PHASE3B_CLOSURE_NOT_VERIFIED' } };
  }
}
