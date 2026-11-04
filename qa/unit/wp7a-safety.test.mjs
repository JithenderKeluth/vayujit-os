import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { allowRequest } from '../safety.mjs';
import { safeWp7aPayload } from '../wp7a-safety.mjs';
const origin = 'http://127.0.0.1:62111';
test('research secondary action links receive the same explicit foreground as buttons', async () => {
  const css = await fs.readFile(
    'apps/web/src/app/intelligence/business-agent-workspace.css',
    'utf8',
  );
  const rule = css.match(/button,\s*\.primary-action,\s*\.action-link\s*\{([^}]+)\}/)?.[1];
  assert.ok(rule);
  assert.match(rule, /color:\s*#fff/);
  assert.match(rule, /background:\s*var\(--vj-color-brand-strong\)/);
});
test('WP7A local mutations are isolated from earlier phases and remain same-origin', () => {
  for (const path of [
    '/__qa/wp7a/control',
    '/api/v1/ai/video/queue',
    '/api/v1/intelligence/business-agent/runs/11111111-1111-1111-1111-111111111111/start',
  ]) {
    assert.equal(allowRequest(origin + path, 'POST', origin, 'WP7A'), true);
    assert.equal(allowRequest(origin + path, 'POST', origin, 'WP6B'), false);
    assert.equal(allowRequest('https://example.org' + path, 'POST', origin, 'WP7A'), false);
  }
});
test('WP7A never admits advertising execution, marketplace publication or HUMAN approval bypass', () => {
  for (const path of [
    '/api/v1/ads/campaigns/confirm',
    '/api/v1/ads/accounts/111/enable',
    '/api/v1/marketplaces/amazon/listings/111/submit',
    '/api/v1/ai/video/storyboards/111/approve',
    '/api/v1/orders/import',
  ])
    assert.equal(allowRequest(origin + path, 'POST', origin, 'WP7A'), false);
});
test('WP7A fault controls accept only bounded synthetic scenarios', () => {
  assert.equal(safeWp7aPayload('/__qa/wp7a/control', { scenario: 'NONE' }), true);
  for (const value of [
    { scenario: 'LIVE' },
    { scenario: 'EXPIRED', credentials: 'secret' },
    null,
    [],
  ])
    assert.equal(safeWp7aPayload('/__qa/wp7a/control', value), false);
});
test('WP7A queue is bounded to credential-free image-free local cards; research calls cannot select LIVE mode', () => {
  const path = '/api/v1/ai/video/queue';
  assert.equal(safeWp7aPayload(path, { failure_scenario: 'success', audio_mode: 'none' }), true);
  for (const p of [
    { script_id: '111' },
    { source_media_ids: ['111'] },
    { audio_mode: 'future_provider_voice' },
    { failure_scenario: 'external' },
    { provider: 'live', credentials: 'secret' },
  ])
    assert.equal(safeWp7aPayload(path, p), false);
});
test('WP7A negative import checks cannot invoke mutation operations or attach credentials', () => {
  const path = '/api/v1/marketplaces/accounts/111/imports';
  const safe = { operation: 'catalog', mode: 'LIVE_READ_ONLY', idempotency_key: 'wp7a-denial' };
  assert.equal(safeWp7aPayload(path, safe), true);
  for (const patch of [{ operation: 'publish' }, { credentials: 'secret' }, { mode: 'LIVE_WRITE' }])
    assert.equal(safeWp7aPayload(path, { ...safe, ...patch }), false);
});
