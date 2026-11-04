// Preserve the first legacy-named WP7A manifest; never overwrite original evidence.
import fs from 'node:fs/promises';
const rows = JSON.parse(await fs.readFile('tmp/qa-wp7a/execution-wp7a.json', 'utf8'));
for (const row of rows) {
  if (!/^[a-f0-9]{16}$/.test(row.token)) throw Error('EXACT_TOKEN_REQUIRED');
  const marker = JSON.parse(
    await fs.readFile(`tmp/qa-seller-browser/${row.token}/wp7a-run.json`, 'utf8'),
  );
  if (marker.token !== row.token) throw Error('OWNED_WP7A_REQUIRED');
  try {
    await fs.writeFile(`tmp/qa-wp7a/execution-${row.token}.json`, JSON.stringify([row], null, 2), {
      flag: 'wx',
    });
  } catch (e) {
    if (e.code !== 'EEXIST') throw e;
  }
}
console.log(JSON.stringify({ preserved_tokens: rows.map((r) => r.token) }));
