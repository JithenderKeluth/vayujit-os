import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { wp7aPath, safeWp7aPayload } from './wp7a-safety.mjs';
import { wp7a3Path, safeWp7a3Payload } from './wp7a3-safety.mjs';
import { wp7a4Path, safeWp7a4Payload } from './wp7a4-safety.mjs';
import { wp7a5Path, safeWp7a5Payload } from './wp7a5-safety.mjs';
import { wp7a6Path, safeWp7a6Payload } from './wp7a6-safety.mjs';
import { wp7a7Path, safeWp7a7Payload } from './wp7a7-safety.mjs';
import { wp7bPreviewPath, safeWp7bPreview } from './wp7b-safety.mjs';
import { wp7a2Path, safeWp7a2Payload } from './wp7a2-safety.mjs';
import {
  allowRequest,
  journeyContextPath,
  safeJourneyContextPayload,
  safeWp5DestinationPayload,
  safeWp6ActivationPayload,
  safeWp6aPayload,
  wp6aPreparationPath,
} from './safety.mjs';

// Allowlisted transport metadata only; never retain raw errors, URLs or arguments.
export function proxyFailureDiagnostic(error) {
  const code = ['ECONNRESET','ECONNREFUSED','ETIMEDOUT','EPIPE','ENOTFOUND'].includes(error?.code) ? error.code : 'UNCLASSIFIED_TRANSPORT';
  return {origin:'qa_reverse_proxy',classification:'upstream_transport',code,status:502,raw_output_persisted:false};
}

// Serve the actual production Angular build; proxy only to this run's API.
export async function serve(port, apiPort, phase = '1', control = null) {
  const seventh = phase === 'WP7A7';
  const assessment = seventh && ['WP7B','WP7BR1'].includes(process.env.QA_WORK_PACKAGE);
  const sixth = seventh || phase === 'WP7A6';
  const fifth = sixth || phase === 'WP7A5';
  const fourth = fifth || phase === 'WP7A4';
  const third = fourth || phase === 'WP7A3';
  const extended = third || phase === 'WP7A2';
  if (extended) phase = 'WP7A';
  // WP6B reuses exactly WP6A's local-only preparation policy, not live execution.
  if (phase === 'WP6B') phase = 'WP6A';
  const root = path.resolve('dist/apps/web/browser');
  await fs.access(path.join(root, 'index.html'));
  const origin = `http://127.0.0.1:${port}`;
  const mime = {
    '.html': 'text/html',
    '.js': 'text/javascript',
    '.css': 'text/css',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
    '.woff2': 'font/woff2',
  };
  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, origin);
      if (!allowRequest(url.href, req.method, origin, assessment ? 'WP7B' : seventh ? 'WP7A7' : sixth ? 'WP7A6' : fifth ? 'WP7A5' : fourth ? 'WP7A4' : third ? 'WP7A3' : extended ? 'WP7A2' : phase)) {
        res.writeHead(403).end();
        return;
      }
      if (url.pathname === '/__qa/restart') {
        // QA-only owned-process control. No production endpoint or auth bypass.
        if (
          phase !== '3' ||
          req.method !== 'POST' ||
          !control ||
          req.headers['x-qa-token'] !== control.token
        ) {
          res.writeHead(403).end();
          return;
        }
        const auth = await fetch(`http://127.0.0.1:${apiPort}/api/v1/auth/me`, {
          headers: { cookie: req.headers.cookie || '' },
        });
        if (!auth.ok) {
          res.writeHead(401).end();
          return;
        }
        try {
          const proof = await control.restart();
          res.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify(proof));
        } catch {
          res.writeHead(503).end();
        }
        return;
      }
      if (
        url.pathname.startsWith('/api/') ||
        url.pathname.startsWith('/health') ||
        url.pathname === '/__qa/witness' || url.pathname.startsWith('/__qa/wp7a/') || (extended && (url.pathname.startsWith('/__qa/wp7a2/') || (third && url.pathname.startsWith('/__qa/wp7a3/')))) || (fourth && url.pathname.startsWith('/__qa/wp7a4/')) || (sixth && url.pathname.startsWith('/__qa/wp7a6/')) || (seventh && url.pathname.startsWith('/__qa/wp7a7/'))
      ) {
        let buffered;
        if (
          ((assessment && wp7bPreviewPath(url.pathname,req.method)) || (seventh && wp7a7Path(url.pathname,req.method)) || (sixth && wp7a6Path(url.pathname,req.method)) || (fifth && wp7a5Path(url.pathname,req.method)) || (fourth && wp7a4Path(url.pathname,req.method)) || (third && wp7a3Path(url.pathname,req.method)) || (extended && wp7a2Path(url.pathname,req.method)) || (phase === 'WP7A' && (wp7aPath(url.pathname, req.method) || url.pathname.endsWith('/runs'))) || url.pathname === '/api/v1/intelligence/suppliers/research' ||
            /^\/api\/v1\/intelligence\/business-agent\/goals\/[a-f0-9-]+\/runs$/.test(
              url.pathname,
            ) ||
            (['4', 'WP6', 'WP6A', 'WP7A'].includes(phase) && journeyContextPath.test(url.pathname)) ||
            (['3', '4', 'WP5', 'WP6', 'WP6A', 'WP7A'].includes(phase) &&
              url.pathname === '/api/v1/marketplaces/accounts') ||
            (['WP6','WP6A','WP7A'].includes(phase) && /^\/api\/v1\/products\/[a-f0-9-]+\/activate$/.test(url.pathname)) ||
            (['WP6A','WP7A'].includes(phase) && wp6aPreparationPath(url.pathname,req.method)) ||
            (phase === 'WP5' && url.pathname === '/api/v1/publishing/destinations')) &&
          (['POST','PUT'].includes(req.method) || (third && req.method === 'PATCH') || (sixth && req.method === 'DELETE'))
        ) {
          const chunks = [];
          let length = 0;
          for await (const chunk of req) {
            length += chunk.length;
            if (length > 100000) throw new Error('QA_BODY_TOO_LARGE');
            chunks.push(chunk);
          }
          buffered = Buffer.concat(chunks);
          const payload = buffered.length ? JSON.parse(buffered.toString()) : {};
          const safe = assessment && wp7bPreviewPath(url.pathname,req.method) ? safeWp7bPreview(payload) : seventh && wp7a7Path(url.pathname,req.method) ? safeWp7a7Payload(url.pathname,payload) : sixth && wp7a6Path(url.pathname,req.method) ? safeWp7a6Payload(url.pathname,payload) : fifth && wp7a5Path(url.pathname,req.method) ? safeWp7a5Payload(url.pathname,payload) : fourth && wp7a4Path(url.pathname,req.method) ? safeWp7a4Payload(url.pathname,payload) : third && wp7a3Path(url.pathname,req.method) ? safeWp7a3Payload(url.pathname,payload) : extended && wp7a2Path(url.pathname,req.method) ? safeWp7a2Payload(url.pathname,payload) : phase === 'WP7A' && (wp7aPath(url.pathname,req.method) || url.pathname.endsWith('/runs'))
            ? safeWp7aPayload(url.pathname,payload)
            : ['WP6A','WP7A'].includes(phase) && wp6aPreparationPath(url.pathname,req.method)
            ? safeWp6aPayload(url.pathname,payload)
            : ['WP6','WP6A','WP7A'].includes(phase) && url.pathname.endsWith('/activate')
            ? safeWp6ActivationPayload(payload)
            : url.pathname.endsWith('/runs')
            ? payload.max_provider_calls === 0 && payload.idempotency_key?.startsWith('wp2-')
            : journeyContextPath.test(url.pathname)
              ? safeJourneyContextPayload(url.pathname, payload)
              : url.pathname.endsWith('/suppliers/research')
                ? payload.mode === 'LOCAL_FIXTURE'
                : url.pathname === '/api/v1/publishing/destinations'
                  ? safeWp5DestinationPayload(payload)
                  : payload.environment === 'sandbox' &&
                    payload.credentials &&
                    Object.keys(payload.credentials).length === 0 &&
                    payload.seller_account_id?.startsWith('qa3-') &&
                    payload.display_name?.startsWith('[QA SYNTHETIC]');
          if (!safe) {
            res.writeHead(403).end();
            return;
          }
        }
        const proxy = http.request(
          {
            host: '127.0.0.1',
            port: apiPort,
            path: req.url,
            method: req.method,
            headers: { ...req.headers, origin },
          },
          (reply) => {
            res.writeHead(reply.statusCode, reply.headers);
            reply.on('error', () => res.destroy());
            reply.on('aborted', () => res.destroy());
            reply.pipe(res);
          },
        );
        proxy.on('error', (error) => {
          const diagnostic = proxyFailureDiagnostic(error);
          if (!res.headersSent && !res.destroyed) res.writeHead(502, {
            'Content-Type':'application/json',
            'X-QA-Error-Origin':diagnostic.origin,
            'X-QA-Transport-Code':diagnostic.code,
          }).end(JSON.stringify({error_code:'qa_upstream_transport_unavailable',retryable:true}));
          else if (!res.destroyed) res.destroy();
        });
        if (buffered) proxy.end(buffered);
        else req.pipe(proxy);
        return;
      }
      const file = path.resolve(root, `.${decodeURIComponent(url.pathname)}`);
      if (file !== root && !file.startsWith(`${root}${path.sep}`)) {
        res.writeHead(403).end();
        return;
      }
      const candidate = await fs
        .stat(file)
        .then((stat) => (stat.isFile() ? file : null))
        .catch(() => null);
      const selected = candidate || path.join(root, 'index.html');
      res.writeHead(200, {
        'Content-Type': mime[path.extname(selected)] || 'application/octet-stream',
        'Cache-Control': 'no-store',
      });
      res.end(await fs.readFile(selected));
    } catch {
      if (!res.headersSent && !res.destroyed) res.writeHead(500).end();
      else if (!res.destroyed) res.destroy();
    }
  });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', resolve);
  });
  return server;
}
