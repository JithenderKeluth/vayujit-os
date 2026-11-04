import fs from 'node:fs/promises';
import crypto from 'node:crypto';

// Immutable report history; browser traces stay at their original ignored local paths.
export async function archiveQaReports() {
  const folder = 'docs/qa/history';
  await fs.mkdir(folder, { recursive: true });
  for (const stem of [
    'initial-report',
    'phase-2-report',
    'phase-3-report',
    'phase-4-report',
    'phase-4a-retest-report',
    'phase-4b-report',
  ]) {
    const raw = await fs.readFile(`docs/qa/${stem}.json`, 'utf8').catch((error) => {
      if (error.code === 'ENOENT') return null;
      throw error;
    });
    if (!raw) continue;
    const report = JSON.parse(raw);
    const stamp = report.generated_at.replaceAll(/[^0-9TZ]/g, '-');
    for (const ext of ['json', 'md']) {
      const data = await fs.readFile(`docs/qa/${stem}.${ext}`).catch((error) => {
        if (error.code === 'ENOENT' && ext === 'md') return null;
        throw error;
      });
      if (!data) continue;
      const target = `${folder}/${stem}-${stamp}.${ext}`;
      try {
        await fs.writeFile(target, data, { flag: 'wx' });
      } catch (error) {
        if (error.code !== 'EEXIST') throw error;
        const saved = await fs.readFile(target);
        if (!saved.equals(data)) throw new Error('QA_ARCHIVE_CONTENT_CONFLICT', { cause: error });
      }
      await fs.writeFile(
        `${target}.sha256`,
        crypto.createHash('sha256').update(data).digest('hex') + '\n',
        { flag: 'w' },
      );
    }
  }
}

if (process.argv[1]?.endsWith('archive-reports.mjs')) await archiveQaReports();
