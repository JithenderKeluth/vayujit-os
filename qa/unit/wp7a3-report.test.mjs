import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

test('WP7A3 report preserves counts and never inherits translation coverage from sharing an artifact route', () => {
  const read = (file) => JSON.parse(fs.readFileSync(new URL('../../docs/qa/seller-experience/' + file, import.meta.url)));
  const matrix = read('wp7a3-required-coverage.json');
  const gate = read('wp7a3-gate.json');
  assert.equal(matrix.entries.length, 49);
  assert.equal(new Set(matrix.entries.map(e => e.id)).size, 49);
  assert.deepEqual(matrix.entries.filter(e => e.full_closure).map(e => e.id), ['L-11']);
  assert.equal(matrix.entries.filter(e => e.status === 'PARTIAL').length, gate.counting.partial);
  assert.equal(matrix.entries.filter(e => e.status === 'NOT_TESTED').length, gate.counting.not_tested);
  assert.deepEqual(matrix.entries.filter(e => !e.full_closure).map(e => e.id).sort(), [...gate.open_entries].sort());
  const translation = matrix.entries.find(e => e.id === 'L-25');
  assert.equal(translation.status, 'NOT_TESTED');
  assert.deepEqual(translation.evidence, []);
  assert.equal(gate.status, 'INCOMPLETE');
});
