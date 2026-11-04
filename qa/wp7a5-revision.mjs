import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
const files = [];
async function walk(root) {
  for (const entry of await fs.readdir(root, { withFileTypes: true })) {
    const file = path.join(root, entry.name);
    if (entry.isDirectory()) await walk(file);
    else if (entry.isFile() && /\.(ts|py|css|html|js|json)$/.test(file)) files.push(file);
  }
}
for (const root of [
  'apps/web/src',
  'apps/api/vayujit_api',
  'apps/api/tests',
  'qa',
  'dist/apps/web/browser',
])
  await walk(root);
files.push('package-lock.json', 'packages/shared/src/index.ts', 'apps/api/pyproject.toml');
const hashes = [];
for (const file of files.sort())
  hashes.push({
    file: file.replaceAll('\\', '/'),
    sha256: crypto
      .createHash('sha256')
      .update(await fs.readFile(file))
      .digest('hex'),
  });
const head = execFileSync(
  'git',
  ['-c', 'safe.directory=' + process.cwd().replaceAll('\\', '/'), 'rev-parse', 'HEAD'],
  { encoding: 'utf8', windowsHide: true },
).trim();
await fs.writeFile(
  'tmp/qa-wp7a5/revision-' + (process.argv[2] || 'baseline') + '.json',
  JSON.stringify(
    { at: new Date().toISOString(), head, dirty: true, node: process.version, files: hashes },
    null,
    2,
  ),
);
console.log(JSON.stringify({ head, dirty: true, files: hashes.length }));
