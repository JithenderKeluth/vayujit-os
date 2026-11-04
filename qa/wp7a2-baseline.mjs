import fs from 'node:fs/promises';
import crypto from 'node:crypto';
const files = [
  'wp7a-coverage-closure.md',
  'wp7a-browser-evidence.md',
  'wp7a-defect-resolution.md',
  'wp7a-gate.json',
  'wp7-journey-coverage-matrix.md',
  'wp7-defect-register.md',
  'wp7-journey-coverage-matrix-wp7a-addendum.md',
];
const rows = [];
for (const file of files) {
  const p = 'docs/qa/seller-experience/' + file;
  rows.push({
    file: p,
    sha256: crypto
      .createHash('sha256')
      .update(await fs.readFile(p))
      .digest('hex'),
  });
}
const old = JSON.parse(await fs.readFile('docs/qa/seller-experience/wp7a-gate.json', 'utf8'));
await fs.mkdir('tmp/qa-wp7a2', { recursive: true });
await fs
  .writeFile(
    'tmp/qa-wp7a2/baseline.json',
    JSON.stringify(
      {
        files: rows,
        previous_gate: old.status,
        existing_matrix_ids: ['B', 'L'],
        four_remaining: old.remaining_critical_coverage,
        additional_wp7_scope:
          'Original L also lists other AI/image/content/campaign artifact preparation/review gaps; these are retained and not silently certified by the four scenarios.',
      },
      null,
      2,
    ),
    { flag: 'wx' },
  )
  .catch((e) => {
    if (e.code !== 'EEXIST') throw e;
  });
console.log(JSON.stringify({ historical_files: rows.length, original_gate_unchanged: true }));
