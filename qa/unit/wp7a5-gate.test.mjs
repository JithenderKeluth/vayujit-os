import test from 'node:test';
import assert from 'node:assert/strict';
import { gate, ids, contexts } from '../wp7a5-gate.mjs';
const entries = () =>
  ids.map((id) => ({
    id,
    acceptance_review: { complete: true },
    evidence_integrity: true,
    attempts: contexts.map((context) => ({
      context,
      status: 'PASS',
      screenshot: 'real.png',
      trace: 'real.zip',
    })),
  }));
test('WP7A5 requires the exact sixteen IDs and preserves the original denominator', () => {
  const result = gate({ entries: entries().slice(0, 15) });
  assert.equal(result.status, 'INCOMPLETE');
  assert.equal(result.exact_scope, false);
  assert.equal(result.original_denominator, 48);
  assert.equal(result.inherited_closed, 32);
});
test('shared route passes cannot replace acceptance review or four browser identities', () => {
  const values = entries();
  values[0].acceptance_review.complete = false;
  values[1].attempts.pop();
  values[2].attempts[0].status = 'FAIL';
  const result = gate({ entries: values });
  assert.equal(result.status, 'INCOMPLETE');
  assert.equal(result.newly_closed, 13);
});
test('missing cleanup, regression evidence or unresolved blockers cannot produce PASS', () => {
  const result = gate({ entries: entries(), blockers: ['unresolved P1'] });
  assert.equal(result.status, 'INCOMPLETE');
  assert.equal(result.cleanup, 'INCOMPLETE');
  assert.equal(result.regressions, 'INCOMPLETE');
  assert.equal(result.application_certification, 'INCOMPLETE');
});
