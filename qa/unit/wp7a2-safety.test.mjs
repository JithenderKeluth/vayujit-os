import test from 'node:test';
import assert from 'node:assert/strict';
import { allowRequest } from '../safety.mjs';
import { safeWp7a2Payload } from '../wp7a2-safety.mjs';
const origin = 'http://127.0.0.1:62001';
test('WP7A2 narrowly adds existing offline approval/recovery, not live execution or earlier phase rights', () => {
  for (const p of [
    '/api/v1/ai/video/storyboards/11111111-1111-1111-1111-111111111111/approve',
    '/api/v1/ads/campaigns/confirm',
    '/__qa/wp7a2/control',
  ]) {
    assert.equal(allowRequest(origin + p, 'POST', origin, 'WP7A2'), true);
    assert.equal(allowRequest(origin + p, 'POST', origin, 'WP7A'), false);
    assert.equal(allowRequest('https://example.org' + p, 'POST', origin, 'WP7A2'), false);
  }
  for (const p of [
    '/api/v1/marketplaces/amazon/listings/111/submit',
    '/api/v1/ai/studio/recovery/actions',
    '/api/v1/ads/accounts/111/credentials',
  ])
    assert.equal(allowRequest(origin + p, 'POST', origin, 'WP7A2'), false);
});
test('WP7A2 credentials can only be the explicit fake marker on a local meta fixture', () => {
  const p = '/api/v1/ads/accounts',
    b = {
      environment: 'local',
      provider: 'meta',
      external_account_id: 'qa-wp7a2-unit',
      display_name: '[QA SYNTHETIC] WP7A2 unit',
      credentials: { token: 'QA-SYNTHETIC-NOT-A-REAL-CREDENTIAL' },
    };
  assert.equal(safeWp7a2Payload(p, b), true);
  for (const patch of [
    { environment: 'production' },
    { provider: 'amazon' },
    { credentials: { token: 'not-approved' } },
  ])
    assert.equal(safeWp7a2Payload(p, { ...b, ...patch }), false);
});
test('WP7A2 controls reject arbitrary commands, mutable approval state and unknown fields', () => {
  assert.equal(
    safeWp7a2Payload('/__qa/wp7a2/control', {
      scenario: 'VIDEO_FAILURE',
      id: '11111111-1111-1111-1111-111111111111',
    }),
    true,
  );
  for (const b of [
    { scenario: 'APPROVE', id: '11111111-1111-1111-1111-111111111111' },
    { scenario: 'RECONSTRUCT', id: '11111111-1111-1111-1111-111111111111', command: 'unsafe' },
  ])
    assert.equal(safeWp7a2Payload('/__qa/wp7a2/control', b), false);
  assert.equal(
    safeWp7a2Payload('/storyboard/approve', { expected_row_version: 1, approved_by: 'someone' }),
    false,
  );
});
