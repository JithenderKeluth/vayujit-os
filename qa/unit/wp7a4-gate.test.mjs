import { test } from 'node:test';
import assert from 'node:assert/strict';
import { wp7a4Gate } from '../wp7a4-gate.mjs';
import { requiredContexts } from '../wp7a4-rollup.mjs';
const fixture = () => ({
  requiredIds: Array.from({ length: 48 }, (_, i) => 'ORIGINAL-' + i),
  entries: Array.from({ length: 48 }, (_, i) => ({
    id: 'ORIGINAL-' + i,
    status: 'PASS',
    full_closure: true,
    evidence_integrity: true,
    attempts: requiredContexts.map((context) => ({ context, status: 'PASS' })),
  })),
  cleanup: {
    database_absence_status: 'PASS',
    databases: [{ absent: true, state: 'DROPPED' }],
    historical_baseline_unchanged: true,
  },
  regressions: Object.fromEntries(
    [
      'backend',
      'angular',
      'node_qa',
      'python_qa',
      'build',
      'lint',
      'typescript',
      'mypy',
      'ruff_black',
      'compile_parser',
      'diff',
    ].map((k) => [k, { status: 'PASS' }]),
  ),
  blockers: [],
});
test('complete scoped evidence never declares whole-application certification', () => {
  const r = wp7a4Gate(fixture());
  assert.equal(r.status, 'PASS');
  assert.equal(r.application_certification, 'INCOMPLETE');
});
for (const reason of [
  'missing ID',
  'partial',
  'missing browser',
  'missing evidence',
  'cleanup',
  'regression',
  'P1',
  'unreasoned exclusion',
])
  test('gate refuses ' + reason, () => {
    const f = fixture();
    if (reason === 'missing ID') f.entries.pop();
    if (reason === 'partial') f.entries[0].status = 'PARTIAL';
    if (reason === 'missing browser') f.entries[0].attempts.pop();
    if (reason === 'missing evidence') f.entries[0].evidence_integrity = false;
    if (reason === 'cleanup') f.cleanup.databases[0].state = 'DROPPING';
    if (reason === 'regression') f.regressions.backend.status = 'FAIL';
    if (reason === 'P1') f.blockers.push({ severity: 'P1' });
    if (reason === 'unreasoned exclusion') f.entries[0].status = 'NOT_SUPPORTED';
    assert.equal(wp7a4Gate(f).status, 'INCOMPLETE');
  });
