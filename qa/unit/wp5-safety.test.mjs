import test from 'node:test';
import assert from 'node:assert/strict';
import { allowRequest, safeWp5DestinationPayload } from '../safety.mjs';
const origin = 'http://127.0.0.1:43210';
test('WP5 admits only the reviewed credential-free mock destination, never real connectors', () => {
  const payload = {
    connector_key: 'mock_publisher_v1',
    name: '[QA SYNTHETIC] WP5 local',
    configuration: { channel_name: 'QA-WP5-LOCAL' },
  };
  assert.equal(safeWp5DestinationPayload(payload), true);
  for (const bad of [
    null,
    {},
    { ...payload, connector_key: 'wordpress' },
    { ...payload, credentials: {} },
    { ...payload, configuration: { ...payload.configuration, endpoint: 'https://example.com' } },
    { ...payload, name: 'real' },
  ])
    assert.ok(!safeWp5DestinationPayload(bad));
});
test('WP5 preserves origin, provider, publishing and worker default-deny and other phase policy', () => {
  const path = '/api/v1/publishing/destinations';
  assert.ok(allowRequest(origin + path, 'POST', origin, 'WP5'));
  assert.ok(!allowRequest(origin + path, 'POST', origin, '4'));
  for (const p of [
    '/api/v1/publishing/jobs',
    '/api/v1/marketplaces/amazon/execute',
    '/api/v1/operations/backups',
    '/api/v1/intelligence/supplier-engagement/dispatch',
  ])
    assert.ok(!allowRequest(origin + p, 'POST', origin, 'WP5'));
  assert.ok(!allowRequest('https://example.com' + path, 'POST', origin, 'WP5'));
});
