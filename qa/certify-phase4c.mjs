// Consolidated audit, not an authority to waive findings or authorize launch.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';

const read = async (file) => JSON.parse(await fs.readFile(file, 'utf8'));
const hash = async (file) =>
  crypto
    .createHash('sha256')
    .update(await fs.readFile(file))
    .digest('hex');
const write = async (name, value) =>
  fs.writeFile(
    'docs/qa/' + name,
    typeof value === 'string' ? value : JSON.stringify(value, null, 2),
  );
const table = (head, rows) =>
  '| ' +
  head.join(' | ') +
  ' |\n| ' +
  head.map(() => '---').join(' | ') +
  ' |\n' +
  rows
    .map(
      (r) =>
        '| ' +
        r.map((v) => String(v).replaceAll('|', '\\|').replaceAll('\n', ' ')).join(' | ') +
        ' |',
    )
    .join('\n') +
  '\n';
const baseline = await read('docs/qa/phase-4c-baseline.json');
const preservation = await Promise.all(
  Object.entries(baseline.sha256).map(async ([file, sha]) => ({
    file,
    unchanged: (await hash(file)) === sha,
  })),
);
const backlog = await read('docs/qa/defect-backlog.json');
const open = backlog.filter((f) => f.retest_status !== 'PASS');
if (open.length !== 12) throw new Error('QA_AUDIT_BASELINE_FINDING_COUNT_CHANGED');
const execution = await read('docs/qa/phase-4c-execution.json');
const inventory = await read('docs/qa/phase-4c-source-inventory.json');
const oldSurface = await read('docs/qa/phase-4-surface-inventory.json');
const quality = await read('docs/qa/phase-4c-quality.json');
const prior = await read('docs/qa/phase-4b-resolution.json');
const oldProof = await Promise.all(
  Object.entries(prior.source_hashes).map(async ([file, sha]) => ({
    file,
    matches: (await hash(file)) === sha,
  })),
);
const policy = {
  'QA-UX-CURRENCY-DESKTOP': [
    'CONDITIONALLY DEFERRABLE — OWNER DECISION',
    'Catalog creation',
    'Accidental USD pricing can invalidate Indian-seller inputs.',
    'Require an owner-confirmed INR entry checklist until a currency-preference change is separately approved.',
    'Desktop create/edit/reload INR and explicit currency confirmation; observation is not closure.',
  ],
  'QA-UX-CURRENCY-MOBILE': [
    'CONDITIONALLY DEFERRABLE — OWNER DECISION',
    'Catalog creation',
    'Same currency risk on mobile; not a second independent monetary defect.',
    'Same INR confirmation policy, with mobile usability acceptance.',
    'Repeat mobile create/edit/reload with INR; do not infer from desktop.',
  ],
  'QA-P2-UX-ECONOMICS-DESKTOP': [
    'CONDITIONALLY DEFERRABLE — OWNER DECISION',
    'Economics/HUMAN decision',
    'Long evidence lists obscure blockers and the safe next decision.',
    'Approve a brief summary/jump-link proposal or witness owner comprehension of the existing screen; retain provenance.',
    'Task-based desktop current/stale/unknown decision review without losing evidence.',
  ],
  'QA-P2-UX-ECONOMICS-MOBILE': [
    'CONDITIONALLY DEFERRABLE — OWNER DECISION',
    'Economics/HUMAN decision',
    '43k-pixel historical fixture makes mobile decisions costly and error-prone.',
    'Desktop-first initial use only if the owner explicitly accepts that limitation; mobile improvement remains open.',
    'Real mobile scrolling, context, summary and decision task at 390px.',
  ],
  'QA-UX-PRE-RUN-MODE-001': [
    'DEFERRABLE FOR OFFLINE USE — OWNER DECISION',
    'Business Agent research',
    'Configured mode, context confirmation and run mode can be mistaken for one authority.',
    'Keep real discovery unavailable until a separately witnessed provider/source-approval journey; approve clearer state copy.',
    'Goal/context/plan/run states with disabled, approval-required, unavailable and permitted read-only modes.',
  ],
  'QA-P3-GAP-001': [
    'BLOCKER IF USED AS SOLE FINANCIAL LEDGER; OTHERWISE OWNER DECISION',
    'Financial reconciliation',
    'A mutable current projection cannot prove exactly what an earlier operational calculation displayed.',
    'Use a separately retained accounting ledger and label projections current/estimated, or approve historical reconstruction requirements. Current source now includes cost IDs; immutability is still missing.',
    'Reopen an earlier pre-refund result with its exact input/cost lineage, or document the accepted current-projection-only scope.',
  ],
  'QA-P3-GAP-002': [
    'BLOCKER FOR GENERIC EXECUTION; ADVISORY-ONLY DEFERRAL REQUIRES OWNER',
    'Action Center HUMAN workflow',
    'Acknowledgement or advisory request is not a durable approval/execution lifecycle.',
    'Retain default-deny and canonical commercial workflows; owner must accept advisory-only scope. Do not build duplicate approval authority.',
    'Approved supported action types must use their canonical stale/replay/HUMAN authorities; generic unsupported actions stay denied.',
  ],
  'QA-P4-API-67A1C8127DF2': [
    'REQUIRED TRIAGE BEFORE MARKETPLACE USE',
    'Marketplace account access',
    'Intermittent account-list 502 could obstruct account operations; root cause not established.',
    'Preserve suspect status. Investigate original proxy/API diagnostics and repeat failure/recovery checks, including migration-backed fixtures.',
    'Explicit repeated authenticated accounts GET, cold startup, injected disconnect/retry and migration-backed context. Non-reproduction is not a fix.',
  ],
  'QA-P4-UX-OVERFLOW-805927FDFA67': [
    'DEFERRABLE IF VIDEO EXCLUDED — OWNER DECISION',
    'Video workspace',
    'Desktop horizontal overflow can hide controls or evidence.',
    'Owner accepts video outside initial-use scope or approves bounded layout correction.',
    '1440px and narrow keyboard/scroll/control-reachability checks; do not hide columns.',
  ],
  'QA-P4-UX-OVERFLOW-4A67C5636387': [
    'DEFERRABLE IF AUTONOMOUS RESEARCH EXCLUDED — OWNER DECISION',
    'Autonomous research workspace',
    'Overflow reduces information/control reachability.',
    'Owner explicitly excludes this workflow or approves bounded layout work; no autonomous execution authorized.',
    'Desktop/mobile document bounds, all columns and keyboard access.',
  ],
  'QA-P4-UX-RESEARCH-LENGTH': [
    'CONDITIONALLY DEFERRABLE — OWNER DECISION',
    'External research/evidence review',
    'Long technical sections increase review friction and source-approval confusion.',
    'Approve minimal summary/progressive disclosure proposal; do not remove provenance or approval checks.',
    'Seller finds evidence gaps, source boundaries and next action in both viewports.',
  ],
  'QA-P4A-A11Y-MANUAL-001': [
    'BLOCKER TO COMPLETE ACCESSIBILITY CERTIFICATION',
    'Cross-application accessibility',
    'Untested/offscreen/conditional content and assistive navigation cannot be certified accessible.',
    'Complete target-by-target manual/assistive review; fix demonstrated violations under separate authorization. No blanket WCAG claim or waiver.',
    'Retain 85 historical rule/state incompletes and the stock numeric cell; expose each relevant node, verify focus/reading order and record remaining unknowns.',
  ],
};
const findings = open.map((f) => {
  const [
    launch_classification,
    journey,
    business_impact,
    required_correction_or_acceptance,
    retest_requirement,
  ] = policy[f.id];
  return {
    ...f,
    audit_journey: journey,
    audit_business_impact: business_impact,
    launch_classification,
    required_correction_or_acceptance,
    retest_requirement,
    owner_acceptance_recorded: false,
    status_changed: false,
  };
});
await write('phase-4c-findings.json', findings);
await write(
  'phase-4c-findings.md',
  '# Phase 4C — twelve open findings\n\nNo finding is closed, downgraded or accepted by this audit. Priority/severity/status remain canonical. Eight UX occurrences are recommendations, not eight proven calculation defects. Product-owner decisions below are REQUIRED, not already granted.\n\n' +
    table(
      [
        'ID / status / severity',
        'Journey and impact',
        'Evidence / expected vs actual',
        'Launch classification',
        'Correction or acceptance rationale',
        'Retest',
      ],
      findings.map((f) => [
        `${f.id}; ${f.retest_status}; ${f.severity}/${f.priority}`,
        `${f.audit_journey}: ${f.audit_business_impact}`,
        `${f.expected} ACTUAL: ${f.actual} [Evidence](${f.evidence[0]?.path?.startsWith('docs/qa/') ? f.evidence[0].path.slice(8) : '../../' + f.evidence[0]?.path})`,
        f.launch_classification,
        f.required_correction_or_acceptance,
        f.retest_requirement,
      ]),
    ),
);

const tests = execution.reports.flatMap((r) => r.tests || []);
const surfaces = [];
const targeted = [];
for (const t of tests)
  for (const e of t.evidence) {
    if (e.name.startsWith('surface-') && !e.name.startsWith('surface-screen-'))
      surfaces.push({
        ...(await read(e.path)),
        test: t.id,
        project: t.project,
        scenario_passed: t.status === 'passed',
        evidence: e.path,
      });
    if (e.name.startsWith('node-review-'))
      targeted.push({ ...(await read(e.path)), test: t.id, project: t.project, evidence: e.path });
  }
const unavailableReasons = (route) => {
  if (route.includes('/trends/'))
    return 'Canonical trend context create/read exists; component source resolves current journey rather than consuming contextId. Exact deep-link context integrity remains untested, not certified by rendering a heading.';
  if (route.includes('/ads/accounts/'))
    return 'Account detail declaration shares accounts section; routeSection source maps it to list. Real account-specific rendering not established; no ad-provider credentials/acquisition.';
  if (route.includes('/ads/campaigns/'))
    return 'Requires canonical persisted advertising campaign/preview and owner context; local creation remains feasible follow-up, not executed by this bounded audit.';
  if (route.includes(':activityId'))
    return 'Requires exact legitimate Video activity/output/version and approvals; a generic checkpoint is not a substitute. Source consumes campaign id but not activityId; exact activity-context integrity needs a separate two-activity test.';
  if (route.includes('/social/posts/'))
    return 'Requires canonical local SocialPost artifact and scope; feasible bounded draft fixture not implemented/executed here. No social dispatch.';
  if (route.includes('/marketplaces/listings/'))
    return 'Needs canonical channel-specific approved artifact/catalog mapping. Generic listing:create is a fake-adapter active-listing operation, not draft creation; first setup rejected it. No fake active ID reused to claim draft certification.';
  if (route.includes('/ai/images/'))
    return 'Requires owned image output/version with private media lineage. No real generation/acquisition; supported deterministic output fixture not executed here.';
  if (route.includes('/ai/') || route.startsWith('/approvals/'))
    return 'Requires canonical generated artifact/version/review context. Do not fabricate approval or substitute product IDs. Existing baseline fixtures did not create it; deterministic preparation is further work.';
  if (route.includes('/destinations/'))
    return 'Safe local mock destination create/read exists; feasible follow-up not executed in this bounded audit. External connector configuration is not required or authorized.';
  if (route.includes('/executions/') || route.includes('/schedules/') || route.includes('/jobs/'))
    return 'Requires canonical persisted job/schedule/execution plus exact approved artifact and local-only connector. No worker execution is enabled to inflate route counts.';
  if (route.includes('/workers/'))
    return 'Requires actual canonical worker registration/heartbeat. No backup/publishing worker started, stopped or fabricated.';
  if (route.includes('/workflows/'))
    return 'Requires a canonical supported workflow run/artifact. Feasible local deterministic workflow is unexecuted, not evidence of missing UI.';
  if (route.includes('/supplier-portfolios/'))
    return 'Canonical owner portfolio/member/assessment authorities exist. Legitimate synthetic selected supplier available, but portfolio create/assessment branch not prepared here; do not use supplier ID as portfolio ID.';
  return 'Inspect exact canonical owner/context prerequisites; no guessed IDs or invented authorization.';
};
const routes = inventory.routes.map((row) => {
  const old = oldSurface.routes.find((r) => r.declaration === row.route);
  const actual = surfaces.filter((s) => s.declaration === row.route);
  const verified = actual.some((s) => s.scenario_passed && s.route_match);
  let classification;
  if (row.kind === 'REDIRECT') classification = 'INTENTIONALLY_UNAVAILABLE_AS_PAGE';
  else if (verified)
    classification = row.route.includes(':')
      ? 'CONTEXT_DEPENDENT_VERIFIED_BOUNDED'
      : 'EXERCISED_VERIFIED_BOUNDED';
  else if (['/setup', '/login'].includes(row.route))
    classification = 'EXERCISED_VERIFIED_BOUNDED_PRIOR_SMOKE';
  else if (row.route === '/marketplaces/inventory/opening')
    classification = 'EXERCISED_VERIFIED_BOUNDED_PRIOR_4B';
  else if (old?.visits?.length)
    classification = row.route.includes(':')
      ? 'CONTEXT_DEPENDENT_PRIOR_VISIT_NOT_WORKFLOW_CERTIFICATION'
      : 'PRIOR_EXERCISED_SURFACE_NOT_FULL_FEATURE';
  else classification = 'CONTEXT_DEPENDENT_UNTESTED';
  return {
    route: row.route,
    kind: row.kind,
    source: row.component,
    classification,
    current_evidence: actual.map((s) => ({
      project: s.project,
      scenario: s.test,
      passed: s.scenario_passed,
      route_match: s.route_match,
      evidence: s.evidence,
    })),
    prior_visit_evidence: old?.visits || [],
    investigation:
      old?.status === 'REQUIRES_UNAVAILABLE_CANONICAL_CONTEXT'
        ? unavailableReasons(row.route)
        : 'Source/DOM visits do not imply every control or complete business workflow is tested.',
  };
});
const artifactRoutes = routes.filter(
  (r) =>
    oldSurface.routes.find((o) => o.declaration === r.route)?.status ===
    'REQUIRES_UNAVAILABLE_CANONICAL_CONTEXT',
);
const counts = (rows) =>
  Object.fromEntries(
    [...new Set(rows.map((r) => r.classification))].map((c) => [
      c,
      rows.filter((r) => r.classification === c).length,
    ]),
  );
const routeAudit = {
  generated_at: new Date().toISOString(),
  earlier_declarations: 154,
  current_declarations: routes.length,
  added: '/marketplaces/inventory/opening',
  classification_counts: counts(routes),
  investigated_artifact_declarations: artifactRoutes.length,
  artifact_classifications: counts(artifactRoutes),
  routes,
  current_control_occurrences: surfaces.reduce((n, s) => n + s.controls.length, 0),
  control_semantics:
    'Repeated DOM control occurrences, not unique requirements or interaction coverage. Explicit assertions in four scenarios only.',
  unreachable_proven: [],
  missing_workflow_proof:
    'See finding ledger; an unvisited route is not proof of absent functionality.',
};
await write('phase-4c-route-control-coverage.json', routeAudit);
await write(
  'phase-4c-route-control-coverage.md',
  '# Phase 4C — route and control reconciliation\n\n154 earlier declarations → ' +
    routes.length +
    ' now; addition: `/marketplaces/inventory/opening`. Six redirects are not application pages. Exact categories are in the JSON; previous surface visits are explicitly not full workflow certification. No declared component is proven unreachable merely because its fixture is unavailable.\n\n## Twenty-six artifact-dependent declarations\n\n' +
    table(
      [
        'Declaration',
        'Disposition',
        'Canonical context / bounded investigation',
        'Current evidence',
      ],
      artifactRoutes.map((r) => [
        r.route,
        r.classification,
        r.investigation,
        r.current_evidence.map((e) => e.evidence).join('; ') ||
          'NOT EXECUTED — retained coverage gap',
      ]),
    ) +
    '\n## All current route declarations\n\n' +
    table(
      ['Route', 'Kind', 'Coverage classification', 'Component'],
      routes.map((r) => [r.route, r.kind, r.classification, r.source]),
    ),
);
const scans = tests.flatMap((t) =>
  (t.axe || []).map((s) => ({ project: t.project, test: t.id, scenario_status: t.status, ...s })),
);
const accessibility = {
  full_document_scans: scans.length,
  violation_rule_state_occurrences: scans.reduce((n, s) => n + s.violations.length, 0),
  incomplete_rule_state_occurrences: scans.reduce((n, s) => n + s.incomplete.length, 0),
  scans,
  targeted,
  historical_manual_item_preserved: 'QA-P4A-A11Y-MANUAL-001',
  wcag_conformance_claimed: false,
};
await write('phase-4c-accessibility.json', accessibility);

const backendDir = process.argv[2];
if (!/^tmp\/qa-agent\/[a-f0-9]{16}$/.test(backendDir || ''))
  throw new Error('QA_AUDIT_BACKEND_EVIDENCE_REQUIRED');
const junit = await fs.readFile(backendDir + '/backend-results.xml', 'utf8');
const suiteTag = junit.match(/<testsuite\s[^>]+>/)?.[0] || '';
const number = (name) => Number(suiteTag.match(new RegExp(' ' + name + '="(\\d+)"'))?.[1] || 0);
const backend = {
  tests: number('tests'),
  failures: number('failures'),
  errors: number('errors'),
  skipped: number('skipped'),
  evidence: backendDir + '/backend-results.xml',
  cleanup: await read(backendDir + '/cleanup.json'),
};
backend.passed = backend.tests - backend.failures - backend.errors - backend.skipped;
const qaNodeLog = await fs.readFile('tmp/qa-agent/phase4c-quality/qa-node.log', 'utf8');
const qaPythonLog = await fs.readFile('tmp/qa-agent/phase4c-quality/qa-python.log', 'utf8');
const angularLog = await fs.readFile('tmp/qa-agent/phase4c-quality/angular.log', 'utf8');
const currentApi = execution.reports.map((r) => ({
  passed: r.api_results?.passed,
  failed: r.api_results?.failed,
  errors: r.api_results?.errors,
  skipped: r.api_results?.skipped,
  exit_code: r.api_results?.process_exit_code,
}));
const summary = {
  generated_at: new Date().toISOString(),
  application_certification: 'INCOMPLETE',
  overall_first_real_operation: 'NO-GO',
  audit_completed: true,
  preserved_inputs: {
    checked: preservation.length,
    changed: preservation.filter((p) => !p.unchanged),
    evidence: 'docs/qa/phase-4c-baseline.json',
  },
  prior_4b_source_reuse: {
    checked: oldProof.length,
    changed: oldProof.filter((p) => !p.matches),
    evidence: 'docs/qa/phase-4b-resolution.json',
  },
  current_execution: execution.executive_summary,
  current_persisted_api: currentApi,
  current_backend: backend,
  current_unit_counts_from_logs: {
    qa_node_passed: Number(qaNodeLog.match(/\bpass (\d+)/)?.[1]) || null,
    qa_python_passed: Number(qaPythonLog.match(/(\d+) passed/)?.[1]) || null,
    angular_passed: Number(angularLog.match(/Tests\s+(\d+) passed/)?.[1]) || null,
    note: 'Actual log counts; exit codes in quality record remain authoritative; no duplicate-requirement claim.',
  },
  quality,
  findings: {
    baseline: backlog.length,
    resolved: backlog.filter((f) => f.retest_status === 'PASS').length,
    still_open: findings.length,
    closed_by_this_audit: 0,
    accepted_by_owner: 0,
  },
  routes: {
    current: routes.length,
    investigated_artifact_declarations: artifactRoutes.length,
    classifications: counts(routes),
    artifact_classifications: counts(artifactRoutes),
  },
  accessibility: {
    scans: scans.length,
    violations: accessibility.violation_rule_state_occurrences,
    incompletes: accessibility.incomplete_rule_state_occurrences,
    targeted_reviews: targeted.length,
    full_wcag: false,
  },
  cleanup: execution.cleanup,
  verdicts: [
    {
      area: 'Application QA',
      status: 'INCOMPLETE',
      evidence:
        'phase-4c-findings.json; phase-4c-route-control-coverage.json; phase-4b-resolution.json',
      reason:
        'Bounded regressions are not whole-application coverage; twelve original findings and untested contexts remain.',
    },
    {
      area: 'Accessibility',
      status: accessibility.violation_rule_state_occurrences ? 'FAIL' : 'INCOMPLETE',
      evidence:
        'phase-4c-accessibility.json; phase-4a-accessibility.json; phase-4b-accessibility.json',
      reason:
        'Remaining manual/assistive/conditional checks; a clean axe subset is not complete WCAG conformance.',
    },
    {
      area: 'Financial safety',
      status: 'INCOMPLETE',
      evidence: backend.evidence + '; phase-2-remediation-validation.md; phase-3b-resolution.json',
      reason:
        'Deterministic synthetic arithmetic/freshness/provenance demonstrated; sole-ledger immutable history, real costs/tax/settlements not certified.',
    },
    {
      area: 'Inventory/order readiness',
      status: 'INCOMPLETE',
      evidence: 'phase-4b-resolution.json; phase-4c-execution.json',
      reason:
        'Opening ledger/replay/concurrency and synthetic order lifecycle pass; genuine marketplace acquisition, fulfillment/reboot/interruption matrix is not certified.',
    },
    {
      area: 'PC-first operational readiness',
      status: 'INCOMPLETE',
      evidence:
        '../seller-os/pc-first-disposable-certification.json; ../seller-os/pc-first-backup-recovery.md',
      reason:
        'Runtime-only historical PASS; encrypted backup/independent restore NOT_RUN or failing, physical independence UNVERIFIED.',
    },
    {
      area: 'Marketplace readiness',
      status: 'NOT CONFIGURED',
      evidence:
        '../seller-os/production-activation-plan.md; ../seller-os/amazon-india-registration-checklist.md; ../seller-os/flipkart-registration-checklist.md',
      reason:
        'No owner account/API onboarding completion evidence; synthetic sandbox accounts are not real seller authorization.',
    },
    {
      area: 'Overall first real operation',
      status: 'NO-GO',
      evidence: 'phase-4c-validation.md',
      reason:
        'Mandatory recovery, physical backup and readiness decisions remain unmet; no waiver granted.',
    },
  ],
  unexecuted: [
    'Live providers and real marketplace registration/OAuth/connectivity',
    'PC-first encrypted backup/restore, physical-disk verification and host reboot',
    'Full migration-backed QA matrix and all historical backend suites',
    'Screen-reader/physical-device/cross-browser/full WCAG review',
    'All remaining artifact-bound routes and every discovered control',
    'Current vulnerability advisory/host security audit',
  ],
};
await write('phase-4c-certification.json', summary);
console.log(
  JSON.stringify({
    status: 'AUDIT_COMPLETE_APPLICATION_INCOMPLETE_NO_GO',
    current_browser: summary.current_execution,
    backend,
    findings: summary.findings,
    routes: summary.routes,
    accessibility: summary.accessibility,
    changed_preserved_inputs: summary.preserved_inputs.changed,
  }),
);
if (preservation.some((p) => !p.unchanged) || oldProof.some((p) => !p.matches))
  process.exitCode = 1;
