// Narrow diagnostic: fresh marked QA installation only; no business mutations.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import net from 'node:net';
import { spawn } from 'node:child_process';

if (!process.env.QA_DATABASE_ADMIN_URL) throw new Error('QA_ADMIN_REQUIRED');
const token = crypto.randomBytes(8).toString('hex');
const folder = path.resolve('tmp/qa-agent', token);
await fs.mkdir(folder, { recursive: true });
const socket = net.createServer();
await new Promise((resolve) => socket.listen(0, '127.0.0.1', resolve));
const port = socket.address().port;
await new Promise((resolve) => socket.close(resolve));
const child = spawn(
  process.env.QA_PYTHON || path.resolve('apps/api/.venv/Scripts/python.exe'),
  ['qa/fixture_server.py', '--port', String(port), '--output', folder, '--token', token],
  {
    env: { ...process.env, QA_PHASE: '3', QA_ORIGIN: 'http://127.0.0.1:4200' },
    windowsHide: true,
    stdio: ['pipe', 'pipe', 'pipe'],
  },
);
let ended = false;
let diagnosticBytes = 0;
child.stdout.on('data', (bytes) => (diagnosticBytes += bytes.length));
child.stderr.on('data', (bytes) => (diagnosticBytes += bytes.length));
const exit = new Promise((resolve) =>
  child.once('exit', (code) => {
    ended = true;
    resolve(code);
  }),
);
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const result = { token, status: 'NOT_EXECUTED' };
async function witness(previous, limit) {
  const started = Date.now();
  while (!ended && Date.now() - started < limit) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/__qa/witness`, {
        signal: AbortSignal.timeout(2000),
      });
      const value = await response.json();
      if (response.ok && value.disposable && value.token === token && value.process_id !== previous)
        return { process: value.process_id, elapsed_ms: Date.now() - started };
    } catch {
      // Owned child only. Never save raw stderr or response text.
    }
    await delay(300);
  }
  throw new Error('QA_OWNED_PROBE_NOT_READY');
}
try {
  result.initial = await witness(null, 90000);
  child.stdin.write(`restart:${token}\n`);
  result.restart = await witness(result.initial.process, 60000);
  result.status = 'PASS_OWNED_PROCESS_RESTART';
} catch (error) {
  result.status = 'BLOCKED';
  result.safe_error = error.message.startsWith('QA_') ? error.message : 'QA_PROBE_FAILED';
} finally {
  child.stdin.end();
  result.child_exit = await Promise.race([exit, delay(45000).then(() => 'TIMEOUT')]);
  if (result.child_exit === 'TIMEOUT') child.kill(); // Exact owned fixture only.
  result.cleanup = await fs
    .readFile(path.join(folder, 'cleanup.json'), 'utf8')
    .then(JSON.parse)
    .catch(() => null);
  result.diagnostic_bytes = diagnosticBytes;
  await fs.writeFile(
    path.join(folder, 'owned-runtime-probe.json'),
    JSON.stringify(result, null, 2),
  );
}
console.log(JSON.stringify(result));
if (result.status !== 'PASS_OWNED_PROCESS_RESTART' || result.child_exit !== 0) process.exitCode = 1;
