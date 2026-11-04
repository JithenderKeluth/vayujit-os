import { test } from 'node:test';
import assert from 'node:assert/strict';
import { saveEvidence } from '../wp7a4-evidence.mjs';
test('Windows sharing failure retries atomic replacement without truncating the ledger', async () => {
  let attempts = 0,
    writes = 0,
    removed = 0;
  const io = {
    writeFile: async (_file, text, opts) => {
      writes++;
      assert.equal(JSON.parse(text).status, 'FAIL');
      assert.equal(opts.flag, 'wx');
    },
    rename: async () => {
      if (++attempts < 3) throw Object.assign(Error('omitted'), { code: 'UNKNOWN' });
    },
    unlink: async () => {
      removed++;
    },
  };
  await saveEvidence('ledger.json', { status: 'FAIL' }, io, async () => {});
  assert.equal(attempts, 3);
  assert.equal(writes, 1);
  assert.equal(removed, 1);
});
test('persistent write failure stays fail-closed and only removes its own staging artifact', async () => {
  let attempts = 0;
  const removed = [];
  const io = {
    writeFile: async () => {},
    rename: async () => {
      attempts++;
      throw Object.assign(Error('omitted'), { code: 'EACCES' });
    },
    unlink: async (file) => {
      removed.push(file);
    },
  };
  await assert.rejects(
    saveEvidence('ledger.json', {}, io, async () => {}),
    { code: 'EACCES' },
  );
  assert.equal(attempts, 5);
  assert.equal(removed.length, 1);
  assert.match(removed[0], /^ledger.json.wp7a4-/);
});
