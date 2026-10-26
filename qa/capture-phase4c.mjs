import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';

const target = 'docs/qa/phase-4c-baseline.json';
try {
  await fs.access(target);
  throw new Error('QA_AUDIT_BASELINE_ALREADY_EXISTS');
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}
const hashes = {};
async function capture(root, accept) {
  for (const entry of await fs.readdir(root, { withFileTypes: true })) {
    const file = path.posix.join(root, entry.name);
    if (entry.isDirectory() && !['__pycache__', 'node_modules'].includes(entry.name))
      await capture(file, accept);
    else if (entry.isFile() && accept(file))
      hashes[file] = crypto
        .createHash('sha256')
        .update(await fs.readFile(file))
        .digest('hex');
  }
}
await capture('apps/api/vayujit_api', (f) => /\.py$/.test(f));
await capture('apps/web/src', () => true);
await capture('packages', (f) => /\.(ts|css|html|json)$/.test(f));
await capture('docs/qa', (f) => !f.includes('/history/') && !f.includes('phase-4c'));
await fs.writeFile(
  target,
  JSON.stringify(
    {
      captured_at: new Date().toISOString(),
      scope: 'immutable production source and prior QA evidence; no finding status mutation',
      sha256: hashes,
    },
    null,
    2,
  ),
  { flag: 'wx' },
);
console.log(JSON.stringify({ captured: Object.keys(hashes).length }));
