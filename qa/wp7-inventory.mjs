// WP7 inventory is fresh source evidence, never presumed executed coverage.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { audit } from './audit.mjs';

const root = 'docs/qa/seller-experience';
const data = await audit({ write: false });
const routeSource = await fs.readFile('apps/web/src/app/app.routes.ts', 'utf8');
for (const r of data.routes) {
  if (!r.component && r.kind === 'PAGE') {
    const block = routeSource.slice(routeSource.indexOf(`path: '${r.route.slice(1)}'`));
    const name = block.match(/loadComponent:\s*(\w+)/)?.[1];
    const escaped = name?.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const rel =
      escaped &&
      routeSource.match(new RegExp(`const ${escaped} = [\\s\\S]*?import\\('([^']+)'\\)`))?.[1];
    if (rel) r.component = path.posix.join('apps/web/src/app', rel + '.ts');
  }
  r.runtime_coverage = 'NOT_TESTED';
  r.feature_execution = 'NOT_TESTED';
  r.api_dependencies = [];
  if (r.component) {
    const source = await fs.readFile(r.component, 'utf8');
    r.api_dependencies = [...source.matchAll(/import[^;]*?from\s+['"]([^'"]*service)['"]/g)].map(
      (m) => path.posix.normalize(path.posix.join(path.posix.dirname(r.component), m[1] + '.ts')),
    );
    r.api_mapping = 'STATIC_SERVICE_REFERENCES_NOT_RUNTIME_PROOF';
  }
}
const files = (await fs.readdir(root)).filter((n) =>
  /^(wp[1-6]|browser-|application-|prioritized-|proposed-|current-|workflow-|audit-|ux-)/.test(n),
);
const evidence = [];
const ledgers = [];
for (const name of files) {
  const text = await fs.readFile(path.join(root, name), 'utf8');
  evidence.push({
    file: `${root}/${name}`,
    sha256: crypto.createHash('sha256').update(text).digest('hex'),
    bytes: Buffer.byteLength(text),
  });
  if (name.endsWith('resolution.json')) ledgers.push({ name, data: JSON.parse(text) });
}
const original = JSON.parse(await fs.readFile(`${root}/browser-findings.json`, 'utf8'));
const findings = Array.isArray(original) ? original : original.findings;
const reconciliation = findings.map((f) => {
  const resolutions = ledgers.filter((l) =>
    ['resolved_findings', 'resolved_original_findings'].some((k) => l.data[k]?.includes(f.id)),
  );
  return {
    ...f,
    historical_disposition: resolutions.length ? 'RESOLVED_BOUNDED_PRIOR_WP' : 'OPEN_OR_UNVERIFIED',
    resolution_ledgers: resolutions.map((r) => `${root}/${r.name}`),
    wp7_retest: 'NOT_TESTED',
  };
});
let revision = null;
try {
  revision = execFileSync(
    'git',
    ['-c', 'safe.directory=' + process.cwd().replaceAll('\\', '/'), 'rev-parse', 'HEAD'],
    { encoding: 'utf8' },
  ).trim();
} catch {
  /* explicit unknown */
}
const inventory = {
  ...data,
  package: 'WP7',
  revision,
  dirty_worktree: true,
  lock_sha256: crypto
    .createHash('sha256')
    .update(await fs.readFile('package-lock.json'))
    .digest('hex'),
  evidence_review: evidence,
  original_findings: reconciliation,
  limitations: [
    'Source references and test-file presence are not executed coverage.',
    'Dynamic routes require canonical persisted identities; unavailable IDs are not invented.',
    'Single seller, disposable synthetic data, live providers and backup operations prohibited.',
  ],
};
await fs.mkdir('tmp/qa-wp7', { recursive: true });
await fs.writeFile('tmp/qa-wp7/inventory.json', JSON.stringify(inventory, null, 2));
console.log(
  JSON.stringify({
    routes: data.routes.length,
    pages: data.routes.filter((r) => r.kind === 'PAGE').length,
    api_declarations: data.api_declarations.length,
    models: data.models.length,
    evidence_files: evidence.length,
    original_findings: reconciliation.length,
    revision,
  }),
);
