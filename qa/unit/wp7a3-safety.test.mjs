import test from 'node:test';
import assert from 'node:assert/strict';
import { allowRequest } from '../safety.mjs';
import { safeWp7a3Payload } from '../wp7a3-safety.mjs';
const o = 'http://127.0.0.1:62000';
test('WP7A3 exact local artifact rights do not leak to earlier phases or external origins', () => {
  for (const p of [
    '/api/v1/ai/studio/generate',
    '/api/v1/ai/images/generate',
    '/api/v1/ai/artifacts/111/approve',
  ]) {
    assert.equal(allowRequest(o + p, 'POST', o, 'WP7A3'), true);
    assert.equal(allowRequest(o + p, 'POST', o, 'WP7A2'), false);
    assert.equal(allowRequest('https://example.com' + p, 'POST', o, 'WP7A3'), false);
  }
});
test('WP7A3 cannot dispatch publication or authorize real credentials', () => {
  for (const p of [
    '/api/v1/publishing/executions',
    '/api/v1/campaigns/111/release',
    '/api/v1/ai/providers/openai_compatible/validate',
    '/api/v1/marketplaces/amazon/listings/111/submit',
  ])
    assert.equal(allowRequest(o + p, 'POST', o, 'WP7A3'), false);
  assert.equal(
    safeWp7a3Payload('/api/v1/ai/studio/generate', { provider_key: 'openai_compatible' }),
    false,
  );
  assert.equal(safeWp7a3Payload('/__qa/wp7a3/control', { scenario: 'APPROVE' }), false);
  assert.equal(
    safeWp7a3Payload('/__qa/wp7a3/control', { scenario: 'WORKER_SUCCESS', command: 'run' }),
    false,
  );
});
