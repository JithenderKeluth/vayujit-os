import fs from 'node:fs/promises';
import { surfaceId, routePlan, classifyCoverage, canonicalRoute } from './phase4-surface.mjs';
import { phase3ApiComplete, certificationStatus, finding } from './safety.mjs';

export function expectedPhase4Ids(routes) {
  const areas = [
    ...new Set(
      routePlan(routes)
        .filter((r) => r.kind === 'PAGE' && !['/login', '/setup'].includes(r.route))
        .map((r) => r.area),
    ),
  ].sort();
  return [
    ...areas.map((a) => 'QA-P4-SURFACE-' + a.toUpperCase().replaceAll(/[^A-Z0-9]/g, '-')),
    ...[1, 2, 3, 4].map((n) => 'QA-P4-TASK-0' + n),
  ];
}
export function phase4Status(report, routes) {
  const ids = expectedPhase4Ids(routes);
  return phase4CleanupComplete(report.cleanup) &&
    certificationStatus(report.reports, report.cleanup, ids.length) === 'PASS_BOUNDED_SMOKE' &&
    report.reports.every(
      (r) =>
        phase3ApiComplete(r.api_results) &&
        ids.every((id) => r.tests.filter((t) => t.id === id).length === 1),
    )
    ? 'PASS_BOUNDED_EXPLORATION'
    : 'INCOMPLETE';
}
export function phase4CleanupComplete(cleanup) {
  return (
    cleanup.length === 2 &&
    new Set(cleanup.map((c) => c.database)).size === 2 &&
    ['desktop', 'mobile'].every((p) => cleanup.filter((c) => c.project === p).length === 1) &&
    cleanup.every(
      (c) =>
        /^vayujit_qa[a-f0-9]{16}_test$/.test(c.database || '') &&
        c.status === 'PASS' &&
        c.child_exit === 0 &&
        c.proof?.marker_verified === true &&
        c.proof?.database_absent === true &&
        c.proof?.database === c.database,
    )
  );
}
const read = async (file) => JSON.parse(await fs.readFile(file, 'utf8'));
const evidence = (test) => test.evidence.map((e) => ({ name: e.name, path: e.path }));
export async function writePhase4Report(report, inventory) {
  report.execution_generated_at ||= report.generated_at;
  report.generated_at = new Date().toISOString();
  const tests = report.reports.flatMap((r) => r.tests);
  const visits = [];
  const nodes = [];
  const actions = [];
  for (const t of tests) {
    for (const e of t.evidence) {
      if (e.name.startsWith('surface-') && !e.name.startsWith('surface-screen-')) {
        const v = await read(e.path);
        if (!v.controls) continue;
        visits.push({
          ...v,
          project: t.project,
          evidence: e.path,
          failure: (t.signals?.api_operations || []).some(
            (o) => o.screen === v.route && o.status >= 500,
          ),
        });
      }
      if (e.name.startsWith('node-review-'))
        nodes.push({ ...(await read(e.path)), name: e.name, project: t.project, evidence: e.path });
      if (e.name === 'approved-actions')
        actions.push(
          ...(await read(e.path)).map((a) => ({ ...a, project: t.project, evidence: e.path })),
        );
      if (e.name === 'stock-handoff-filter-empty') {
        const v = await read(e.path);
        visits.push({
          ...v,
          project: t.project,
          evidence: e.path,
          route_match: true,
          failure: false,
        });
      }
    }
  }
  // Resolve source route declarations only with legitimate fixture IDs saved by
  // the canonical API setup. A missing fixture remains explicit, never a fake ID.
  const planned = [];
  for (const c of report.cleanup) {
    const token = c.database.match(/qa([a-f0-9]{16})_test/)[1];
    const m = await read(`tmp/qa-agent/${token}/phase3-manifest.json`).catch(() => ({}));
    planned.push({ project: c.project, routes: routePlan(inventory.routes, m) });
  }
  const coverage = classifyCoverage(planned[0]?.routes || routePlan(inventory.routes), visits);
  const findings = new Map();
  const add = (f) => {
    const old = findings.get(f.id);
    if (old) {
      old.evidence = [
        ...new Map([...old.evidence, ...f.evidence].map((e) => [e.path, e])).values(),
      ];
      return;
    }
    findings.set(f.id, f);
  };
  const make = (
    id,
    route,
    type,
    actual,
    confidence,
    refs,
    priority = 'P2',
    severity = 'MODERATE',
  ) =>
    finding(id, {
      feature: 'Phase 4 exploratory ' + type.toLowerCase(),
      area: route.split('/')[1] || 'home',
      journey: 'First-seller supported task review',
      route,
      type,
      severity,
      priority,
      expected:
        'Supported local workflow is usable, truthful and accessible without unexpected errors or forbidden execution.',
      actual,
      business_impact:
        'The seller may encounter an inaccessible, misleading or incomplete supported workflow.',
      reproduction_steps: [
        'npm.cmd run qa:phase4',
        'Open ' +
          route +
          ' in the recorded synthetic scenario; inspect attached state and network evidence.',
      ],
      evidence: refs,
      confidence,
      suggested_fix:
        'Review exact affected source/authority and approve only a bounded fix; preserve security and financial semantics.',
      retest_status: 'NOT_RETESTED',
    });
  for (const t of tests) {
    for (const scan of t.axe || [])
      for (const v of scan.violations) {
        add(
          make(
            'QA-P4-AXE-' + surfaceId(canonicalRoute(scan.route) + '|' + v.id).toUpperCase(),
            canonicalRoute(scan.route),
            'ACCESSIBILITY',
            JSON.stringify(v),
            'CONFIRMED',
            evidence(t),
            ['critical', 'serious'].includes(v.impact) ? 'P1' : 'P2',
            ['critical', 'serious'].includes(v.impact) ? 'MAJOR' : 'MODERATE',
          ),
        );
      }
    for (const op of (t.signals?.api_operations || []).filter((o) => o.status >= 500)) {
      if (t.signals.expected_http_errors.some((e) => e.path === op.path && e.status === op.status))
        continue;
      add(
        make(
          'QA-P4-API-' + surfaceId(canonicalRoute(op.path)).toUpperCase(),
          canonicalRoute(op.screen),
          'SUSPECTED_DEFECT',
          `${op.method} ${op.path} returned HTTP ${op.status}. ORM-only fixture/migration requirements and code cause require separate triage; not automatically a production defect.`,
          'SUSPECTED',
          evidence(t),
        ),
      );
    }
    if (!['passed', 'skipped'].includes(t.status))
      add(
        make(
          'QA-P4-ASSERT-' + surfaceId(t.id + '|' + t.project).toUpperCase(),
          t.signals?.visited_routes.at(-1) || 'unknown',
          'SUSPECTED_DEFECT',
          t.error.join('\n'),
          'SUSPECTED',
          evidence(t),
          'P1',
          'MAJOR',
        ),
      );
  }
  const priorPath = 'docs/qa/phase-4-prior-backlog.json';
  for (const f of findings.values()) {
    if (f.type !== 'ACCESSIBILITY') continue;
    const rule = JSON.parse(f.actual).id;
    const recommendations = {
      label:
        'Associate each visible field label with its input; test accessible name and keyboard targeting. Complexity: small.',
      'select-name':
        'Associate the status filter label with its select, preserving filtering semantics. Complexity: small.',
      'color-contrast':
        'Correct shared foreground/background tokens or opacity for these exact enabled text nodes; recheck all states and viewports without lowering ratios. Complexity: medium.',
      'scrollable-region-focusable':
        'Give the overflow region a descriptive accessible name and keyboard focus, then verify horizontal scrolling and focus escape. Complexity: small.',
      'aria-prohibited-attr':
        'Use an appropriate progress role/element for the recorded ARIA properties, preserving accurate state values. Complexity: small.',
      dlitem:
        'Place dt/dd pairs inside a valid dl structure, preserving content and responsive grouping. Complexity: small.',
      'empty-table-header':
        'Provide a meaningful accessible column heading or correctly mark a non-data action column. Complexity: small.',
    };
    f.expected = `No axe ${rule} violation in the recorded application state.`;
    f.business_impact = ['label', 'select-name'].includes(rule)
      ? 'Assistive-technology users cannot reliably identify or operate the offered filters.'
      : 'Recorded semantics, readability or keyboard access impede seller comprehension or assistive navigation.';
    f.suggested_fix =
      recommendations[rule] ||
      'Remove nested/duplicate landmark semantics while retaining the canonical application main and named regions; retest all shared component routes. Complexity: small to medium.';
  }
  const stockRefs = tests.flatMap((t) =>
    t.evidence.filter((e) => e.name === 'stock-handoff-filter-empty'),
  );
  if (stockRefs.length) {
    const f = make(
      'QA-P4-UX-STOCK-EMPTY',
      '/marketplaces/inventory',
      'USABILITY',
      'Searching for a nonexistent SKU on a populated installation shows “No canonical inventory yet” and creation guidance rather than distinguishing no matching results. The same scenario then retrieves an existing persisted SKU.',
      'RECOMMENDATION',
      stockRefs,
      'P2',
      'MINOR',
    );
    f.expected =
      'A filtered-empty result is distinguishable from an installation with no stock records.';
    f.business_impact =
      'A first-time seller may think saved stock is missing or attempt unnecessary duplicate creation.';
    f.suggested_fix =
      'Use “No matching inventory” with clear/reset-filter guidance when filters are active; preserve real initial-empty creation guidance separately. Complexity: small copy/state distinction, not a new inventory authority.';
    add(f);
  }
  const clippedCaptions = nodes.filter(
    (n) => n.project === 'mobile' && n.name.endsWith('-original') && !n.text_horizontally_in_view,
  );
  if (clippedCaptions.length) {
    const f = make(
      'QA-P4-A11Y-CAPTION-CLIPPING',
      '/intelligence/sourcing-economics',
      'ACCESSIBILITY',
      `${clippedCaptions.length} original mobile caption occurrences extend beyond the visible viewport even after controlled left-edge scrolling. Their wider-viewport counterparts pass contrast; the original narrow nodes remain axe-incomplete. This confirms clipping, not an invented contrast ratio or full WCAG determination.`,
      'CONFIRMED',
      clippedCaptions.map((n) => ({ name: n.name, path: n.evidence })),
      'P2',
      'MODERATE',
    );
    f.expected =
      'Table captions remain readable in the narrow layout while table data remains keyboard-scrollable.';
    f.business_impact =
      'The seller cannot read the complete evidence-table purpose at the default mobile scroll position.';
    f.suggested_fix =
      'Constrain/wrap captions within the visible region independently of wide table columns; retain semantic captions, focusable overflow and every evidence column. Complexity: medium shared DD/economics responsive styling.';
    add(f);
  }
  for (const route of [
    ...new Set(
      visits.filter((v) => v.document.width > v.viewport.width + 1).map((v) => v.declaration),
    ),
  ]) {
    const rows = visits.filter(
      (v) => v.declaration === route && v.document.width > v.viewport.width + 1,
    );
    const f = make(
      'QA-P4-UX-OVERFLOW-' + surfaceId(route).toUpperCase(),
      route,
      'USABILITY',
      rows
        .map(
          (v) =>
            `${v.project}: document width ${v.document.width}px at viewport ${v.viewport.width}px`,
        )
        .join('; '),
      'RECOMMENDATION',
      rows.map((v) => ({ name: 'Runtime surface bounds', path: v.evidence })),
      'P2',
      'MINOR',
    );
    f.business_impact =
      'Whole-page horizontal scrolling can obscure actions and disrupt desktop navigation.';
    f.suggested_fix =
      'Inspect grid/flex min-width and bound overflow to named table/preview regions; preserve content. Complexity: small to medium layout work, requiring targeted visual retest.';
    add(f);
  }
  const longResearch = visits.filter(
    (v) =>
      ['/intelligence/external', '/intelligence/websites'].includes(v.declaration) &&
      v.document.height > 10000,
  );
  if (longResearch.length) {
    const f = make(
      'QA-P4-UX-RESEARCH-LENGTH',
      '/intelligence/external',
      'USABILITY',
      longResearch
        .map((v) => `${v.project} ${v.declaration}: ${v.document.height}px document height`)
        .join('; '),
      'RECOMMENDATION',
      longResearch.map((v) => ({ name: 'Measured long research screen', path: v.evidence })),
      'P2',
      'MINOR',
    );
    f.business_impact =
      'Long source/evidence workspaces can make the current decision and next action difficult to find; length alone is not a functional defect.';
    f.suggested_fix =
      'Review a concise status summary, section jump links and scoped evidence disclosure without deleting provenance. Complexity: medium information-architecture proposal requiring product approval.';
    add(f);
  }
  let prior = await read(priorPath).catch(() => null);
  if (!prior) {
    prior = await read('docs/qa/defect-backlog.json');
    await fs.writeFile(priorPath, JSON.stringify(prior, null, 2), { flag: 'wx' });
  }
  // A remediation rerun must retain the complete immutable pre-fix ledger.
  // Only the independent, evidence-linked resolution step may close findings.
  const remediationBaseline = await read('docs/qa/phase-4a-baseline.json').catch(() => null);
  if (remediationBaseline) {
    const currentLedger = await read('docs/qa/defect-backlog.json');
    prior = [
      ...new Map(
        [...remediationBaseline.findings, ...currentLedger].map((f) => [f.id, f]),
      ).values(),
    ];
  }
  // Exploratory evidence never silently closes earlier findings. Node-level
  // verification is separate from the aggregate historical accessibility ticket.
  const backlog = [...new Map([...prior, ...findings.values()].map((f) => [f.id, f])).values()];
  await fs.writeFile('docs/qa/defect-backlog.json', JSON.stringify(backlog, null, 2));
  const scans = tests.flatMap((t) => (t.axe || []).map((s) => ({ ...s, project: t.project })));
  const controls = visits.flatMap((v) =>
    v.controls.map((c) => ({
      ...c,
      route: v.route,
      declaration: v.declaration,
      project: v.project,
      evidence: v.evidence,
    })),
  );
  const api = report.reports.flatMap((r) => r.api_results?.tests || []);
  report.status = phase4Status(report, inventory.routes);
  report.full_application_certification = 'INCOMPLETE';
  report.adjacent_regressions = {};
  for (const stem of ['phase-2-report', 'phase-1-retest-report']) {
    const adjacent = await read(`docs/qa/${stem}.json`).catch(() => null);
    if (adjacent)
      report.adjacent_regressions[stem] = {
        evidence: `docs/qa/${stem}.json`,
        generated_at: adjacent.generated_at,
        status: adjacent.status,
        summary: adjacent.executive_summary,
        cleanup: adjacent.cleanup,
      };
  }
  report.quality_and_commands = 'docs/qa/phase-4-validation.md';
  report.executive_summary = {
    passed: tests.filter((t) => t.status === 'passed').length,
    failed: tests.filter((t) => !['passed', 'skipped'].includes(t.status)).length,
    skipped: tests.filter((t) => t.status === 'skipped').length,
    blocked_installations: report.reports.filter((r) => r.blocker).length,
    api_passed: api.filter((t) => t.status === 'PASS').length,
    api_failed: api.filter((t) => t.status === 'FAIL').length,
    api_errors: api.filter((t) => t.status === 'ERROR').length,
    route_declarations: inventory.routes.length,
    visited_declarations: new Set(visits.map((v) => v.declaration)).size,
    unavailable_context_declarations: coverage.filter(
      (r) => r.status === 'REQUIRES_UNAVAILABLE_CANONICAL_CONTEXT',
    ).length,
    safety_denied_request_occurrences: tests.flatMap((t) => t.signals?.denied_requests || [])
      .length,
    control_occurrences: controls.length,
    unique_control_fingerprints: new Set(controls.map((c) => c.id)).size,
    visible_control_occurrences: controls.filter((c) => c.visible).length,
    recorded_action_outcomes: actions.length,
    axe_state_scans: scans.length,
    axe_rule_violation_occurrences: scans.flatMap((s) => s.violations).length,
    new_confirmed_route_rule_findings: [...findings.values()].filter((f) =>
      f.id.startsWith('QA-P4-AXE-'),
    ).length,
    confirmed_non_axe_findings: [...findings.values()].filter(
      (f) => f.confidence === 'CONFIRMED' && !f.id.startsWith('QA-P4-AXE-'),
    ).length,
    inherited_open_findings: prior.length,
    complete_application_coverage: false,
  };
  const accessibility = {
    scope:
      'Established axe, original DOM; controlled scroll/viewport/focus only. Wide viewport pass does not clear narrow viewport failure. No complete WCAG claim.',
    nodes,
    scans,
  };
  const surface = {
    planned,
    routes: coverage,
    visits,
    controls,
    actions,
    backend_operations_observed: tests.flatMap((t) => t.signals?.api_operations || []),
    api_only_candidates: inventory.api_declarations.filter((e) => !e.frontend_candidates.length),
    unreachable_policy:
      'Absent runtime visit is NOT EXECUTED/context unavailable, not proof of unreachable production functionality.',
  };
  await fs.writeFile('docs/qa/phase-4-surface-inventory.json', JSON.stringify(surface, null, 2));
  await fs.writeFile('docs/qa/phase-4-accessibility.json', JSON.stringify(accessibility, null, 2));
  report.findings = [...findings.values()];
  report.prior_open_findings = prior;
  report.actions = actions;
  report.accessibility_summary = {
    node_reviews: nodes.length,
    verified_contrast_nodes: nodes.filter(
      (n) => n.passes.includes('color-contrast') && !n.incomplete.length && !n.violations.length,
    ).length,
    incomplete_node_reviews: nodes.filter((n) => n.incomplete.length).length,
    actual_node_violations: nodes.filter((n) => n.violations.length).length,
    clipped_text_reviews: nodes.filter((n) => !n.text_horizontally_in_view).length,
  };
  const journeyDefinitions = [
    [
      'Initial setup/onboarding',
      ['/setup', '/login', '/dashboard'],
      'PARTIAL: existing owner login/logout tested; fresh owner creation remains prior Phase 1 evidence',
    ],
    [
      'Product discovery/selection',
      ['/intelligence/business-agent', '/intelligence/product-opportunities'],
      'PARTIAL: persisted synthetic selected context; live discovery intentionally forbidden',
    ],
    [
      'Supplier evaluation/DD',
      ['/intelligence/sourcing', '/intelligence/due-diligence'],
      'PARTIAL: canonical synthetic supplier/DD context; no live acquisition/contact',
    ],
    [
      'Economics/profitability',
      ['/intelligence/sourcing-economics', '/marketplaces/financials'],
      'PARTIAL: canonical prior oracles/API regressions and contextual browser evidence; not complete accounting',
    ],
    [
      'Catalog management',
      ['/catalog', '/products'],
      'PARTIAL: supported edit/cancel/save/reload; image/variant workflows inventoried, not fully exercised',
    ],
    [
      'Initial inventory entry',
      ['/marketplaces/inventory'],
      inventory.routes.some((r) => r.route === '/marketplaces/inventory/opening')
        ? 'IMPLEMENTED: dedicated opening-stock handoff; functional certification is in the separate Phase 4B report, not inferred from a route visit'
        : 'MISSING LAUNCH-CRITICAL UI HANDOFF: API exists; no automatic new production workflow',
    ],
    [
      'Inventory updates',
      ['/marketplaces/inventory'],
      'PARTIAL: persisted API regression; browser filter/mapping cancel/error recovery',
    ],
    [
      'Order handling',
      ['/marketplaces/orders'],
      'PARTIAL: fake-provider canonical lifecycle API and read-only UI; no real marketplace handling',
    ],
    [
      'Financial reconciliation',
      ['/marketplaces/financials', '/marketplaces/settlements'],
      'PARTIAL: deterministic synthetic reconciliation and four exact historical node checks',
    ],
    [
      'Business Agent recommendations',
      ['/intelligence/business-agent'],
      'PARTIAL: read-only discovery; canonical financial agent API regressions',
    ],
    [
      'Action Center HUMAN decisions',
      ['/operations/action-center'],
      'PARTIAL: canonical signal transition API regressions; generic business approval/execution remains unsupported',
    ],
    [
      'Settings/status/recovery',
      ['/settings', '/operations'],
      'PARTIAL: read-only route inventory; injected HTTP recovery only, no worker/backup mutation',
    ],
  ];
  const journeys = journeyDefinitions.map(([journey, routes, assessment]) => ({
    journey,
    assessment,
    route_evidence: coverage.filter((c) =>
      routes.some((r) => c.declaration === r || c.declaration.startsWith(r + '/')),
    ),
    seller_review_questions: {
      start:
        'See actual headings/navigation/empty-state captures; not a subjective task-success assertion',
      next_step: 'Review recorded actionable controls and state text',
      inputs: 'Required/disabled fields inventoried; only explicit scenario validation executed',
      trust: 'Synthetic/UNKNOWN preserved; no real provider evidence',
      persistence: 'Only explicitly asserted save/reload and prior API scenarios',
      correction: 'Only explicit cancel/filter/retry scenarios',
      completion: 'No general completion claim',
      unsupported: 'Default deny and missing workflow assessment retained',
    },
  }));
  await fs.writeFile('docs/qa/phase-4-journeys.json', JSON.stringify(journeys, null, 2));
  await fs.writeFile('docs/qa/phase-4-report.json', JSON.stringify(report, null, 2));
  const rows = coverage
    .map(
      (c) =>
        `| ${c.declaration} | ${c.status} | ${c.visits.map((v) => v.project + ': ' + v.control_count).join(', ')} |`,
    )
    .join('\n');
  await fs.writeFile(
    'docs/qa/phase-4-coverage.md',
    `# Phase 4 actual route/control coverage\n\nA visit is not full functional coverage. Controls include repeated navigation and conditional hidden controls; only explicit action occurrences were exercised. No arbitrary button clicking.\n\n| Declaration | Actual status | Control occurrences per visit |\n| --- | --- | --- |\n${rows}\n\n## Seller journey assessment\n\n${journeys.map((j) => '- ' + j.journey + ': ' + j.assessment).join('\n')}\n\nExact controls, forms, dialog, table and state observations: [surface inventory](phase-4-surface-inventory.json). No absent dialog/conditional state is inferred implemented or unsupported solely from this DOM. Backend-only candidates are conservative static references, not missing-feature verdicts.\n`,
  );
  await fs.writeFile(
    'docs/qa/phase-4-report.md',
    `# QA Phase 4 executed report\n\n${report.generated_at}. **${report.status}**. Application certification **INCOMPLETE**.\n\n## Actual counts\n\n\`\`\`json\n${JSON.stringify(report.executive_summary, null, 2)}\n\`\`\`\n\n## New findings (triage categories preserved)\n\n${report.findings.map((f) => `- **${f.id}** ${f.priority} / ${f.confidence} / ${f.type}: ${f.actual.slice(0, 1000)} Evidence: ${f.evidence.map((e) => e.path).join(', ')}`).join('\n') || 'None recorded. Unexecuted controls/states are not passed.'}\n\n## Accessibility subset\n\n\`\`\`json\n${JSON.stringify(report.accessibility_summary, null, 2)}\n\`\`\`\n\nSee [exact node and scan evidence](phase-4-accessibility.json). Wide viewport success is not narrow/mobile closure; no WCAG conformance claim.\n\n## Prior findings\n\n${prior.map((f) => '- ' + f.id + ' / ' + f.priority + ' / ' + f.retest_status).join('\n')}\n\nPreserved without automatic closure. [Current backlog](defect-backlog.json).\n\n## Cleanup\n\n${report.cleanup.map((c) => `- ${c.project}: ${c.status}, child exit ${c.child_exit}, marker=${c.proof?.marker_verified === true}, absent=${c.proof?.database_absent === true}`).join('\n')}\n\n## Coverage and limitations\n\n[Route/control matrix](phase-4-coverage.md), [12 seller journeys](phase-4-journeys.json), [initial stock proposal](phase-4-stock-entry-assessment.md), and [validation / exact Windows commands](phase-4-validation.md).\n\nOnly disposable synthetic state. Existing ORM fixtures are not migration certification. No marketplace/provider calls, supplier contact, publication, worker/backup changes, permanent data changes, branches, commits or pushes.\n`,
  );
  const old = await fs.readFile('docs/qa/coverage-matrix.md', 'utf8');
  await fs.writeFile(
    'docs/qa/coverage-matrix.md',
    old.replace(/\n<!-- PHASE4 -->[\s\S]*$/, '') +
      `\n<!-- PHASE4 -->\n## Phase 4 exploratory extension\n\nSee [actual Phase 4 coverage](phase-4-coverage.md) and [report](phase-4-report.md). ${report.executive_summary.visited_declarations}/${inventory.routes.length} declarations observed, not complete feature coverage. Prior tables remain historical execution evidence. Application certification INCOMPLETE.\n`,
  );
}
