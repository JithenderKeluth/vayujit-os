import test from 'node:test';
import assert from 'node:assert/strict';
import { allowRequest, safeWp6ActivationPayload } from '../safety.mjs';
const origin = 'http://127.0.0.1:43210';
const id = '11111111-1111-4111-8111-111111111111';
test('WP6 admits only local canonical Product activation, not publication or other phase expansion', () => {
  const route = `/api/v1/products/${id}/activate`;
  assert.equal(allowRequest(origin + route, 'POST', origin, 'WP6'), true);
  assert.equal(allowRequest(origin + route, 'POST', origin, '4'), false);
  for (const [url, method] of [
    [origin + route, 'DELETE'],
    ['https://evil.invalid' + route, 'POST'],
    [origin + '/api/v1/products/not-a-uuid/activate', 'POST'],
    [origin + '/api/v1/marketplaces/amazon/execute', 'POST'],
    [origin + '/api/v1/publishing/jobs', 'POST'],
    [origin + '/api/v1/operations/backups', 'POST'],
    [origin + '/__qa/restart', 'POST'],
  ])
    assert.equal(allowRequest(url, method, origin, 'WP6'), false);
});
test('WP6 activation accepts no credentials, side effects, status claims or arbitrary arguments', () => {
  assert.equal(safeWp6ActivationPayload({}), true);
  for (const p of [
    null,
    [],
    true,
    '{}',
    { credentials: {} },
    { publish: true },
    { status: 'active' },
    { marketplace: 'amazon' },
  ])
    assert.equal(safeWp6ActivationPayload(p), false);
});
