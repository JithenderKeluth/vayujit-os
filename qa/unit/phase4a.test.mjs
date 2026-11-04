import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { serve } from '../server.mjs';
import { allowRequest, safeJourneyContextPayload } from '../safety.mjs';

const id = '11111111-1111-1111-1111-111111111111';
const path = '/api/v1/intelligence/reviews/contexts';
const payload = {
  name: 'Selected product reviews',
  product_id: null,
  product_opportunity_id: id,
  marketplace: 'AMAZON_IN',
  market: 'IN',
  status: 'ACTIVE',
  idempotency_key: 'ux-r11a-review-' + id + '-AMAZON_IN-IN',
};
test('audited local context payloads are exact and cannot enable acquisition or external execution', () => {
  assert.equal(safeJourneyContextPayload(path, payload), true);
  for (const extra of [
    { url: 'https://example.com' },
    { mode: 'LIVE_READ_ONLY' },
    { actor_type: 'HUMAN' },
    { credentials: { key: 'forbidden' } },
    { approve: true },
  ])
    assert.equal(safeJourneyContextPayload(path, { ...payload, ...extra }), false);
  assert.equal(
    safeJourneyContextPayload(path, { ...payload, idempotency_key: 'unrelated' }),
    false,
  );
  assert.equal(
    safeJourneyContextPayload(path, { ...payload, product_opportunity_id: null }),
    false,
  );
  assert.equal(safeJourneyContextPayload(path, { ...payload, status: 'VERIFIED' }), false);
  assert.equal(safeJourneyContextPayload(path, []), false);
});
test('context allowance is restricted to reviewed Phase 4 routes and canonical POST', () => {
  const origin = 'http://127.0.0.1:49123';
  assert.equal(allowRequest(origin + path, 'POST', origin, '4'), true);
  assert.equal(allowRequest(origin + path, 'POST', origin, '3'), false);
  assert.equal(allowRequest(origin + path, 'DELETE', origin, '4'), false);
  assert.equal(
    allowRequest(
      origin + '/api/v1/intelligence/reviews/contexts/abc/snapshots',
      'POST',
      origin,
      '4',
    ),
    false,
  );
  assert.equal(
    safeJourneyContextPayload('/api/v1/intelligence/suppliers/research', payload),
    false,
  );
});

test('HTTP proxy rejects hostile context payloads before contacting the canonical API', async () => {
  let forwarded = 0;
  const api = http.createServer((req, res) => {
    forwarded++;
    res.writeHead(401).end();
  });
  await new Promise((resolve) => api.listen(0, '127.0.0.1', resolve));
  const proxy = await serve(0, api.address().port, '4');
  try {
    const url = `http://127.0.0.1:${proxy.address().port}${path}`;
    for (const body of [
      { ...payload, mode: 'LIVE_READ_ONLY' },
      { ...payload, approve: true },
    ]) {
      const reply = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      assert.equal(reply.status, 403);
    }
    assert.equal(forwarded, 0);
    const reply = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    assert.equal(reply.status, 401, 'Canonical authentication is not bypassed');
    assert.equal(forwarded, 1);
  } finally {
    await Promise.all(
      [proxy, api].map(
        (server) =>
          new Promise((resolve) => {
            server.closeAllConnections();
            server.close(resolve);
          }),
      ),
    );
  }
});
