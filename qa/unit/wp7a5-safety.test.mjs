import { test } from 'node:test';
import assert from 'node:assert/strict';
import { allowRequest } from '../safety.mjs';
import { safeWp7a5Payload } from '../wp7a5-safety.mjs';
const origin = 'http://127.0.0.1:49111';
test('WP7A5 extends metadata/recovery only and never dispatch or real credentials', () => {
  for (const path of [
    '/api/v1/social/posts/abc/publish-now',
    '/api/v1/marketplaces/amazon/listings/abc/submit',
    '/api/v1/ai/providers/abc/validate',
  ])
    assert.equal(allowRequest(origin + path, 'POST', origin, 'WP7A5'), false);
  assert.equal(safeWp7a5Payload('/api/v1/ai/seo/tags', { api_key: 'not-a-real-key' }), false);
  assert.equal(
    allowRequest('https://example.com/api/v1/ai/seo/tags', 'POST', origin, 'WP7A5'),
    false,
  );
});
test('bounded local fault controls do not leak to prior phases', () => {
  assert.equal(
    safeWp7a5Payload('/__qa/wp7a3/control', { scenario: 'WORKER_FAIL', limit: 1 }),
    true,
  );
  for (const limit of [0, 17, true, '1'])
    assert.equal(
      safeWp7a5Payload('/__qa/wp7a3/control', { scenario: 'WORKER_FAIL', limit }),
      false,
    );
  assert.equal(allowRequest(origin + '/api/v1/ai/seo/tags/abc', 'PUT', origin, 'WP7A4'), false);
  assert.equal(allowRequest(origin + '/api/v1/ai/seo/tags/abc', 'PUT', origin, 'WP7A5'), true);
});
test('synthetic observation admission requires explicit UNKNOWN provenance', () => {
  const path = '/api/v1/intelligence/trends/contexts/abc/observations';
  assert.equal(
    safeWp7a5Payload(path, {
      raw_metadata: { synthetic: true },
      verification_state: 'UNKNOWN',
      provenance_note: '[QA SYNTHETIC] local',
    }),
    true,
  );
  assert.equal(
    safeWp7a5Payload(path, {
      raw_metadata: { synthetic: true },
      verification_state: 'VERIFIED',
      provenance_note: '[QA SYNTHETIC] local',
    }),
    false,
  );
});
