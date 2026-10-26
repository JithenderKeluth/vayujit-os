import fs from 'node:fs/promises';
import { finding } from './safety.mjs';

export async function writePhase2Report(report) {
  const phase1 = JSON.parse(await fs.readFile('docs/qa/initial-report.json', 'utf8'));
  const api = report.reports.flatMap((r, index) =>
    (r.api_results?.tests || []).map((t) => ({ ...t, project: ['desktop', 'mobile'][index] })),
  );
  const addContext = (entry, journey = 'Phase 2 seller journey') => ({
    ...entry,
    area: entry.area || entry.feature,
    journey: entry.journey || journey,
    business_impact:
      entry.business_impact ||
      (entry.type === 'ACCESSIBILITY'
        ? 'Seller may be unable to perceive or navigate evidence and approval states.'
        : 'May prevent trustworthy, repeatable seller decisions; inspect the specific evidence before remediation.'),
  });
  report.findings = report.findings
    .filter((f) => !f.id.startsWith('QA-P2-API-'))
    .map((f) =>
      addContext({
        ...f,
        id: f.id.startsWith('QA-P2-')
          ? f.id
          : `QA-P2-ASSERT-${f.id.match(/QA-RUN-([A-Z]+)-/)[1]}-${f.feature.split(' ')[0]}`,
        reproduction_steps: ['npm.cmd run qa:phase2', ...f.reproduction_steps.slice(1)],
      }),
    );
  report.usability_findings = report.usability_findings.map((f) => addContext(f));
  const reviewed = await fs
    .readFile('docs/qa/phase-2-reviewed-findings.json', 'utf8')
    .then(JSON.parse)
    .catch((error) => {
      if (error.code === 'ENOENT') return [];
      throw error;
    });
  const reviewedIds = new Set(reviewed.map((f) => f.id));
  report.confirmed_bugs = report.confirmed_bugs.filter((f) => !reviewedIds.has(f.id));
  report.usability_findings = report.usability_findings.filter((f) => !reviewedIds.has(f.id));
  report.confirmed_bugs.push(
    ...reviewed.filter(
      (f) =>
        f.confidence === 'CONFIRMED' &&
        !(
          f.retest_status === 'PASS' &&
          ((f.id === 'QA-P2-FIN-001' &&
            api.filter((t) => t.id.startsWith('test_06_')).length === 2 &&
            api.filter((t) => t.id.startsWith('test_06_')).every((t) => t.status === 'PASS')) ||
            (f.id === 'QA-P2-DEC-001' &&
              report.reports.flatMap((r) => r.tests).filter((t) => t.id === 'QA-P2-03').length ===
                2 &&
              report.reports
                .flatMap((r) => r.tests)
                .filter((t) => t.id === 'QA-P2-03')
                .every((t) => t.status === 'passed')))
        ) &&
        !report.confirmed_bugs.some((existing) => existing.id === f.id),
    ),
  );
  report.usability_findings.push(
    ...reviewed.filter(
      (f) =>
        f.confidence === 'RECOMMENDATION' &&
        !report.usability_findings.some((existing) => existing.id === f.id),
    ),
  );
  report.confirmed_bugs = report.confirmed_bugs.map((f) =>
    addContext({
      ...f,
      id: f.id.replace('QA-AXE-', 'QA-P2-AXE-'),
      retest_status: f.retest_status === 'PASS' ? 'FAIL' : f.retest_status,
      reproduction_steps: ['npm.cmd run qa:phase2', ...f.reproduction_steps.slice(1)],
    }),
  );
  const failedApi = api
    .filter((t) => !['PASS', 'SKIP'].includes(t.status))
    .map((t) =>
      finding(
        `QA-P2-API-${t.project.toUpperCase()}-${t.id.toUpperCase().replaceAll('_', '-')}`,
        addContext({
          feature: t.id,
          route: 'See api-results.json and phase2-manifest.json',
          type:
            t.id.includes('stale') || t.id.includes('changed_readiness')
              ? 'CALCULATION'
              : 'SUSPECTED_DEFECT',
          severity: 'MAJOR',
          priority: 'P1',
          expected: 'Canonical persisted workflow and independent Decimal assertions pass.',
          actual: t.error || t.error_type,
          reproduction_steps: ['npm.cmd run qa:phase2', t.id],
          evidence: report.cleanup
            .filter((c) => c.project === t.project)
            .map((c) => ({
              name: 'API evidence',
              path: `tmp/qa-agent/${c.database.match(/qa([a-f0-9]{16})_test/)[1]}/api-results.json`,
            })),
          confidence: 'SUSPECTED',
          suggested_fix:
            'Triage canonical contract and captured data; no automatic production repair.',
          retest_status: 'NOT_RETESTED',
        }),
      ),
    );
  report.api_tests = api;
  report.executive_summary.api_passed = api.filter((t) => t.status === 'PASS').length;
  report.executive_summary.api_failed = api.filter((t) => t.status === 'FAIL').length;
  report.executive_summary.api_errors = api.filter((t) => t.status === 'ERROR').length;
  report.findings.push(...failedApi);
  report.inherited_phase1_findings = [
    ...phase1.confirmed_bugs,
    ...phase1.findings,
    ...phase1.usability_findings,
  ];
  report.phase1_status = phase1.status;
  report.gaps = [
    'Manual synthetic ProductOpportunity candidates are authored through the canonical API; real product web discovery is NOT executed or claimed.',
    'Supplier LOCAL_FIXTURE evidence is synthetic/unverified, not live supplier proof. Switching suppliers/multiple-supplier comparisons remain unexecuted.',
    'GST and marketplace fee schedules are not inferred. Explicit hypothetical fee arithmetic and unknown tax exclusions are tested; jurisdictional tax certification is not claimed.',
    'Metadata-created disposable schemas retain the Phase 1 migration limitation; no migration PASS is claimed.',
    'Full order/refund/settlement net-profit lifecycle and cross-installation isolation remain Phase 3 gaps.',
  ];
  await fs.writeFile('docs/qa/phase-2-report.json', JSON.stringify(report, null, 2));
  const tests = report.reports.flatMap((r) => r.tests);
  const priority = [
    ...report.inherited_phase1_findings,
    ...report.confirmed_bugs,
    ...report.findings,
    ...report.usability_findings,
  ].sort((a, b) => a.priority.localeCompare(b.priority));
  await fs.writeFile('docs/qa/defect-backlog.json', JSON.stringify(priority, null, 2));
  await fs.writeFile(
    'docs/qa/phase-2-report.md',
    `# QA Agent Phase 2 — actual execution\n\n${new Date(report.generated_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST. **${report.status}**. No comprehensive application certification.\n\n## Results\n\nBrowser: ${tests.filter((t) => t.status === 'passed').length} passed / ${tests.filter((t) => t.status === 'failed' || t.status === 'timedOut').length} failed / ${tests.filter((t) => t.status === 'skipped').length} skipped. API: ${api.filter((t) => t.status === 'PASS').length} passed / ${api.filter((t) => t.status === 'FAIL').length} failed / ${api.filter((t) => t.status === 'ERROR').length} errors.\n\n| Scenario | Viewport | Result | Evidence |\n| --- | --- | --- | --- |\n${tests.map((t) => `| ${t.id} | ${t.project} | ${t.status} | ${t.evidence.map((e) => e.path).join('<br>')} |`).join('\n')}\n\n## Failed assertions / confirmed automated findings\n\n${[...report.findings, ...report.confirmed_bugs].map((f) => `- **${f.id}** (${f.confidence}, ${f.priority}): ${f.actual.replaceAll('\n', ' ').slice(0, 1600)}. Impact: ${f.business_impact}`).join('\n') || 'None recorded.'}\n\n## Preserved history\n\n${report.inherited_phase1_findings.length} Phase 1 findings retained unchanged in initial-report.json. Not silently closed. [Prioritized backlog](defect-backlog.json).\n\n## Gaps and blocked segments\n\n${report.gaps.map((g) => '- ' + g).join('\n')}\n\n## Safety / cleanup\n\n${report.cleanup.map((c) => `- ${c.project}: ${c.status}; ${c.database}; absent=${c.proof?.database_absent === true}`).join('\n')}\n\nNo permanent/golden database writes, live marketplace/provider calls, supplier contacts, publishing, payments, production fixes, commits or pushes.\n\n## Reproduce\n\nSet the current-shell QA_DATABASE_ADMIN_URL as documented in architecture.md, then run npm.cmd run qa:phase2. Separate suites: npm.cmd run qa:unit; python -m unittest discover -s qa/unit; npm.cmd run test:web.\n\n## Next phase\n\nPhase 3: migration-driven fixtures, supplier switching, financial/order/refund/settlement oracles, cross-installation IDs and broader keyboard coverage. Production remediation of found defects requires separate authorization.\n`,
  );
  const ledger = JSON.parse(await fs.readFile('docs/qa/executed-coverage.json', 'utf8'));
  const generatedMarkdown = await fs.readFile('docs/qa/phase-2-report.md', 'utf8');
  await fs.writeFile(
    'docs/qa/phase-2-report.md',
    generatedMarkdown.replace(
      'payments, production fixes, commits or pushes.',
      'payments, commits or pushes. Authorized in-scope code remediation is documented separately in phase-2-remediation-validation.md.',
    ),
  );
  const scans = tests.flatMap((t) => t.axe || []);
  await fs.appendFile(
    'docs/qa/phase-2-report.md',
    '\n## Persisted API and financial scenario ledger\n\n' +
      '| Scenario | Installation | Result |\n| --- | --- | --- |\n' +
      api.map((t) => `| ${t.id} | ${t.project} | ${t.status} |`).join('\n') +
      '\n\n## Usability recommendations (not confirmed functional bugs)\n\n' +
      (report.usability_findings
        .map(
          (f) =>
            `- **${f.id}** (${f.confidence}, ${f.priority}): ${f.actual} Suggested correction: ${f.suggested_fix}`,
        )
        .join('\n') || 'None recorded.') +
      `\n\n## Accessibility scope\n\n${scans.length} actual axe scans; ${scans.reduce((n, s) => n + s.violations.length, 0)} rule/state occurrences; ${scans.reduce((n, s) => n + s.incomplete.length, 0)} incomplete rule/state occurrences retained for manual review. ` +
      'No rule was disabled. Automated scans do not establish full WCAG compliance. Functional steps may have passed even when the scenario fails accessibility. ' +
      'See [Phase 2 architecture and exact Windows commands](phase-2-architecture.md) and [validation and triage](phase-2-validation.md).\n',
  );
  const phase2Routes = [...new Set(tests.flatMap((t) => t.signals?.visited_routes || []))];
  const coverage = await fs.readFile('docs/qa/coverage-matrix.md', 'utf8');
  await fs.writeFile(
    'docs/qa/coverage-matrix.md',
    coverage.replace(/\n<!-- PHASE2 -->[\s\S]*$/, '') +
      '\n<!-- PHASE2 -->\n## Phase 2 executed coverage\n\n' +
      'The source inventory above is not an execution ledger. Phase 1 execution remains in [executed-coverage.json](executed-coverage.json). ' +
      'The following rows are actual Phase 2 scenarios, not comprehensive page coverage.\n\n' +
      '| Scenario | Viewport | Status |\n| --- | --- | --- |\n' +
      tests.map((t) => `| ${t.title} | ${t.project} | ${t.status} |`).join('\n') +
      '\n\n| Persisted API / financial scenario | Fixture installation | Status |\n| --- | --- | --- |\n' +
      api.map((t) => `| ${t.id} | ${t.project} | ${t.status} |`).join('\n') +
      '\n\n### Explicit gaps\n\n' +
      report.gaps.map((g) => '- ' + g).join('\n') +
      '\n',
  );
  await fs.writeFile(
    'docs/qa/phase-2-coverage.json',
    JSON.stringify(
      { phase1: ledger, phase2_routes: phase2Routes, api_scenarios: api, gaps: report.gaps },
      null,
      2,
    ),
  );
}
