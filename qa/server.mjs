import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { allowRequest, journeyContextPath, safeJourneyContextPayload } from './safety.mjs';

// Serve the actual production Angular build; proxy only to this run's API.
export async function serve(port, apiPort, phase = '1', control = null) {
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
      if (!allowRequest(url.href, req.method, origin, phase)) {
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
        url.pathname === '/__qa/witness'
      ) {
        let buffered;
        if (
          (url.pathname === '/api/v1/intelligence/suppliers/research' ||
            (phase === '4' && journeyContextPath.test(url.pathname)) ||
            (['3', '4'].includes(phase) && url.pathname === '/api/v1/marketplaces/accounts')) &&
          req.method === 'POST'
        ) {
          const chunks = [];
          let length = 0;
          for await (const chunk of req) {
            length += chunk.length;
            if (length > 100000) throw new Error('QA_BODY_TOO_LARGE');
            chunks.push(chunk);
          }
          buffered = Buffer.concat(chunks);
          const payload = JSON.parse(buffered.toString());
          const safe = journeyContextPath.test(url.pathname)
            ? safeJourneyContextPayload(url.pathname, payload)
            : url.pathname.endsWith('/suppliers/research')
              ? payload.mode === 'LOCAL_FIXTURE'
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
        proxy.on('error', () => {
          if (!res.headersSent && !res.destroyed) res.writeHead(502).end();
          else if (!res.destroyed) res.destroy();
        });
        if (buffered) proxy.end(buffered);
        else req.pipe(proxy);
        return;
      }
      const file = path.resolve(root, `.${decodeURIComponent(url.pathname)}`);
      if (!file.startsWith(`${root}${path.sep}`)) {
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
