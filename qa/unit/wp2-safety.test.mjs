import { test } from 'node:test';
import assert from 'node:assert/strict';
import { serve } from '../server.mjs';
import { allowRequest } from '../safety.mjs';
test('WP2 permits score comparison but never starts a Business Agent run', () => {
  const origin = 'http://127.0.0.1:4200';
  assert.equal(
    allowRequest(
      origin + '/api/v1/intelligence/product-opportunities/score/rank',
      'POST',
      origin,
      '4',
    ),
    true,
  );
  assert.equal(
    allowRequest(
      origin +
        '/api/v1/intelligence/business-agent/runs/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/start',
      'POST',
      origin,
      '4',
    ),
    false,
  );
  assert.equal(allowRequest('https://supplier.example/', 'GET', origin, '4'), false);
});
test('WP2 queued-run fixture refuses provider budgets and nonfixture identities before upstream', async () => {
  const server = await serve(0, 1, '4');
  try {
    const origin = `http://127.0.0.1:${server.address().port}`;
    for (const payload of [
      { idempotency_key: 'wp2-x', max_provider_calls: 1 },
      { idempotency_key: 'other', max_provider_calls: 0 },
      {},
    ]) {
      const response = await fetch(
        origin +
          '/api/v1/intelligence/business-agent/goals/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/runs',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
      );
      assert.equal(response.status, 403);
    }
  } finally {
    await new Promise((r) => server.close(r));
  }
});
