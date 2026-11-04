import test from 'node:test';
import assert from 'node:assert/strict';
import { phase3bResolvedIds } from '../phase3b-resolution.mjs';
import { remediationCases } from '../phase3a-resolution.mjs';
const report = () => ({
  cleanup: ['desktop', 'mobile'].map((project) => ({
    project,
    database: project,
    status: 'PASS',
    child_exit: 0,
    proof: { database: project, database_absent: true },
  })),
  reports: [0, 1].map(() => ({
    process_exit_code: 0,
    tests: [
      ...Array.from({ length: 6 }, (_, i) => `QA-P3-0${i + 1}`),
      'QA-P3B-01',
      'QA-P3B-02',
      'QA-P3B-03',
    ].map((id) => ({ id, status: 'passed' })),
    api_results: {
      process_exit_code: 0,
      tests: [
        ...Object.values(remediationCases),
        'test_17_canonical_order_synthetic_provenance_and_state_change',
        ...Array.from({ length: 12 }, (_, i) => `other-${i}`),
      ].map((id) => ({ id, status: 'PASS' })),
    },
  })),
});
test('Phase 3B closes only named roots and reviewed navigation, not accessibility or gaps', () => {
  const ids = phase3bResolvedIds(report(), { verified: true });
  assert.equal(ids.length, 8);
  assert.ok(ids.includes('QA-P3-SOURCE-001'));
  assert.ok(!ids.includes('QA-P3-A11Y-REVIEW-001'));
  assert.ok(!ids.includes('QA-P3-GAP-003'));
});
test('Phase 3B rejects missing targeted execution and cleanup failure', () => {
  assert.deepEqual(phase3bResolvedIds(report(), { verified: false }), []);
  const r = report();
  r.cleanup[0].child_exit = 1;
  assert.deepEqual(phase3bResolvedIds(r, { verified: true }), []);
});
test('Phase 3B rejects failed or missing original and supplemental scenarios', () => {
  const r = report();
  r.reports[0].tests[3].status = 'failed';
  assert.deepEqual(phase3bResolvedIds(r, { verified: true }), []);
  r.reports[0].tests[3].status = 'passed';
  r.reports[1].tests.pop();
  assert.deepEqual(phase3bResolvedIds(r, { verified: true }), []);
});
test('Phase 3B cannot close with API error or unknown exit despite passing browser', () => {
  const r = report();
  r.reports[0].api_results.tests[5].status = 'ERROR';
  assert.deepEqual(phase3bResolvedIds(r, { verified: true }), []);
  r.reports[0].api_results.tests[5].status = 'PASS';
  r.reports[1].api_results.process_exit_code = 1;
  assert.deepEqual(phase3bResolvedIds(r, { verified: true }), []);
});
