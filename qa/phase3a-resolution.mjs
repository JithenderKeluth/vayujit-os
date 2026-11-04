import fs from 'node:fs/promises';
import crypto from 'node:crypto';

export const originalTests = {
  'qa/phase3_api.py': 'fb57f64c32519ac17af2a9bc5d482da554249b2c560ef6672018bd38ba76150f',
  'qa/tests/phase3.spec.mjs': 'd862ddf17f9c1806bdd53bd1b6969411b5dff89ec8660db574768b87f0240e7c',
};
export const browserTimingCorrection = {
  baseline_sha256: '986105d28a17ca0df223766f3e09dacb124bdd7cb3ce7e981947ad87d83965d5',
  retested_sha256: originalTests['qa/tests/phase3.spec.mjs'],
  change:
    'Only the QA-owned restart request gets timeout 45000 plus an explanatory comment. No assertion, locator, input or expected business behavior changed.',
  measured_restart_ms: 18871,
  evidence: 'tmp/qa-agent/974f9e6a0ee5313a/owned-runtime-probe.json',
};
export const remediationCases = {
  'QA-P3-FIN-001': 'test_08_unknown_cost_revision_does_not_resurrect_old_known_cost',
  'QA-P3-IDEM-001': 'test_05_conflicting_stock_key_is_not_silently_accepted',
  'QA-P3-IDEM-002': 'test_07_conflicting_financial_event_is_rejected',
  'QA-P3-IDEM-003': 'test_13_conflicting_signal_transition_key_rejected',
  'QA-P3-SIGNAL-001': 'test_15_source_changes_rescan_and_signal_resolution',
};
const testedSources = [
  'apps/api/vayujit_api/commerce/financial_router.py',
  'apps/api/vayujit_api/commerce/inventory_router.py',
  'apps/api/vayujit_api/operations/action_center_router.py',
  'apps/api/tests/test_qa_phase3a_remediation.py',
];
const hash = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex');

// Closure is evidence-gated, not inferred from a manually edited finding status.
export function resolvedIds(report, evidence) {
  if (
    !evidence?.verified ||
    report.cleanup?.length !== 2 ||
    new Set(report.cleanup.map((c) => c.database)).size !== 2 ||
    !['desktop', 'mobile'].every((p) => report.cleanup.some((c) => c.project === p)) ||
    !report.cleanup.every(
      (c) =>
        c.status === 'PASS' &&
        c.child_exit === 0 &&
        c.proof?.database_absent === true &&
        c.proof?.database === c.database,
    ) ||
    report.reports?.length !== 2
  )
    return [];
  return Object.entries(remediationCases)
    .filter(([, id]) =>
      report.reports.every((r) => {
        const matches = r.api_results?.tests?.filter((t) => t.id === id) || [];
        return matches.length === 1 && matches[0].status === 'PASS';
      }),
    )
    .map(([id]) => id);
}

export async function verifyTargetedEvidence(token) {
  if (!/^[a-f0-9]{16}$/.test(token || '')) return { verified: false };
  const folder = `tmp/qa-agent/${token}`;
  const xml = await fs.readFile(`${folder}/backend-results.xml`, 'utf8');
  const cleanup = JSON.parse(await fs.readFile(`${folder}/cleanup.json`, 'utf8'));
  const testedSourceHashes = JSON.parse(
    await fs.readFile(`${folder}/tested-source-sha256.json`, 'utf8'),
  );
  const currentSourceHashes = Object.fromEntries(
    await Promise.all(testedSources.map(async (file) => [file, hash(await fs.readFile(file))])),
  );
  const suites = [...xml.matchAll(/<testsuite\s[^>]*>/g)];
  const targetedCases = [...xml.matchAll(/<testcase\s[^>]*>/g)].filter((match) =>
    /classname="[^"]*test_qa_phase3a_remediation"/.test(match[0]),
  );
  const total = Number(suites[0]?.[0].match(/\btests="(\d+)"/)?.[1]);
  const validSuite =
    suites.length === 1 &&
    targetedCases.length === 17 &&
    total >= 17 &&
    ['errors', 'failures', 'skipped'].every((key) =>
      new RegExp(`\\b${key}="0"`).test(suites[0][0]),
    );
  const originals = await Promise.all(
    Object.entries(originalTests).map(
      async ([file, expected]) => hash(await fs.readFile(file)) === expected,
    ),
  );
  const verified =
    validSuite &&
    originals.every(Boolean) &&
    JSON.stringify(currentSourceHashes) === JSON.stringify(testedSourceHashes) &&
    cleanup.status === 'PASS' &&
    cleanup.marker_verified === true &&
    cleanup.database_absent === true &&
    cleanup.database === `vayujit_qa${token}_test`;
  return {
    verified,
    token,
    tests: total,
    targeted_tests: 17,
    junit: `${folder}/backend-results.xml`,
    junit_sha256: hash(xml),
    cleanup: `${folder}/cleanup.json`,
    test_contract_hashes_verified: originals.every(Boolean),
    original_api_tests_unchanged: originals[0],
    browser_timing_correction: browserTimingCorrection,
    tested_source_sha256: testedSourceHashes,
  };
}

export async function verifiedResolutionLedger(report) {
  const raw = await fs.readFile('docs/qa/phase-3a-resolution.json', 'utf8').catch((e) => {
    if (e.code === 'ENOENT') return null;
    throw e;
  });
  if (!raw) return { ids: [], evidence: null };
  const ledger = JSON.parse(raw);
  let evidence;
  try {
    evidence = await verifyTargetedEvidence(ledger.targeted_evidence?.token);
  } catch {
    // Retain open findings when local artifacts have been removed or corrupted.
    return { ids: [], evidence: { verified: false, code: 'QA_TARGETED_ARTIFACTS_UNAVAILABLE' } };
  }
  if (
    evidence.junit_sha256 !== ledger.targeted_evidence?.junit_sha256 ||
    JSON.stringify(evidence.tested_source_sha256) !==
      JSON.stringify(ledger.targeted_evidence?.tested_source_sha256)
  )
    return { ids: [], evidence: { ...evidence, verified: false } };
  return { ids: resolvedIds(report, evidence), evidence };
}
