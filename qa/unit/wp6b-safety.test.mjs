import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { allowRequest } from '../safety.mjs';
import { serve, proxyFailureDiagnostic } from '../server.mjs';
test('WP6B inherits only WP6A local policy, never external execution', () => {
  const origin = 'http://127.0.0.1:43210';
  for (const p of [
    '/api/v1/ads/campaigns/confirm',
    '/api/v1/ai/video/queue',
    '/api/v1/ads/accounts/a/enable',
    '/api/v1/ads/jobs/a/run',
  ])
    assert.equal(allowRequest(origin + p, 'POST', origin, 'WP6B'), false);
  assert.equal(
    allowRequest('https://evil.invalid/api/v1/financial/events', 'POST', origin, 'WP6B'),
    false,
  );
});
test('proxy diagnostics discard raw sensitive messages, paths and arbitrary codes', () => {
  const value = proxyFailureDiagnostic({
    code: 'ECONNRESET',
    message: 'password=secret token=private',
    url: 'postgresql://private',
  });
  assert.deepEqual(value, {
    origin: 'qa_reverse_proxy',
    classification: 'upstream_transport',
    code: 'ECONNRESET',
    status: 502,
    raw_output_persisted: false,
  });
  assert.equal(proxyFailureDiagnostic({ code: 'SECRET_VALUE' }).code, 'UNCLASSIFIED_TRANSPORT');
  assert.ok(!JSON.stringify(value).includes('password'));
});
test('actual QA proxy identifies refused upstream, preserves application 500 and recovers', async () => {
  const upstream = http.createServer((req, res) =>
    res
      .writeHead(req.url.includes('comparison') ? 500 : 200, { 'Content-Type': 'application/json' })
      .end('{}'),
  );
  await new Promise((r) => upstream.listen(0, '127.0.0.1', r));
  const apiPort = upstream.address().port;
  const proxy = await serve(0, apiPort, 'WP6B'),
    origin = 'http://127.0.0.1:' + proxy.address().port;
  try {
    let r = await fetch(origin + '/api/v1/ads/comparison');
    assert.equal(r.status, 500);
    assert.equal(r.headers.get('x-qa-error-origin'), null);
    await new Promise((r) => upstream.close(r));
    r = await fetch(origin + '/api/v1/ads/comparison');
    assert.equal(r.status, 502);
    assert.equal(r.headers.get('x-qa-error-origin'), 'qa_reverse_proxy');
    assert.ok(['ECONNRESET', 'ECONNREFUSED'].includes(r.headers.get('x-qa-transport-code')));
    assert.deepEqual(await r.json(), {
      error_code: 'qa_upstream_transport_unavailable',
      retryable: true,
    });
    await new Promise((r) => upstream.listen(apiPort, '127.0.0.1', r));
    r = await fetch(origin + '/api/v1/ads/overview');
    assert.equal(r.status, 200);
  } finally {
    await new Promise((r) => proxy.close(r));
    if (upstream.listening) await new Promise((r) => upstream.close(r));
  }
});
