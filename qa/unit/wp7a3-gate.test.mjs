import test from 'node:test';
import assert from 'node:assert/strict';
import { wp7a3Gate } from '../wp7a3-gate.mjs';
const browser = {
  status: 'PASS',
  checks: ['chrome-1440', 'chrome-390', 'msedge-1440', 'msedge-390'].flatMap((c) =>
    Array.from({ length: 9 }, (_, i) => ({
      context: 'wp7a3-' + c,
      id: 'L-' + String(i + 9).padStart(2, '0'),
      status: 'PASS',
    })),
  ),
};
const input = {
  entries: Array.from({length:49},(_,i)=>({id:'required-'+i,status:'PASS',full_closure:true})),
  requiredIds: Array.from({length:49},(_,i)=>'required-'+i),
  browser,
  backendExit: 0,
  cleanup: 'PASS',
};
test('WP7A3 can close only an explicit complete matrix and all browser identities', () =>
  assert.equal(wp7a3Gate(input).status, 'PASS'));
test('WP7A3 cannot close on route rendering or a bounded action subset', () => {
  for (const status of ['PARTIAL', 'NOT_TESTED', 'BLOCKED', 'FAIL', 'PASS'])
    assert.equal(
      wp7a3Gate({ ...input, entries: [{ id: 'remaining', status }] }).status,
      'INCOMPLETE',
    );
});
test('WP7A3 denies empty/missing scope and unreasoned exclusions', () => {
  for (const entries of [[], null, [{ id: 'remaining', status: 'NOT_SUPPORTED' }]])
    assert.equal(wp7a3Gate({ ...input, entries }).status, 'INCOMPLETE');
});
test('WP7A3 missing browser context cannot be replaced by duplicate passes', () => {
  assert.equal(
    wp7a3Gate({
      ...input,
      browser: {
        ...browser,
        checks: browser.checks.map((c) => ({ ...c, context: 'wp7a3-chrome-1440' })),
      },
    }).status,
    'INCOMPLETE',
  );
});
test('WP7A3 backend, cleanup and unresolved blockers are mandatory', () => {
  for (const patch of [{ backendExit: 1 }, { cleanup: 'UNVERIFIED' }, { blockers: ['P1'] }])
    assert.equal(wp7a3Gate({ ...input, ...patch }).status, 'INCOMPLETE');
});
