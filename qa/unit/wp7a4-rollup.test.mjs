import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rollup, requiredContexts } from '../wp7a4-rollup.mjs';
test('partial replay preserves the latest other browser failures', () => {
  const e = {
    prior_status: 'NOT_TESTED',
    attempts: requiredContexts.map((context) => ({ context, token: 'old', status: 'FAIL' })),
  };
  e.attempts.push({ context: requiredContexts[0], token: 'new', status: 'PASS' });
  assert.equal(rollup(e).status, 'FAIL');
  for (const context of requiredContexts.slice(1))
    e.attempts.push({ context, token: 'new', status: 'PASS' });
  assert.equal(rollup(e).full_closure, true);
});
test('one or three browser contexts can never close a coverage entry', () => {
  for (const n of [0, 1, 3])
    assert.notEqual(
      rollup({
        prior_status: 'NOT_TESTED',
        attempts: requiredContexts.slice(0, n).map((context) => ({ context, status: 'PASS' })),
      }).status,
      'PASS',
    );
});
