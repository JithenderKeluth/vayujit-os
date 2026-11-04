// Wait for this exact owned aggregate backend run to finish before further DDL.
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
const token = process.argv[2];
if (!/^[a-f0-9]{16}$/.test(token || '')) throw Error('EXACT_BACKEND_TOKEN_REQUIRED');
const file = path.join('tmp/qa-wp7-backend', token, 'runner.json');
while (
  !(await fs
    .access(file)
    .then(() => true)
    .catch(() => false))
)
  await new Promise((r) => setTimeout(r, 2000));
const backend = JSON.parse(await fs.readFile(file, 'utf8'));
const cleanup = await fs
  .readFile(path.join(path.dirname(file), 'cleanup.json'), 'utf8')
  .then(JSON.parse)
  .catch(() => null);
if (backend.token !== token || !cleanup?.database_absent)
  throw Error('BACKEND_CLEANUP_REQUIRED_BEFORE_CONTINUATION');
async function run(cmd, args) {
  const p = spawn(cmd, args, { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  let bytes = 0;
  p.stdout.on('data', (d) => (bytes += d.length));
  p.stderr.on('data', (d) => (bytes += d.length));
  const code = await new Promise((r) => p.on('exit', r));
  return { exit_code: code, output_bytes: bytes, raw_output_persisted: false };
}
const recovery = await run(path.resolve('apps/api/.venv/Scripts/python.exe'), [
  '-m',
  'qa.wp7_recover',
  '9cce2e3c4fc034f5',
  '4963364d9460948d',
]);
await fs.writeFile(
  'tmp/qa-wp7/continuation.json',
  JSON.stringify({ backend: token, recovery }, null, 2),
);
console.log(JSON.stringify({ stage: 'QUIESCENT_RECOVERY', ...recovery }));
if (recovery.exit_code !== 0) process.exitCode = 1;
else {
  const r = await run(process.execPath, [
    'qa/wp7-run.mjs',
    'wp3',
    'wp4',
    'wp5',
    'wp6',
    'wp6a',
    'wp6b',
    'layout',
  ]);
  await fs.writeFile(
    'tmp/qa-wp7/continuation.json',
    JSON.stringify({ backend: token, recovery, browsers: r }, null, 2),
  );
  console.log(JSON.stringify({ stage: 'BROWSER_CONTINUATION', ...r }));
  process.exitCode = r.exit_code;
}
