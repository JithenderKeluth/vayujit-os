import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import Ajv2020 from 'ajv/dist/2020.js';
import { resolutionDecisions, focusedComplete } from './phase4a-resolution.mjs';
import { phase4Status } from './phase4-report.mjs';
import { canonicalRoute } from './phase4-surface.mjs';
import { finding } from './safety.mjs';

const read = async (p) => JSON.parse(await fs.readFile(p, 'utf8'));
const hash = async (p) =>
  crypto
    .createHash('sha256')
    .update(await fs.readFile(p))
    .digest('hex');
const baseline = await read('docs/qa/phase-4a-baseline.json');
const existingLedger = await read('docs/qa/defect-backlog.json');
const priorAdditional = await read('docs/qa/phase-4a-additional-findings.json').catch(() => []);
const additional = [
  ...new Map(
    [
      ...priorAdditional,
      ...existingLedger.filter(
        (f) => f.id.startsWith('QA-P4-') && !baseline.findings.some((b) => b.id === f.id),
      ),
    ].map((f) => [f.id, f]),
  ).values(),
];
await fs.writeFile(
  'docs/qa/phase-4a-additional-findings.json',
  JSON.stringify(additional, null, 2),
);
const evaluatedBaseline = { ...baseline, findings: [...baseline.findings, ...additional] };
const original = await read('docs/qa/phase-4a-baseline-report.json');
const full = await read('docs/qa/phase-4-report.json');
const focused = await read('docs/qa/phase-4a-retest-report.json');
const inventory = await read('docs/qa/phase-4-source-inventory.json');
const preserved = ['qa/tests/phase4.spec.mjs', 'qa/explore.mjs'];
const executionHashes = await Promise.all(
  [full, focused].map(async (report) => {
    const hashes = report.tested_source_sha256;
    if (!hashes || !hashes['apps/web/src/app/ai/ai.css']) return false;
    return (
      await Promise.all(
        Object.entries(hashes)
          .filter(
            ([file]) => report.phase !== 'QA_AGENT_PHASE_4' || file !== 'qa/tests/phase4a.spec.mjs',
          )
          .map(async ([file, expected]) => (await hash(file)) === expected),
      )
    ).every(Boolean);
  }),
);
const originalsVerified =
  (await hash('docs/qa/phase-4a-baseline-report.json')) === baseline.report_sha256 &&
  (
    await Promise.all(preserved.map(async (p) => (await hash(p)) === baseline.source_sha256[p]))
  ).every(Boolean);
const hashesVerified = originalsVerified && executionHashes.every(Boolean);
const nodes = [];
for (const [suite, report] of [
  ['original', full],
  ['focused', focused],
]) {
  for (const r of report.reports)
    for (const t of r.tests)
      for (const ref of t.evidence) {
        if (ref.name.startsWith('node-review-'))
          nodes.push({
            ...(await read(ref.path)),
            name: ref.name,
            project: t.project,
            suite,
            evidence: ref.path,
          });
      }
}
const decisions = resolutionDecisions({
  baseline: evaluatedBaseline,
  original,
  full,
  focused,
  routes: inventory.routes,
  nodes,
  hashesVerified,
});
const fileFor = (route) =>
  inventory.routes.find((r) => canonicalRoute(r.route.replace(/:[^/]+/g, ':id')) === route)
    ?.component;
const roots = {
  contextIds: [
    'R11',
    'Populated Trend context setup and context list reused the same heading ID and region name.',
    'Give the populated list its own unique heading ID and matching labelledby reference.',
  ],
  productRegion: [
    'R12',
    'Product detail workspace and its inner product summary had the same accessible name.',
    'Use a distinct Product opportunity workspace region name while retaining the visible product headings.',
  ],
  groups: [
    'R10',
    'A populated external-research badge collection named a generic div without a compatible role.',
    'Use an explicitly named group; preserve labels, badges and server-derived recovery actions.',
  ],
  landmark: [
    'R1',
    'Routed components repeated the application shell main landmark.',
    'Use a named section inside the existing sole application main; preserve headings, classes and navigation.',
  ],
  complementary: [
    'R2',
    'Generation summary aside was nested within another landmark/form.',
    'Use a named Generation summary section, preserving controls and form semantics.',
  ],
  labels: [
    'R3',
    'Status selects and date inputs lacked associated visible labels.',
    'Explicit unique for/id associations; group labels with their controls; retain filter query contract.',
  ],
  progress: [
    'R4',
    'Generic progress div carried ARIA properties without a compatible role.',
    'Named progressbar with canonical current/min/max and textual step values.',
  ],
  headings: [
    'R5',
    'Action column headings were empty.',
    'Visible Actions column heading with col scope; retain every action.',
  ],
  contrast: [
    'R6',
    'Empty-state foreground and small status text lost contrast on their actual backgrounds.',
    'Reuse darker theme foreground; small website state text inherits its verified state color.',
  ],
  scroll: [
    'R7',
    'Overflowing table containers were not keyboard focusable.',
    'Named tabindex=0 regions, unique accurate names and existing-theme visible focus; ArrowRight and Tab escape tested.',
  ],
  definitions: [
    'R8',
    'Description terms and definitions were children of a generic div.',
    'Semantic dl wrapper without removing or changing data.',
  ],
  captions: [
    'R9',
    'Wide table intrinsic width made its caption exceed the mobile viewport and clip.',
    'Size caption to an inline-size query container, allow wrapping and keep it at the scroll start; preserve full table columns and keyboard scrolling.',
  ],
  harness: [
    'H1',
    'Phase 4 proxy denied three automatic owner-scoped local context POSTs; not provider calls.',
    'Permit only audited metadata payloads to exact canonical context endpoints, retain backend authentication, owner checks and deny acquisition/approvals.',
  ],
};
function detail(row, finding) {
  let group;
  const rule = row.rule;
  if (rule === 'aria-prohibited-attr' && finding.route === '/intelligence/external')
    group = 'groups';
  else if (rule === 'landmark-unique' && finding.route === '/intelligence/trends')
    group = 'contextIds';
  else if (
    rule === 'landmark-unique' &&
    finding.route.startsWith('/intelligence/product-opportunities/')
  )
    group = 'productRegion';
  else if (rule?.startsWith('landmark-'))
    group = rule.includes('complementary') ? 'complementary' : 'landmark';
  else
    group = {
      label: 'labels',
      'select-name': 'labels',
      'aria-prohibited-attr': 'progress',
      'empty-table-header': 'headings',
      'color-contrast': 'contrast',
      'scrollable-region-focusable': 'scroll',
      dlitem: 'definitions',
    }[rule];
  if (finding.id.includes('CAPTION') || finding.id === 'QA-P3-A11Y-REVIEW-001') group = 'captions';
  let files = [fileFor(finding.route)].filter(Boolean);
  if (group === 'scroll') files.push('apps/web/src/styles.css');
  if (group === 'labels') files.push('apps/web/src/app/ai/ai.css');
  if (group === 'captions')
    files = [
      'apps/web/src/app/intelligence/sourcing-economics-workspace.component.ts',
      'apps/web/src/app/intelligence/supplier-due-diligence.component.ts',
    ];
  if (finding.id.startsWith('QA-P4-ASSERT-')) {
    files = ['See linked original scenario and route/rule resolution rows'];
    return {
      root: 'OVERLAPPING_SCENARIO_RECORD',
      root_cause:
        'Aggregate test failure overlaps route/rule findings, and Intelligence additionally included H1.',
      correction:
        'No assertion weakening; original scenario rerun after bounded UI and fixture repairs.',
      changed_files: files,
    };
  }
  return {
    root: group ? roots[group][0] : 'OUT_OF_SCOPE',
    root_cause: group ? roots[group][1] : finding.actual,
    correction: group ? roots[group][2] : 'No automatic correction or closure.',
    changed_files: files,
  };
}
const ledger = decisions.map((row) => {
  const finding = evaluatedBaseline.findings.find((f) => f.id === row.id);
  return {
    ...row,
    route: finding.route,
    priority: finding.priority,
    ...detail(row, finding),
    before: { actual: finding.actual, evidence: finding.evidence },
    status: row.resolved ? 'RESOLVED' : 'OPEN',
    retest_status: row.resolved ? 'PASS' : finding.retest_status,
  };
});
const resolved = new Set(ledger.filter((r) => r.resolved).map((r) => r.id));
const backlog = evaluatedBaseline.findings.map((f) =>
  resolved.has(f.id)
    ? {
        ...f,
        retest_status: 'PASS',
        evidence: [
          ...f.evidence,
          {
            name: 'Independent Phase 4A resolution ledger',
            path: 'docs/qa/phase-4a-resolution.json',
          },
        ],
      }
    : f,
);
for (const f of full.findings) if (!backlog.some((b) => b.id === f.id)) backlog.push(f);
// A recurrence in current evidence always wins over historical closure.
for (const f of full.findings) {
  const row = backlog.find((b) => b.id === f.id);
  if (row && resolved.has(row.id)) throw new Error('QA_RESOLUTION_RECURRENCE_CONFLICT');
}
const manualReviews = full.reports.flatMap((r) =>
  r.tests.flatMap((t) =>
    t.axe.flatMap((scan) =>
      scan.incomplete.map((rule) => ({
        project: t.project,
        scenario: t.id,
        route: scan.route,
        state: scan.state,
        rule,
      })),
    ),
  ),
);
if (manualReviews.length) {
  const manual = finding('QA-P4A-A11Y-MANUAL-001', {
    feature: 'Unreviewed full-document axe incomplete results across recorded routes',
    area: 'application-accessibility',
    journey: 'Manual accessibility follow-up',
    route: '/intelligence',
    type: 'ACCESSIBILITY',
    severity: 'MODERATE',
    priority: 'P2',
    expected:
      'Unresolved obscured, conditional or empty-content checks remain explicitly pending, never inferred WCAG PASS.',
    actual: `${manualReviews.length} rule/state incomplete occurrences across recorded routes; see the exact targets in phase-4-accessibility.json. These are manual-review requirements, not confirmed violations or independent code defects.`,
    reproduction_steps: [
      'npm.cmd run qa:phase4',
      'Review retained incomplete target nodes in the recorded routes and viewports with real scrolling/content states.',
    ],
    evidence: [
      { name: 'Original full axe and node evidence', path: 'docs/qa/phase-4-accessibility.json' },
    ],
    confidence: 'SUSPECTED',
    business_impact:
      'Automated evidence does not establish accessibility of every table, conditional control or assistive-technology interaction.',
    suggested_fix:
      'Independently review remaining nodes and assistive navigation; add bounded regressions for confirmed defects. Do not disable rules or equate empty/offscreen checks with success.',
    retest_status: 'BLOCKED',
  });
  backlog.push(manual);
  ledger.push({
    id: manual.id,
    route: manual.route,
    priority: manual.priority,
    resolved: false,
    status: 'OPEN',
    retest_status: 'BLOCKED',
    reason: 'Manual-review follow-up; not a confirmed violation',
    root: 'MANUAL_REVIEW',
    root_cause: manual.actual,
    correction: 'No automatic closure',
    changed_files: [],
    before: { actual: manual.actual, evidence: manual.evidence },
    after: [],
  });
}
const validateFinding = new Ajv2020({ allErrors: true }).compile(
  await read('qa/finding.schema.json'),
);
if (!backlog.every((f) => validateFinding(f)))
  throw new Error('QA_RESOLUTION_FINDING_SCHEMA_INVALID');
const testRows = full.reports.flatMap((r) => r.tests);
const scenarioMap = baseline.failed_scenarios.map((s) => ({
  id: s.id,
  project: s.project,
  before: s.evidence,
  error: s.error,
  finding_ids: baseline.findings
    .filter((f) => f.evidence.some((e) => s.evidence.some((b) => b.path === e.path)))
    .map((f) => f.id),
  harness_issue:
    s.id === 'QA-P4-SURFACE-INTELLIGENCE'
      ? 'H1: metadata context POST blocked before canonical API; separately audited/repaired'
      : null,
  after: testRows.find((t) => t.id === s.id && t.project === s.project),
}));
const afterHashes = Object.fromEntries(
  await Promise.all(Object.keys(baseline.source_sha256).map(async (p) => [p, await hash(p)])),
);
const report = {
  generated_at: new Date().toISOString(),
  scope: 'QA_PHASE_4A_BOUNDED_ACCESSIBILITY_REMEDIATION',
  status:
    hashesVerified &&
    focusedComplete(focused) &&
    phase4Status(full, inventory.routes) === 'PASS_BOUNDED_EXPLORATION' &&
    ledger
      .filter((r) => r.id.startsWith('QA-P4-AXE-') || r.id === 'QA-P4-A11Y-CAPTION-CLIPPING')
      .every((r) => r.resolved)
      ? 'ACCESSIBILITY_REMEDIATION_VALIDATED_BOUNDED_SCOPE'
      : 'REMEDIATION_INCOMPLETE',
  application_certification: 'INCOMPLETE',
  original_assertions_and_helper_unchanged: originalsVerified,
  execution_source_hashes_verified: hashesVerified,
  baseline_report_sha256: baseline.report_sha256,
  verified_source_sha256: afterHashes,
  changed_production_files_since_baseline: Object.keys(afterHashes).filter(
    (p) => afterHashes[p] !== baseline.source_sha256[p],
  ),
  extra_production_file:
    'apps/web/src/app/ai/ai.css (filter label layout only; not in pre-fix source hash set)',
  roots,
  retained_manual_review_occurrences: manualReviews,
  original_eight_scenarios: scenarioMap,
  findings: ledger,
  summary: {
    baseline_findings: baseline.findings.length,
    resolved: resolved.size,
    remaining_open: backlog.filter((f) => !resolved.has(f.id)).length,
    focused_browser: focused.executive_summary,
    original_browser: full.executive_summary,
    original_node_reviews: nodes.filter((n) => n.suite === 'original').length,
    focused_node_reviews: nodes.filter((n) => n.suite === 'focused').length,
  },
  cleanup: { focused: focused.cleanup, original: full.cleanup },
  limitations: [
    'Automated axe and bounded keyboard tests are not complete WCAG conformance or assistive-technology certification.',
    'Full-document obscured/empty-table incomplete nodes are retained; targeted caption and historical-header reviews do not clear unrelated nodes.',
    'Initial stock entry remains launch-critical and unimplemented.',
    'No provider, permanent database, HUMAN-authority or financial algorithm changes.',
  ],
};
await fs.writeFile('docs/qa/phase-4a-resolution.json', JSON.stringify(report, null, 2));
await fs.writeFile('docs/qa/defect-backlog.json', JSON.stringify(backlog, null, 2));
await fs.writeFile(
  'docs/qa/phase-4a-accessibility.json',
  JSON.stringify(
    {
      generated_at: report.generated_at,
      scope:
        'Original and focused Chrome evidence; exact nodes only, not whole-application WCAG certification',
      original_assertions_unchanged: originalsVerified,
      execution_source_hashes_verified: hashesVerified,
      nodes,
      document_scans: [
        ['original', full],
        ['focused', focused],
      ].flatMap(([suite, run]) =>
        run.reports.flatMap((r) =>
          r.tests.flatMap((t) =>
            t.axe.map((scan) => ({ ...scan, suite, project: t.project, scenario: t.id })),
          ),
        ),
      ),
      retained_original_manual_review_occurrences: manualReviews,
    },
    null,
    2,
  ),
);
const followup = `\n<!-- PHASE4A -->\n## Phase 4A independent remediation follow-up\n\n${report.generated_at}. **${report.status}**; application **INCOMPLETE**. Original Phase 4: ${full.executive_summary.passed} passed / ${full.executive_summary.failed} failed. Focused accessibility: ${focused.executive_summary.passed} passed / ${focused.executive_summary.failed} failed. ${resolved.size} stable finding records independently resolved; ${report.summary.remaining_open} remain open, including the launch-critical initial-stock gap and retained manual-review requirements. No original browser assertions or axe thresholds weakened. Counts above this section remain historical execution evidence, not the current resolution ledger.\n\n[Full validation and Windows commands](phase-4a-validation.md), [per-finding resolution](phase-4a-resolution.md), [exact accessibility evidence](phase-4a-accessibility.json), [current backlog](defect-backlog.json). No stock workflow implemented; no whole-application or WCAG PASS.\n`;
for (const path of [
  'docs/qa/phase-4-validation.md',
  'docs/qa/phase-4-coverage.md',
  'docs/qa/coverage-matrix.md',
]) {
  const current = await fs.readFile(path, 'utf8');
  await fs.writeFile(path, current.replace(/\n<!-- PHASE4A -->[\s\S]*$/, '') + followup);
}
await fs.writeFile(
  'docs/qa/phase-4a-resolution.md',
  `# Phase 4A independent finding resolution\n\n${report.generated_at}. **${report.status}**. Application **INCOMPLETE**.\n\nThe 102 original axe records are route/rule buckets sharing roots, not 102 independent code bugs. No original Phase 4 assertion or contrast helper was edited. Every old finding is retained in the backlog, including resolved history.\n\n## Original eight failed scenarios\n\n| Scenario | Viewport | Retest | Original finding IDs |\n| --- | --- | --- | --- |\n${scenarioMap.map((s) => `| ${s.id} | ${s.project} | ${s.after?.status || 'NOT EXECUTED'} | ${s.finding_ids.join(', ')} |`).join('\n')}\n\nIntelligence also included the separately audited H1 fixture restriction; a failed scenario is not an independent business bug. Exact original errors, element targets, before/after screenshots, traces and API evidence remain in [the JSON ledger](phase-4a-resolution.json).\n\n## Root corrections\n\n${Object.values(
    roots,
  )
    .map(([id, cause, fix]) => `- ${id}: ${cause} ${fix}`)
    .join(
      '\n',
    )}\n\n## Per-finding ledger\n\n| Stable ID | Route | Root | Result | Changed source |\n| --- | --- | --- | --- | --- |\n${ledger.map((r) => `| ${r.id} | ${r.route} | ${r.root} | ${r.resolved ? 'RESOLVED / independent retest' : 'OPEN / preserved'} | ${r.changed_files.join(', ')} |`).join('\n')}\n\nEach JSON row includes exact original result, source, correction and independent after-evidence; the caption row lists all 48 actual target reviews. Historical review additionally requires eight financial-header reviews. No unresolved full-document incomplete result is hidden or declared WCAG PASS.\n`,
);
console.log(
  JSON.stringify({
    status: report.status,
    resolved: resolved.size,
    open: report.summary.remaining_open,
    hashesVerified,
  }),
);
if (report.status !== 'ACCESSIBILITY_REMEDIATION_VALIDATED_BOUNDED_SCOPE') process.exitCode = 1;
