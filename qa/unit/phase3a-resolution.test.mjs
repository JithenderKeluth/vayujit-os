import test from 'node:test';
import assert from 'node:assert/strict';
import { remediationCases, resolvedIds } from '../phase3a-resolution.mjs';

const report = () => ({
  cleanup: Array.from({ length: 2 }, (_, i) => ({
    status: 'PASS',
    database: `qa-${i}`,
    project: ['desktop', 'mobile'][i],
    child_exit: 0,
    proof: { database_absent: true, database: `qa-${i}` },
  })),
  reports: Array.from({ length: 2 }, () => ({
    api_results: { tests: Object.values(remediationCases).map((id) => ({ id, status: 'PASS' })) },
  })),
});

test('only five explicitly scoped roots can close with both original installations passing', () => {
  assert.deepEqual(resolvedIds(report(), { verified: true }), Object.keys(remediationCases));
  assert.ok(!Object.keys(remediationCases).includes('QA-P3-SOURCE-001'));
  assert.ok(!Object.keys(remediationCases).includes('QA-P3-UX-001'));
});
test('missing or failed targeted evidence cannot close roots', () => {
  assert.deepEqual(resolvedIds(report()), []);
  assert.deepEqual(resolvedIds(report(), { verified: false }), []);
});
test('failed cleanup prevents closure even when assertions pass', () => {
  const value = report();
  value.cleanup[0].child_exit = 1;
  assert.deepEqual(resolvedIds(value, { verified: true }), []);
});
test('failed or missing original assertion reopens its root', () => {
  const value = report();
  value.reports[0].api_results.tests[0].status = 'FAIL';
  assert.equal(resolvedIds(value, { verified: true }).length, 4);
  value.reports[1].api_results.tests.pop();
  assert.equal(resolvedIds(value, { verified: true }).length, 3);
});
test('duplicate original evidence is not two independent passing installations', () => {
  const value = report();
  value.reports[0].api_results.tests.push(value.reports[0].api_results.tests[0]);
  assert.equal(resolvedIds(value, { verified: true }).length, 4);
  value.reports.pop();
  assert.deepEqual(resolvedIds(value, { verified: true }), []);
});
test('duplicating a cleanup proof cannot establish two isolated installations', () => {
  const value = report();
  value.cleanup[1] = value.cleanup[0];
  assert.deepEqual(resolvedIds(value, { verified: true }), []);
});
