// Mechanical redaction only: preserve outcomes and failure identity, not headers.
import fs from 'node:fs/promises';
import path from 'node:path';
const root = 'tmp/qa-seller-browser';
const rows = [];
for (const token of await fs.readdir(root)) {
  if (!/^[a-f0-9]{16}$/.test(token)) continue;
  const p = path.join(root, token, 'wp7a2-browser.json');
  let v;
  try {
    v = JSON.parse(await fs.readFile(p, 'utf8'));
  } catch {
    continue;
  }
  if (v.token !== token) throw Error('REDACTION_SCOPE_MISMATCH');
  let count = 0;
  for (const check of v.checks) {
    if (check.safe_error?.includes('\n')) {
      check.safe_error = check.safe_error.split('\n')[0].slice(0, 300);
      count++;
    }
  }
  if (count) {
    await fs.writeFile(p, JSON.stringify(v, null, 2));
    rows.push({
      token,
      diagnostics_redacted: count,
      outcomes_preserved: true,
      raw_copy_retained: false,
    });
  }
}
await fs.writeFile('tmp/qa-wp7a2/redaction.json', JSON.stringify(rows, null, 2));
console.log(JSON.stringify({ runs_sanitized: rows.length }));
