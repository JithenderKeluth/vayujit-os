import fs from 'node:fs/promises';
import { finding } from './safety.mjs';
import { verifiedResolutionLedger } from './phase3a-resolution.mjs';
import { verifiedPhase3bLedger } from './phase3b-resolution.mjs';

const read = async (name, fallback) =>
  fs
    .readFile(name, 'utf8')
    .then(JSON.parse)
    .catch((e) => {
      if (e.code === 'ENOENT') return fallback;
      throw e;
    });
const context = (f) => ({
  ...f,
  area: f.area || f.feature,
  journey: f.journey || 'Operational seller lifecycle',
  business_impact:
    f.business_impact ||
    'Seller may misinterpret or be unable to complete the recorded operational workflow.',
});

export async function writePhase3Report(report) {
  // Reporting/triage can add evidence after execution; preserve the execution
  // timestamp and give each report revision its own immutable archive identity.
  report.execution_generated_at ||= report.generated_at;
  report.generated_at = new Date().toISOString();
  const prior = await read('docs/qa/defect-backlog.json', []);
  const tests = report.reports.flatMap((r) => r.tests);
  const api = report.reports.flatMap((r, index) =>
    (r.api_results?.tests || []).map((t) => ({
      ...t,
      project: ['desktop', 'mobile'][index],
      evidence: `tmp/qa-agent/${report.cleanup[index].database.match(/qa([a-f0-9]{16})_test/)[1]}/api-results.json`,
    })),
  );
  report.api_tests = api;
  report.executive_summary.api_passed = api.filter((r) => r.status === 'PASS').length;
  report.executive_summary.api_failed = api.filter((r) => r.status === 'FAIL').length;
  report.executive_summary.api_errors = api.filter((r) => r.status === 'ERROR').length;
  report.findings = report.findings
    .filter((f) => !f.id.startsWith('QA-P3-API-'))
    .map((f) =>
      context({
        ...f,
        id: f.id.startsWith('QA-P3-')
          ? f.id
          : `QA-P3-ASSERT-${f.id.match(/QA-RUN-([A-Z]+)-/)[1]}-${f.feature.split(' ')[0]}`,
        reproduction_steps: ['npm.cmd run qa:phase3', ...f.reproduction_steps.slice(1)],
      }),
    );
  report.confirmed_bugs = report.confirmed_bugs.map((f) =>
    context({
      ...f,
      id: f.id.replace('QA-AXE-', 'QA-P3-AXE-'),
      reproduction_steps: ['npm.cmd run qa:phase3', ...f.reproduction_steps.slice(1)],
    }),
  );
  for (const t of api.filter((r) => !['PASS', 'SKIP'].includes(r.status))) {
    report.findings.push(
      finding(
        `QA-P3-API-${t.project.toUpperCase()}-${t.id.toUpperCase().replaceAll('_', '-')}`,
        context({
          feature: t.id,
          route: 'See canonical route and API artifact in phase3_api.py',
          type: 'SUSPECTED_DEFECT',
          severity: 'MAJOR',
          priority: 'P1',
          expected:
            'Persisted canonical operational scenario satisfies its explicit financial/security/lifecycle assertions.',
          actual: t.error || t.error_type,
          reproduction_steps: ['npm.cmd run qa:phase3', t.id],
          evidence: [{ name: 'Persisted API assertions', path: t.evidence }],
          confidence: 'SUSPECTED',
          suggested_fix:
            'Review captured canonical response and source contract before authorizing a production correction.',
          retest_status: 'NOT_RETESTED',
        }),
      ),
    );
  }
  const resolution = await verifiedResolutionLedger(report);
  const phase3bResolution = await verifiedPhase3bLedger(report);
  const closedIds = new Set([...resolution.ids, ...phase3bResolution.ids]);
  const reviewed = (await read('docs/qa/phase-3-reviewed-findings.json', [])).map((f) =>
    closedIds.has(f.id)
      ? {
          ...f,
          retest_status: 'PASS',
        }
      : f,
  );
  report.resolved_findings = reviewed.filter((f) => closedIds.has(f.id));
  report.remediation_evidence = resolution.evidence;
  report.phase3b_remediation_evidence = phase3bResolution.evidence;
  report.reviewed_findings = reviewed;
  const reviewedIds = new Set(reviewed.map((f) => f.id));
  report.confirmed_bugs = report.confirmed_bugs.filter((f) => !reviewedIds.has(f.id));
  report.confirmed_bugs.push(
    ...reviewed.filter(
      (f) => f.confidence === 'CONFIRMED' && f.type !== 'MISSING_FLOW' && !closedIds.has(f.id),
    ),
  );
  report.product_gaps = reviewed.filter((f) => f.type === 'MISSING_FLOW');
  report.accessibility_review_tasks = reviewed.filter(
    (f) => f.type === 'ACCESSIBILITY' && f.confidence === 'SUSPECTED',
  );
  report.executive_summary.confirmed_defect_roots = report.confirmed_bugs.length;
  report.executive_summary.product_gaps = report.product_gaps.length;
  report.executive_summary.manual_accessibility_tasks = report.accessibility_review_tasks.length;
  report.usability_findings = report.usability_findings.map(context);
  const scans = tests.flatMap((t) => t.axe || []);
  report.manual_accessibility_reviews = scans.flatMap((s) =>
    s.incomplete.map((r) => ({ route: s.route, state: s.state, ...r })),
  );
  report.mobile_contrast_review = [];
  for (const test of tests.filter((t) => t.project === 'mobile')) {
    for (const evidence of test.evidence.filter((e) => e.name.startsWith('obscured-table-'))) {
      const data = await read(evidence.path, null);
      if (!data) continue;
      const incomplete = data.diagnostics.filter((d) => d.incomplete.length);
      report.mobile_contrast_review.push({
        state: evidence.name,
        evidence: evidence.path,
        targets: data.targets.length,
        examined: data.diagnostics.length,
        axe_passes_after_scrolling: data.diagnostics.filter((d) =>
          d.passes.includes('color-contrast'),
        ).length,
        confirmed_violations: data.diagnostics.filter((d) => d.violations.length).length,
        remaining_incomplete: incomplete,
        status: incomplete.length
          ? 'OPEN_MANUAL_REVIEW'
          : data.targets.length
            ? 'SCROLLED_TARGETS_VERIFIED_BY_AXE'
            : 'NO_CURRENT_INCOMPLETE_TARGETS_NOT_HISTORICAL_CLOSURE',
      });
    }
  }
  await fs.writeFile(
    'docs/qa/phase-3-mobile-contrast-review.json',
    JSON.stringify(
      {
        scope:
          'Established axe engine after real scrolling, supplemental to full-document scans; repeated states are not unique defect counts.',
        states: report.mobile_contrast_review,
      },
      null,
      2,
    ),
  );
  const resolutions = await read('docs/qa/remediation-retest.json', { resolutions: [] });
  const resolved = new Set(
    resolutions.resolutions.filter((r) => r.status === 'RESOLVED').map((r) => r.id),
  );
  report.inherited_open_findings = prior
    .filter(
      (f) =>
        !f.id.startsWith('QA-P3-') &&
        !resolved.has(f.id) &&
        !closedIds.has(f.id) &&
        f.retest_status !== 'PASS',
    )
    .map(context);
  report.gaps = [
    'Real provider, external publication, payment/refund dispatch, supplier contact and marketplace authorization are intentionally not executed.',
    'Order creation/lifecycle uses the actual synthetic-provider API; the UI is a read-only projection, not a seller order-entry or refund-dispatch authority.',
    'Action Center supports local signal acknowledge/snooze/resolve/reopen, not a complete persisted approval/rejection/execution workflow. Its request-action response is not proof of an executed or durably approved action.',
    'Independent fresh-process database reconstruction is tested; database service outage and publishing-worker restart remain NOT EXECUTED to avoid interacting with unrelated runtime/backup services.',
    'Browser failures/timeouts and committed-response loss use explicit network interception, not a claim of real infrastructure failure or worker recovery.',
    'ORM metadata fixtures do not validate the complete migration chain. No migration certification is claimed.',
    'No applicable GST treatment, real marketplace fee schedule, bank reconciliation or complete net-profit accounting is inferred from hypothetical synthetic evidence.',
    'Keyboard checks are bounded; screen-reader/assistive-technology certification and comprehensive modal focus-trap testing remain unexecuted.',
  ];
  const newFindings = [
    ...report.confirmed_bugs,
    ...report.findings,
    ...report.usability_findings,
    ...reviewed.filter((f) => !closedIds.has(f.id)),
  ];
  const dedup = new Map(
    [...report.inherited_open_findings, ...newFindings].map((f) => [f.id, context(f)]),
  );
  await fs.writeFile(
    'docs/qa/defect-backlog.json',
    JSON.stringify(
      [...dedup.values()].sort((a, b) => a.priority.localeCompare(b.priority)),
      null,
      2,
    ),
  );
  await fs.writeFile('docs/qa/phase-3-report.json', JSON.stringify(report, null, 2));
  const table = (rows) => rows.map((t) => `| ${t.id} | ${t.project} | ${t.status} |`).join('\n');
  await fs.writeFile(
    'docs/qa/phase-3-report.md',
    `# QA Phase 3: actual operational execution\n\n${report.generated_at}. **${report.status}**. Full application certification remains incomplete.\n\n## Results\n\nBrowser ${report.executive_summary.passed} passed / ${report.executive_summary.failed} failed; persisted API ${report.executive_summary.api_passed} passed / ${report.executive_summary.api_failed} failed / ${report.executive_summary.api_errors} errors.\n\n| Browser scenario | Viewport | Result |\n| --- | --- | --- |\n${table(tests)}\n\n| Persisted scenario | Installation | Result |\n| --- | --- | --- |\n${table(api)}\n\n## Confirmed accessibility findings\n\n${report.confirmed_bugs.map((f) => `- **${f.id}** (${f.priority}): ${f.actual}`).join('\n') || 'None recorded.'}\n\n## Failed assertions: triage required\n\n${report.findings.map((f) => `- **${f.id}** (${f.confidence}, ${f.priority}): ${f.actual.replaceAll('\n', ' ').slice(0, 1800)}`).join('\n') || 'None.'}\n\n## Reviewed defects / gaps\n\n${reviewed.map((f) => `- **${f.id}** (${f.confidence}, ${f.priority}): ${f.actual} Impact: ${f.business_impact} Proposed correction: ${f.suggested_fix}`).join('\n') || 'Review pending; do not infer a production defect solely from a failed locator.'}\n\n## Preserved findings\n\n${report.inherited_open_findings.length} inherited open findings retained. Original Phase 1/2 reports, resolutions and SHA256 history are not overwritten. See [backlog](defect-backlog.json).\n\n## Accessibility investigation\n\n${scans.length} full-document axe state scans; ${scans.reduce((n, s) => n + s.violations.length, 0)} violation occurrences and ${report.manual_accessibility_reviews.length} incomplete occurrences. Original mobile tables are additionally investigated using real scrolling and targeted axe contrast diagnostics; those do not replace full-document scans. No rules or thresholds were relaxed. No full WCAG compliance claim.\n\n## Evidence\n\n${tests.map((t) => `- ${t.project} ${t.id}: ${t.evidence.map((e) => e.path).join(', ')}`).join('\n')}\n\n## Gaps and blocked work\n\n${report.gaps.map((g) => '- ' + g).join('\n')}\n\n## Cleanup\n\n${report.cleanup.map((c) => `- ${c.project}: ${c.status}; child exit ${c.child_exit}; database absent ${c.proof?.database_absent === true}`).join('\n')}\n\nOnly disposable synthetic state was used. No automatic production fixes, permanent/golden data changes, marketplace/provider calls, commercial actions, Docker changes, commits, pushes or branches.\n\n## Reproduce\n\nSet the local current-shell QA_DATABASE_ADMIN_URL described in architecture.md, then run npm.cmd run qa:phase3. See [Phase 3 validation](phase-3-validation.md) for independent regression results, exact commands, triage and remediation/Phase 4 priorities.\n`,
  );
  const markdown = await fs.readFile('docs/qa/phase-3-report.md', 'utf8');
  await fs.writeFile(
    'docs/qa/phase-3-report.md',
    markdown
      .replace(
        'No automatic production fixes, permanent/golden data changes',
        'Only explicitly scoped remediation was implemented. No permanent/golden data changes',
      )
      .replace(
        '## Confirmed accessibility findings',
        '## Confirmed application and accessibility defects',
      ) +
      (closedIds.size
        ? `\n## Evidence-gated bounded remediation\n\n${[...closedIds].join(', ')} independently retested and resolved. Reviewed actual-behavior text above is retained historical baseline, not a claim that a resolved defect still reproduces. See [Phase 3A ledger](phase-3a-resolution.json), [Phase 3B ledger](phase-3b-resolution.json), and [current validation](phase-3b-validation.md). Excluded findings and incomplete accessibility review remain open; application certification remains INCOMPLETE.\n`
        : ''),
  );
  const coverage = await fs.readFile('docs/qa/coverage-matrix.md', 'utf8');
  await fs.writeFile(
    'docs/qa/coverage-matrix.md',
    coverage.replace(/\n<!-- PHASE3 -->[\s\S]*$/, '') +
      '\n<!-- PHASE3 -->\n## Phase 3 actual operational coverage\n\nPrior executed coverage and resolutions remain in [Phase 1 retest](phase-1-retest-report.json), [Phase 2](phase-2-coverage.json) and [remediation](remediation-retest.json). The source inventory is not proof of execution.\n\n| Scenario | Viewport | Status |\n| --- | --- | --- |\n' +
      table(tests) +
      '\n\n| Persisted scenario | Installation | Status |\n| --- | --- | --- |\n' +
      table(api) +
      '\n\n### Unexecuted/blocked scope\n\n' +
      report.gaps.map((g) => '- ' + g).join('\n') +
      '\n',
  );
  await fs.writeFile(
    'docs/qa/phase-3-coverage.json',
    JSON.stringify(
      {
        browser: tests.map((t) => ({
          id: t.id,
          project: t.project,
          status: t.status,
          routes: t.signals?.visited_routes,
        })),
        api,
        gaps: report.gaps,
      },
      null,
      2,
    ),
  );
}
