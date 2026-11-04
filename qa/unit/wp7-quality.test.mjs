import test from 'node:test';
import assert from 'node:assert/strict';
import { certificationDecision, journeyIds, junitCases } from '../wp7-quality.mjs';
import { cleanupWaitMs } from '../safety.mjs';
const clean = () => ({
  cleanup_verified: true,
  unresolved_p0_p1: 0,
  critical_integrity_or_authorization_failure: false,
  significant_required_coverage_missing: false,
  journeys: journeyIds.map((id) => ({ id, status: 'PASS' })),
  required_accessibility_dispositions: true,
  lower_severity_conditions: [],
});
test('WP7 cannot substitute green unit tests for absent required journeys', () => {
  const e = clean();
  e.journeys = [];
  assert.equal(certificationDecision(e).decision, 'FAIL');
  e.journeys = journeyIds.map((id) => ({ id, status: 'PASS' }));
  e.significant_required_coverage_missing = true;
  assert.equal(certificationDecision(e).decision, 'FAIL');
});
test('WP7 fails closed for cleanup, critical integrity, authorization and unresolved P1', () => {
  for (const patch of [
    { cleanup_verified: false },
    { unresolved_p0_p1: 1 },
    { critical_integrity_or_authorization_failure: true },
    { required_accessibility_dispositions: false },
  ])
    assert.equal(certificationDecision({ ...clean(), ...patch }).decision, 'FAIL');
});
test('WP7 distinguishes bounded conditional and scoped PASS from launch certification', () => {
  assert.equal(certificationDecision(clean()).decision, 'PASS');
  const r = certificationDecision({
    ...clean(),
    lower_severity_conditions: ['manual assistive technology limitation'],
  });
  assert.equal(r.decision, 'CONDITIONAL');
  assert.equal(r.production_launch, 'NOT_CERTIFIED');
  assert.equal(r.backup_restore, 'PARKED');
  assert.equal(r.wp8_started, false);
});
test('WP7 fixture shutdown outlasts the guarded DROP without extending its SQL authority', () => {
  assert.equal(cleanupWaitMs(undefined), 45000);
  assert.equal(cleanupWaitMs('15000'), 45000);
  assert.equal(cleanupWaitMs('90000'), 120000);
  for (const value of ['0', '90001', '-1', '15.5', 'unbounded', true])
    assert.throws(() => cleanupWaitMs(value), /QA_DELETE_TIMEOUT_DENIED/);
});
test('WP7 JUnit census preserves adjacent self-closing passes and paired failures/skips', () => {
  const xml =
    '<testsuite><testcase classname="unit" name="one"/><testcase classname="unit" name="two" />' +
    '<testcase classname="unit" name="three"><failure message="fixture"/></testcase>' +
    '<testcase classname="unit" name="four"><skipped/></testcase><testcase classname="unit" name="five"></testcase></testsuite>';
  assert.deepEqual(
    junitCases(xml).map((r) => r.status),
    ['PASS', 'PASS', 'FAIL', 'SKIPPED', 'PASS'],
  );
});
test('WP7 effective census reconciles exact case identities without adding overlapping retests', () => {
  const pass = (n) => `<testcase classname="unit" name="case${n}"/>`;
  const original = junitCases(
    Array.from({ length: 234 }, (_, n) =>
      n === 100 ? '<testcase classname="unit" name="case100"><failure/></testcase>' : pass(n),
    ).join(''),
  );
  const replay = junitCases(Array.from({ length: 35 }, (_, n) => pass(n + 90)).join(''));
  const effective = new Map([...original, ...replay].map((r) => [r.key, r.status]));
  assert.equal(original.length, 234);
  assert.equal(replay.length, 35);
  assert.equal(effective.size, 234);
  assert.ok([...effective.values()].every((r) => r === 'PASS'));
});
