import test from 'node:test';
import assert from 'node:assert/strict';
import { allowRequest, safeWp6aPayload } from '../safety.mjs';
const origin = 'http://127.0.0.1:43210';
test('WP6A allows local drafts only; provider execution, approvals and workers remain denied', () => {
  assert.ok(allowRequest(origin + '/api/v1/ads/accounts', 'POST', origin, 'WP6A'));
  for (const p of [
    '/api/v1/ads/accounts/a/validate',
    '/api/v1/ads/accounts/a/enable',
    '/api/v1/ads/campaigns/confirm',
    '/api/v1/ads/jobs/a/run',
    '/api/v1/ai/video/queue',
    '/api/v1/ai/video/storyboards/a/approve',
    '/api/v1/operations/backups',
  ])
    assert.equal(allowRequest(origin + p, 'POST', origin, 'WP6A'), false);
  assert.equal(
    allowRequest('https://evil.invalid/api/v1/ads/accounts', 'POST', origin, 'WP6A'),
    false,
  );
  assert.equal(allowRequest(origin + '/api/v1/ads/accounts', 'POST', origin, 'WP6'), false);
});
test('WP6A local accounts cannot carry credentials, real identity, external environment or extra commands', () => {
  const p = {
    provider: 'meta',
    environment: 'local',
    display_name: '[QA SYNTHETIC] WP6A local',
    external_account_id: 'qa-wp6a-local',
    credentials: {},
  };
  assert.ok(safeWp6aPayload('/api/v1/ads/accounts', p));
  for (const change of [
    { credentials: { token: 'x' } },
    { environment: 'production' },
    { provider: 'google' },
    { display_name: 'Real' },
    { external_account_id: 'real' },
    { enable: true },
  ])
    assert.ok(!safeWp6aPayload('/api/v1/ads/accounts', { ...p, ...change }));
});
