import fs from 'node:fs/promises';
import { writePhase2Report } from './phase2-report.mjs';

const read = async (file) => JSON.parse(await fs.readFile(file, 'utf8'));
const phase1 = await read('docs/qa/phase-1-retest-report.json');
const phase2 = await read('docs/qa/phase-2-report.json');
// No finding is closed by source inspection, unit tests alone, or a partial run.
for (const report of [phase1, phase2]) {
  if (
    report.status !== 'PASS_BOUNDED_SMOKE' ||
    report.cleanup.length !== 2 ||
    !report.cleanup.every(
      (c) => c.status === 'PASS' && c.child_exit === 0 && c.proof?.database_absent,
    )
  )
    throw new Error('QA_REMEDIATION_RETEST_NOT_COMPLETE');
}
if (phase2.executive_summary.api_passed !== 22 || phase2.executive_summary.api_failed !== 0)
  throw new Error('QA_REMEDIATION_API_RETEST_NOT_COMPLETE');
const archives = (await fs.readdir('docs/qa/history')).sort();
const baselineFile = (stem) =>
  'docs/qa/history/' + archives.find((f) => f.startsWith(stem + '-') && f.endsWith('.json'));
const baselines = [
  await read(baselineFile('initial-report')),
  await read(baselineFile('phase-2-report')),
];
const rows = [];
for (const [index, baseline] of baselines.entries()) {
  const current = index === 0 ? phase1 : phase2;
  const tests = current.reports.flatMap((r) => r.tests);
  for (const finding of [
    ...baseline.confirmed_bugs,
    ...baseline.findings,
    ...baseline.usability_findings,
  ]) {
    const project = finding.id.includes('MOBILE')
      ? 'mobile'
      : finding.id.includes('DESKTOP')
        ? 'desktop'
        : null;
    let matching = [];
    let resolved = false;
    if (finding.confidence !== 'RECOMMENDATION') {
      if (finding.type === 'ACCESSIBILITY') {
        const rule = JSON.parse(finding.actual).id;
        matching = tests.filter(
          (t) =>
            (!project || t.project === project) && t.axe.some((s) => s.state === finding.feature),
        );
        resolved =
          matching.length > 0 &&
          matching.every((t) =>
            t.axe
              .filter((s) => s.state === finding.feature)
              .every((s) => !s.violations.some((v) => v.id === rule)),
          );
      } else if (finding.id === 'QA-P2-FIN-001' || finding.feature.startsWith('test_06_')) {
        matching = phase2.api_tests.filter(
          (t) => t.id.startsWith('test_06_') && (!project || t.project === project),
        );
        resolved = matching.length > 0 && matching.every((t) => t.status === 'PASS');
      } else {
        const id = finding.id === 'QA-P2-DEC-001' ? 'QA-P2-03' : finding.feature.split(' ')[0];
        matching = tests.filter((t) => t.id === id && (!project || t.project === project));
        resolved = matching.length > 0 && matching.every((t) => t.status === 'passed');
      }
    }
    rows.push({
      id: finding.id,
      baseline: index === 0 ? 'PHASE_1' : 'PHASE_2',
      status: resolved
        ? 'RESOLVED'
        : finding.confidence === 'RECOMMENDATION'
          ? 'OPEN_RECOMMENDATION'
          : 'NOT_RETESTED',
      priority: finding.priority,
      confidence: finding.confidence,
      original_finding: finding,
      retest_evidence: matching.flatMap(
        (t) =>
          t.evidence || [{ name: 'Persisted API retest', path: 'docs/qa/phase-2-report.json' }],
      ),
    });
  }
}
const resolution = {
  generated_at: new Date().toISOString(),
  classification: 'KNOWN_PHASE_1_AND_2_GATES_PASSED_NOT_COMPREHENSIVE_APPLICATION_CERTIFICATION',
  baselines: [baselineFile('initial-report'), baselineFile('phase-2-report')],
  retests: { phase1: phase1.generated_at, phase2: phase2.generated_at },
  resolutions: rows,
};
await fs.writeFile('docs/qa/remediation-retest.json', JSON.stringify(resolution, null, 2));
const reviewed = await read('docs/qa/phase-2-reviewed-findings.json');
for (const finding of reviewed) {
  const result = rows.find((r) => r.id === finding.id);
  if (result?.status === 'RESOLVED') {
    finding.retest_status = 'PASS';
    finding.evidence = [
      ...finding.evidence.filter((e) => e.path !== 'docs/qa/remediation-retest.json'),
      {
        name: 'Independent persisted/browser retest and resolution record',
        path: 'docs/qa/remediation-retest.json',
      },
    ];
  }
}
await fs.writeFile('docs/qa/phase-2-reviewed-findings.json', JSON.stringify(reviewed, null, 2));
phase2.resolved_findings = rows
  .filter((r) => r.status === 'RESOLVED')
  .map((r) => ({
    ...r.original_finding,
    retest_status: 'PASS',
    area: r.original_finding.area || r.original_finding.feature,
    journey: r.original_finding.journey || 'Previously tested seller journey',
    business_impact:
      r.original_finding.business_impact ||
      'Original defect independently retested; see the immutable baseline and new evidence.',
    evidence: [...r.original_finding.evidence, ...r.retest_evidence],
  }));
await writePhase2Report(phase2);
// Preserve original finding records; the active backlog excludes only demonstrated closures.
const latest = await read('docs/qa/defect-backlog.json');
const closed = new Set(rows.filter((r) => r.status === 'RESOLVED').map((r) => r.id));
await fs.writeFile(
  'docs/qa/defect-backlog.json',
  JSON.stringify(
    latest
      .filter((f) => !closed.has(f.id))
      .map((f) => ({
        ...f,
        area: f.area || f.feature,
        journey: f.journey || 'Original seller usability review',
        business_impact:
          f.business_impact ||
          'Seller clarity recommendation retained; not automatically closed by functional test success.',
      })),
    null,
    2,
  ),
);
await fs.appendFile(
  'docs/qa/phase-2-report.md',
  '\n## Independent remediation comparison\n\n' +
    `[Resolution ledger](remediation-retest.json): ${closed.size} original finding occurrences independently resolved. ` +
    'Counts are occurrences, not distinct root causes. Original reports and hashes remain in history/.\n\n' +
    '| Original finding | Retest status | Priority |\n| --- | --- | --- |\n' +
    rows.map((r) => `| ${r.id} | ${r.status} | ${r.priority} |`).join('\n') +
    '\n',
);
console.log(
  JSON.stringify({
    resolved: closed.size,
    remaining: rows
      .filter((r) => r.status !== 'RESOLVED')
      .map((r) => ({ id: r.id, status: r.status, priority: r.priority })),
  }),
);
const coverage = await fs.readFile('docs/qa/coverage-matrix.md', 'utf8');
await fs.writeFile(
  'docs/qa/coverage-matrix.md',
  coverage.replace(/\n<!-- REMEDIATION_RETEST -->[\s\S]*$/, '') +
    '\n<!-- REMEDIATION_RETEST -->\n## Phase 1 independent remediation retest\n\n' +
    '| Scenario | Viewport | Status |\n| --- | --- | --- |\n' +
    phase1.reports
      .flatMap((r) => r.tests)
      .map((t) => `| ${t.title} | ${t.project} | ${t.status} |`)
      .join('\n') +
    `\n\n${closed.size} original finding occurrences are resolved by matching actual retest evidence. ` +
    'Original reports and hashes are preserved. Open usability recommendations and unexecuted coverage remain open. ' +
    'See [remediation validation](phase-2-remediation-validation.md) and [resolution ledger](remediation-retest.json).\n',
);
