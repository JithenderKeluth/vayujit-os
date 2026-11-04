import fs from 'node:fs/promises';
import crypto from 'node:crypto';
const root = 'docs/qa/seller-experience/';
const files = [
  'wp7-certification-report.md',
  'wp7-journey-coverage-matrix.md',
  'wp7-defect-register.md',
  'wp7-certification-gate.json',
  'wp7-browser-evidence.md',
  'wp7-accessibility-evidence.md',
  'wp6a-schema-remediation.md',
  'wp6a-browser-retest.md',
  'wp6a-resolution.json',
  'wp6b-remediation.md',
  'wp6b-browser-retest.md',
  'wp6b-quality-gate.json',
];
const hashes = [];
let gate;
for (const name of files) {
  const bytes = await fs.readFile(root + name);
  hashes.push({
    file: root + name,
    sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
  });
  if (name === 'wp7-certification-gate.json') gate = JSON.parse(bytes);
}
const result = {
  date: new Date().toISOString(),
  files: hashes,
  parent_finding: 'SE-WP7-COVERAGE-001',
  original_classification: gate.application_certification,
  targeted_matrix_ids: gate.journeys.filter((j) => 'BGHL'.includes(j.id)),
  original_findings: gate.new_findings,
  remaining_risks: gate.decision_inputs.lower_severity_conditions,
  original_cleanup: gate.cleanup.status,
  original_application_certification_unchanged: true,
};
await fs.mkdir('tmp/qa-wp7a', { recursive: true });
try {
  await fs.writeFile('tmp/qa-wp7a/baseline.json', JSON.stringify(result, null, 2), { flag: 'wx' });
} catch (e) {
  if (e.code !== 'EEXIST') throw e;
}
console.log(
  JSON.stringify({
    targeted_matrix_ids: result.targeted_matrix_ids.map((j) => ({
      id: j.id,
      previous_status: j.status,
    })),
    historical_files: hashes.length,
  }),
);
