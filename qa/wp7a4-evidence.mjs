import fs from 'node:fs/promises';
import crypto from 'node:crypto';

// Atomic replacement and bounded retry for transient Windows file sharing failures.
// Never retry forever or treat a failed evidence write as certification success.
export async function saveEvidence(
  file,
  value,
  io = fs,
  delay = (ms) => new Promise((r) => setTimeout(r, ms)),
) {
  const temp = file + '.wp7a4-' + crypto.randomUUID() + '.tmp';
  let created = false;
  try {
    await io.writeFile(temp, JSON.stringify(value, null, 2), { flag: 'wx' });
    created = true;
    for (let n = 0; ; n++) {
      try {
        await io.rename(temp, file);
        return;
      } catch (error) {
        if (n === 4 || !['UNKNOWN', 'EBUSY', 'EACCES', 'EPERM'].includes(error.code)) throw error;
        await delay(100 * (n + 1));
      }
    }
  } finally {
    if (created)
      await io.unlink(temp).catch((error) => {
        if (error.code !== 'ENOENT') throw error;
      });
  }
}
