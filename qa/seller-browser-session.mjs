// Mission-specific owned runtime. Never changes historical QA reports.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import net from 'node:net';
import { spawn } from 'node:child_process';
import { serve } from './server.mjs';
import { cleanupWaitMs } from './safety.mjs';
import {startupPolicy,safeStartupDiagnostic} from './wp7br1-startup.mjs';

const cleanupDeadline = cleanupWaitMs(process.env.QA_DATABASE_DROP_TIMEOUT_MS);

if (!process.env.QA_DATABASE_ADMIN_URL || !process.env.QA_POSTGRES_INSTANCE_MANIFEST)
  throw new Error('APPROVED_QA_INSTANCE_REQUIRED');
const token = crypto.randomBytes(8).toString('hex');
const folder = path.resolve('tmp/qa-seller-browser', token);
await fs.mkdir(folder, { recursive: true });
if (['WP5', 'WP6', 'WP6A', 'WP6B', 'WP7A', 'WP7A2', 'WP7A3', 'WP7A4', 'WP7A5', 'WP7A6', 'WP7A7'].includes(process.env.QA_BROWSER_PHASE))
  await fs.writeFile(
    path.join(folder, `${process.env.QA_BROWSER_PHASE.toLowerCase()}-session.json`),
    JSON.stringify({ token, synthetic: true, package: process.env.QA_BROWSER_PHASE }),
  );
async function freePort() {
  const s = net.createServer();
  await new Promise((r) => s.listen(0, '127.0.0.1', r));
  const port = s.address().port;
  await new Promise((r) => s.close(r));
  return port;
}
const apiPort = await freePort();
const webPort = await freePort();
const origin = `http://127.0.0.1:${webPort}`;
const child = spawn(
  process.env.QA_PYTHON || path.resolve('apps/api/.venv/Scripts/python.exe'),
  [
    '-m',
    'qa.fixture_server',
    '--port',
    String(apiPort),
    '--output',
    folder,
    '--token',
    token,
    ...(process.env.QA_MIGRATE === '1' ? ['--migrate'] : []),
  ],
  {
    env: {
      ...process.env,
      QA_PHASE: '2',
      QA_ORIGIN: origin,
      PYTHONPATH: [process.cwd(), path.resolve('apps/api')].join(path.delimiter),
    },
    windowsHide: true,
    stdio: ['pipe', 'pipe', 'pipe'],
  },
);
let ended = false;
let diagnosticBytes = 0;
let safeDiagnosticBuffer='';
child.stdout.on('data', (d) => (diagnosticBytes += d.length));
child.stderr.on('data', (d) => {diagnosticBytes += d.length;if(process.env.QA_WORK_PACKAGE==='WP7BR1' && safeDiagnosticBuffer.length<65536)safeDiagnosticBuffer+=d;});
child.on('error', () => {
  ended = true;
});
const exit = new Promise((r) =>
  child.once('exit', (code) => {
    ended = true;
    r(code);
  }),
);
const delay = (ms) => new Promise((r) => setTimeout(r, ms));
let web;
const result = {
  token,
  origin,
  folder,
  status: 'STARTING',
  synthetic: true,
  qa_phase: ['WP6', 'WP6A', 'WP6B', 'WP7A', 'WP7A2', 'WP7A3', 'WP7A4', 'WP7A5', 'WP7A6', 'WP7A7'].includes(process.env.QA_BROWSER_PHASE)
    ? process.env.QA_BROWSER_PHASE
    : '4',
  database_scope: `vayujit_qa${token}_test`,
  schema:
    process.env.QA_MIGRATE === '1' ? 'ALEMBIC_HEAD' : 'ORM_METADATA_NOT_MIGRATION_CERTIFICATION',
};
try {
  let ready = false;
  const policy=startupPolicy(process.env.QA_WORK_PACKAGE),startupBegan=Date.now();
  let lastStatus=null,probes=0;
  for (let n = 0; !ended && (policy.deadlineMs?Date.now()-startupBegan<policy.deadlineMs:n<300); n++) {
    try {
      probes++;
      const r = await fetch(`http://127.0.0.1:${apiPort}/__qa/witness`, {
        signal: AbortSignal.timeout(policy.probeMs),
      });
      lastStatus=r.status;
      const w = await r.json();
      if (r.ok && w.token === token && w.disposable) {
        ready = true;
        break;
      }
    } catch {
      /* Only poll this owned child. Never persist raw output. */
    }
    await delay(400);
  }
  if(process.env.QA_WORK_PACKAGE==='WP7BR1')result.startup={elapsed_ms:Date.now()-startupBegan,deadline_ms:policy.deadlineMs,probe_timeout_ms:policy.probeMs,probes,last_status:lastStatus,...safeStartupDiagnostic(safeDiagnosticBuffer)};
  if (!ready) throw new Error('OWNED_QA_RUNTIME_NOT_READY');
  web = await serve(
    webPort,
    apiPort,
    ['WP5', 'WP6', 'WP6A', 'WP6B', 'WP7A', 'WP7A2', 'WP7A3', 'WP7A4', 'WP7A5', 'WP7A6', 'WP7A7'].includes(process.env.QA_BROWSER_PHASE)
      ? process.env.QA_BROWSER_PHASE
      : '4',
  );
  result.status = 'READY';
  await fs.writeFile(path.join(folder, 'session.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
  // Local explicit stop marker; no permanent service or background task created.
  while (
    !ended &&
    !(await fs
      .access(path.join(folder, 'stop.request'))
      .then(() => true)
      .catch(() => false))
  )
    await delay(500);
} catch (error) {
  result.status = 'BLOCKED';
  result.safe_error = ['OWNED_QA_RUNTIME_NOT_READY'].includes(error.message)
    ? error.message
    : 'QA_SESSION_FAILED';
} finally {
  if (web) await new Promise((r) => web.close(r));
  child.stdin.end();
  result.cleanup_wait_ms = cleanupDeadline;
  let cleanupTimer;
  try {
    result.child_exit = await Promise.race([
      exit,
      new Promise((resolve) => {
        cleanupTimer = setTimeout(() => resolve('TIMEOUT'), cleanupDeadline);
      }),
    ]);
  } finally {
    globalThis.clearTimeout(cleanupTimer);
  }
  if (result.child_exit === 'TIMEOUT') child.kill(); // Only the child owned above.
  result.cleanup = await fs
    .readFile(path.join(folder, 'cleanup.json'), 'utf8')
    .then(JSON.parse)
    .catch(() => null);
  result.diagnostic_bytes = diagnosticBytes;
  result.status =
    result.child_exit === 0 && result.cleanup?.database_absent ? 'CLEANED' : 'CLEANUP_BLOCKED';
  await fs.writeFile(path.join(folder, 'session-final.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
}
