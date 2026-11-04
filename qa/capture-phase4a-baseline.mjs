import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import { archiveQaReports } from './archive-reports.mjs';

const target = 'docs/qa/phase-4a-baseline.json';
if (
  await fs
    .access(target)
    .then(() => true)
    .catch(() => false)
)
  throw new Error('QA_PHASE4A_BASELINE_ALREADY_EXISTS');
await archiveQaReports();
const reportRaw = await fs.readFile('docs/qa/phase-4-report.json');
const report = JSON.parse(reportRaw);
const backlog = JSON.parse(await fs.readFile('docs/qa/defect-backlog.json', 'utf8'));
const inventory = JSON.parse(await fs.readFile('docs/qa/phase-4-source-inventory.json', 'utf8'));
const components = new Set();
for (const f of backlog.filter((f) => f.confidence === 'CONFIRMED' && f.type === 'ACCESSIBILITY')) {
  const r = inventory.routes.find(
    (r) => r.route === f.route || r.route.replace(/:[^/]+/g, ':id') === f.route,
  );
  if (r?.component) components.add(r.component);
}
for (const file of [
  'apps/web/src/styles.css',
  'apps/web/src/app/intelligence/supplier-due-diligence.component.ts',
  'qa/tests/phase4.spec.mjs',
  'qa/explore.mjs',
])
  components.add(file);
const sha = async (file) =>
  crypto
    .createHash('sha256')
    .update(await fs.readFile(file))
    .digest('hex');
const source_sha256 = Object.fromEntries(
  await Promise.all([...components].sort().map(async (f) => [f, await sha(f)])),
);
await fs.writeFile('docs/qa/phase-4a-baseline-report.json', reportRaw, { flag: 'wx' });
await fs.writeFile(
  target,
  JSON.stringify(
    {
      generated_at: new Date().toISOString(),
      report_sha256: crypto.createHash('sha256').update(reportRaw).digest('hex'),
      source_sha256,
      findings: backlog,
      failed_scenarios: report.reports
        .flatMap((r) => r.tests)
        .filter((t) => t.status !== 'passed')
        .map((t) => ({ id: t.id, project: t.project, error: t.error, evidence: t.evidence })),
      classification: 'IMMUTABLE_PRE_REMEDIATION_EVIDENCE',
    },
    null,
    2,
  ),
  { flag: 'wx' },
);
console.log(
  JSON.stringify({ findings: backlog.length, sources: components.size, original_failures: 8 }),
);
