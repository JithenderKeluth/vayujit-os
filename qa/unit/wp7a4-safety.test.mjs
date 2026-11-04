import test from 'node:test';
import assert from 'node:assert/strict';
import { allowRequest } from '../safety.mjs';
import { safeWp7a4Payload } from '../wp7a4-safety.mjs';
test('WP7A4 local preparation never authorizes dispatch or real credentials', () => {
  const o = 'http://127.0.0.1:62000';
  for (const p of [
    '/publishing/executions',
    '/social/posts/111/publish',
    '/marketplaces/amazon/execute',
    '/campaigns/111/release',
  ])
    assert.equal(allowRequest(o + '/api/v1' + p, 'POST', o, 'WP7A4'), false);
  assert.equal(
    safeWp7a4Payload('/api/v1/social/accounts', {
      environment: 'local',
      credentials: { token: 'real' },
    }),
    false,
  );
  assert.equal(
    safeWp7a4Payload('/api/v1/publishing/destinations', { connector_key: 'shopify' }),
    false,
  );
  assert.equal(
    allowRequest('https://example.com/api/v1/ai/studio/presets', 'POST', o, 'WP7A4'),
    false,
  );
});
test('WP7A4 rights are phase-isolated and preparation controls are bounded', () => {
  const o = 'http://127.0.0.1:62000',
    p = '/api/v1/ai/studio/presets';
  assert.equal(allowRequest(o + p, 'POST', o, 'WP7A4'), true);
  assert.equal(allowRequest(o + p, 'POST', o, 'WP7A3'), false);
  assert.equal(
    safeWp7a4Payload('/__qa/wp7a4/prepare', { artifact_id: 'a'.repeat(36), execute: true }),
    false,
  );
  assert.equal(
    safeWp7a4Payload('/api/v1/ai/video/bulk/preview', { product_ids: ['1', '2'] }),
    false,
  );
});
test('local Video HUMAN approval and synthetic reconciliation remain narrow', () => {
  const origin = 'http://127.0.0.1:62000',
    url = origin + '/api/v1/ai/video/generations/11111111-1111-1111-1111-111111111111/approve';
  assert.equal(allowRequest(url, 'POST', origin, 'WP7A4'), true);
  assert.equal(allowRequest(url, 'POST', origin, 'WP7A3'), false);
  assert.equal(safeWp7a4Payload(new URL(url).pathname, { feedback: null }), true);
  assert.equal(safeWp7a4Payload(new URL(url).pathname, { feedback: null, execute: true }), false);
  assert.equal(
    safeWp7a4Payload('/api/v1/intelligence/cross-marketplace/suppliers/reconcile', {
      supplier_ids: ['a', 'b'],
    }),
    false,
  );
  assert.equal(
    safeWp7a4Payload('/api/v1/intelligence/suppliers/manual', {
      display_name: 'Real supplier',
      provenance: 'synthetic',
    }),
    false,
  );
  assert.equal(
    safeWp7a4Payload('/api/v1/ai/video/bulk', { product_ids: ['p'], video_types: ['a', 'b', 'c'] }),
    false,
  );
});
