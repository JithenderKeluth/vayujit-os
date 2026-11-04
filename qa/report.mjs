import fs from 'node:fs/promises';

export function markdown(report) {
  const tests = report.reports.flatMap((item) => item.tests);
  const localTime = new Date(report.generated_at).toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
  });
  const item = (finding) =>
    `### ${finding.id}\n\n${finding.priority} / ${finding.severity} / ${finding.confidence}; route: ${finding.route}.\n\nExpected: ${finding.expected}\n\nActual: ${finding.actual}\n\nReproduce: ${finding.reproduction_steps.join(' → ')}\n\nSuggested fix: ${finding.suggested_fix}\n\nRetest: ${finding.retest_status}. Evidence: ${finding.evidence.map((entry) => entry.path).join(', ')}\n`;
  const summaries = tests.map(
    (test) =>
      `| ${test.id} | ${test.project} | ${test.status.toUpperCase()} | ${test.duration_ms} | ${test.evidence.map((entry) => entry.path).join('<br>')} |`,
  );
  const visited = [...new Set(tests.flatMap((test) => test.signals?.visited_routes || []))];
  const axe = tests.flatMap((test) =>
    (test.axe || []).map((scan) => ({ ...scan, project: test.project })),
  );
  return `# QA Agent Phase 1 — executed report

Generated ${localTime} IST (${report.generated_at}).

## Executive summary

Classification: **${report.status}**. QA foundation is implemented; application release certification is not implied.

- Browser tests: ${report.executive_summary.passed} passed, ${report.executive_summary.failed} failed, ${tests.filter((test) => test.status === 'skipped').length} skipped; ${tests.length} total.
- ${report.confirmed_bugs.length} recorded axe rule findings (viewport/state occurrences, not necessarily distinct root causes).
- ${report.findings.length} assertion-failure records requiring triage; ${report.usability_findings.length} subjective usability recommendations.
- This QA execution makes no external provider calls or marketplace executions. Application remediation preceding a retest is documented separately.

## Coverage matrix

${report.coverage.inventoried_routes} Angular route declarations; ${report.coverage.api_declarations} static API declarations; ${report.coverage.models} model tables; ${report.coverage.existing_backend_test_files} backend test files; ${report.coverage.existing_angular_spec_files} Angular spec files inventoried. Runtime OpenAPI operations: ${report.coverage.runtime_api_operations.filter(Number.isFinite).join(', ') || 'NOT_AVAILABLE'}.

See [all route/spec coverage](coverage-matrix.md), [all API/model/service declarations](application-inventory.json), [executed route ledger](executed-coverage.json), and [structured run evidence](initial-report.json). ${visited.length} unique route paths were visited. A visit is not full feature coverage. Historical tests were inventoried, not all rerun.

| Scenario | Viewport | Result | Duration ms | Local evidence (ignored by Git) |
| --- | --- | --- | --- | --- |
${summaries.join('\n')}

## Confirmed automated accessibility findings

${report.confirmed_bugs.map(item).join('\n') || 'None recorded; do not infer unscanned states are accessible.'}

## Suspected defects / failed assertions

These can overlap confirmed axe findings. A failed test is not automatically a functional product defect.

${report.findings.map(item).join('\n') || 'None recorded.'}

## Usability recommendations

${report.usability_findings.map(item).join('\n') || 'None recorded.'}

## Accessibility and keyboard scope

${axe.length} real Chrome axe scans; ${axe.reduce((n, scan) => n + scan.violations.length, 0)} rule occurrences; ${axe.reduce((n, scan) => n + scan.incomplete.length, 0)} incomplete rule/state occurrences retained for manual review. No rules were disabled. Critical/serious findings fail the scenario even when soft assertions allow later evidence collection. Keyboard checks cover Tab/Shift+Tab during owner setup, not all dialogs or assistive technology. This does not certify WCAG conformance.

## Missing flows / blocked tests

See [journeys and phased architecture](architecture.md). Full discovery → HUMAN selection → supplier → due diligence → economics, inventory/order/financial Decimal oracles, private-media, marketplace controls, cross-installation foreign IDs and desktop Electron remain pending. Real providers and all external execution are deliberately forbidden, not unblocked by test fixtures.

Fresh disposable schemas are created from canonical ORM metadata, not a migration replay. Health-ready output is attached; no fake Alembic head is stamped. Migration readiness can therefore be unavailable and is not certified. Original PC-first backup/restore certification remains untouched.

## Disposable cleanup

${report.cleanup.map((entry) => `- ${entry.project}: ${entry.status}; ${entry.database}; child exit ${entry.child_exit}; verified absent=${entry.proof?.database_absent || false}.`).join('\n')}

Only fresh token-matched QA databases are eligible for removal. Private synthetic media/evidence folders remain locally under ignored tmp/qa-agent. No shared Docker resources were changed.

## Runtime blockers

${
  report.reports
    .filter((entry) => entry.blocker)
    .map((entry) => entry.blocker)
    .join('\n') ||
  'No runner startup blocker in this attempt. Failing assertions and remaining scope above remain open.'
}

## Next implementation phase

${report.next_phase}
`;
}

export async function writeReport(report, stem = 'initial-report') {
  if (!['initial-report', 'phase-1-retest-report'].includes(stem))
    throw new Error('QA_REPORT_TARGET_DENIED');
  const reviewed = await fs
    .readFile('docs/qa/review-findings.json', 'utf8')
    .then(JSON.parse)
    .catch(() => []);
  const known = new Set(report.usability_findings.map((entry) => entry.id));
  report.usability_findings.push(...reviewed.filter((entry) => !known.has(entry.id)));
  await fs.writeFile(`docs/qa/${stem}.json`, JSON.stringify(report, null, 2));
  await fs.writeFile(`docs/qa/${stem}.md`, markdown(report));
}

if (process.argv[1]?.endsWith('report.mjs')) {
  await writeReport(JSON.parse(await fs.readFile('docs/qa/initial-report.json', 'utf8')));
}
