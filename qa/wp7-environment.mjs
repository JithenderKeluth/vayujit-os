// Exact tested source/dependency fingerprints; never enumerate .env or secret stores.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const hash = (b) => crypto.createHash('sha256').update(b).digest('hex');
const files = [];
async function walk(folder) {
  for (const e of await fs.readdir(folder, { withFileTypes: true })) {
    const f = path.posix.join(folder, e.name);
    if (e.isDirectory()) {
      if (!['__pycache__', 'node_modules', '.venv'].includes(e.name)) await walk(f);
    } else if (/\.(py|ts|css|html|mjs|json)$/.test(f))
      files.push({ file: f, sha256: hash(await fs.readFile(f)) });
  }
}
for (const folder of [
  'apps/web/src',
  'apps/api/vayujit_api',
  'apps/api/alembic',
  'apps/api/tests',
  'qa',
  'dist/apps/web/browser',
])
  await walk(folder);
files.sort((a, b) => a.file.localeCompare(b.file));
const dependencies = {};
for (const name of ['@angular/core', 'typescript', '@playwright/test', 'axe-core'])
  dependencies[name] = JSON.parse(
    await fs.readFile(
      require.resolve(`${name}/package.json`, { paths: [path.resolve('apps/web'), process.cwd()] }),
      'utf8',
    ),
  ).version;
const result = {
  date: new Date().toISOString(),
  git_base: execFileSync(
    'git',
    ['-c', 'safe.directory=' + process.cwd().replaceAll('\\', '/'), 'rev-parse', 'HEAD'],
    { encoding: 'utf8' },
  ).trim(),
  dirty_worktree: true,
  node: process.version,
  powershell: execFileSync(
    'powershell.exe',
    ['-NoProfile', '-NonInteractive', '-Command', '$PSVersionTable.PSVersion.ToString()'],
    { encoding: 'utf8' },
  ).trim(),
  python: execFileSync(path.resolve('apps/api/.venv/Scripts/python.exe'), ['--version'], {
    encoding: 'utf8',
  }).trim(),
  dependencies,
  lock_sha256: hash(await fs.readFile('package-lock.json')),
  source_and_build_tree_sha256: hash(JSON.stringify(files)),
  files,
  configuration: {
    database: 'APPROVED_SIGNED_DISPOSABLE_ONLY',
    migrations: 'ALEMBIC_HEAD',
    external_egress: 'DENIED',
    providers: 'LOCAL_FIXTURE_ONLY',
    backup: 'PARKED',
    permanent_database: 'NOT_ACCESSED',
  },
};
await fs.mkdir('tmp/qa-wp7', { recursive: true });
await fs.writeFile('tmp/qa-wp7/environment.json', JSON.stringify(result, null, 2));
console.log(
  JSON.stringify({
    git_base: result.git_base,
    files: files.length,
    node: result.node,
    python: result.python,
    dependencies,
  }),
);
