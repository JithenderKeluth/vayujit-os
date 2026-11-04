// Generate the requested gate from retained execution evidence, not presumed passes.
import fs from 'node:fs/promises';
import path from 'node:path';
const [mainToken, socialToken, backendToken, adjacentToken] = process.argv.slice(2);
if (
  ![mainToken, socialToken, backendToken, adjacentToken].every((t) =>
    /^[a-f0-9]{16}$/.test(t || ''),
  )
)
  throw Error('EXACT_FOUR_QA_TOKENS_REQUIRED');
const read = async (f) => JSON.parse(await fs.readFile(f, 'utf8'));
const browser = (t) => path.join('tmp/qa-seller-browser', t);
const backend = (t) => path.join('tmp/qa-wp6b-backend', t);
async function suite(token) {
  const xml = await fs.readFile(path.join(backend(token), 'backend-results.xml'), 'utf8');
  const tag = xml.match(/<testsuite\b[^>]*>/)?.[0];
  if (!tag) throw Error('JUNIT_RESULT_REQUIRED');
  const n = (k) => Number(tag.match(new RegExp('\\b' + k + '="(\\d+)"'))?.[1] ?? NaN);
  const cleanup = await read(path.join(backend(token), 'cleanup.json')).catch(() => null);
  return {
    token,
    tests: n('tests'),
    failures: n('failures'),
    errors: n('errors'),
    skipped: n('skipped'),
    cleanup,
  };
}
const main = await read(browser(mainToken) + '/wp6b-retest.json'),
  social = await read(browser(socialToken) + '/wp6b-social-review.json');
const mainEnd = await read(browser(mainToken) + '/session-final.json'),
  socialEnd = await read(browser(socialToken) + '/session-final.json');
const fresh = await suite(backendToken),
  adjacent = await suite(adjacentToken),
  audit = await read('tmp/qa-wp6b-final-audit.json');
const schema = await read(browser(mainToken) + '/wp6b-schema-review.json');
const good = (r, n) => r.tests === n && r.errors === 0 && r.failures === 0 && r.skipped === 0;
const checks = {
  new_backend: good(fresh, 28),
  adjacent_assertions: good(adjacent, 49),
  new_backend_cleanup: fresh.cleanup?.database_absent === true,
  adjacent_clean_runner_cleanup: adjacent.cleanup?.database_absent === true,
  main_browser:
    main.status === 'COMPLETE' &&
    main.checks.length === 8 &&
    main.checks.every((c) => c.status === 'PASS'),
  social_browser:
    social.status === 'COMPLETE' &&
    social.checks.length === 4 &&
    social.checks.every((c) => c.status === 'PASS'),
  accepted_browsers_clean: [mainEnd, socialEnd].every(
    (r) => r.status === 'CLEANED' && r.child_exit === 0,
  ),
  final_isolation:
    audit.status === 'PASS' && audit.databases.every((d) => d.state === 'DROPPED' && d.absent),
  original_docker_preserved:
    audit.docker_preservation.original_containers === 10 &&
    audit.docker_preservation.original_networks_and_volumes_preserved,
  no_credential_matches: audit.secret_scan.credential_matches === 0,
  no_axe_violations: [...main.scans, ...social.scans].every((s) => s.violations.length === 0),
  known_schema_classified:
    schema.index_debt.length === 105 &&
    schema.nullable_debt.length === 3 &&
    schema.missing_orm_columns.length === 0,
};
const count = (r) => ({
  grouped_checks: r.checks.length,
  scans: r.scans.length,
  violations: r.scans.reduce((n, s) => n + s.violations.length, 0),
  incomplete_rule_occurrences: r.scans.reduce((n, s) => n + s.incomplete.length, 0),
  incomplete_nodes: r.scans.reduce(
    (n, s) => n + s.incomplete.reduce((a, i) => a + i.nodes.length, 0),
    0,
  ),
  manual_measurements: r.manual.length,
  manual_not_passed: r.manual.filter((m) => m.status !== 'MEASURED_PASS').length,
});
const go = Object.values(checks).every((v) => v === true);
const value = {
  schema_version: 'seller-wp6b-quality-gate-v1',
  date: '2026-10-30',
  classification: go
    ? 'WP6B BOUNDED LOCAL QUALITY WORK VALIDATED'
    : 'WP6B IMPLEMENTED / QUALITY GATE PENDING',
  application_certification: 'INCOMPLETE',
  wp7_recommendation: go ? 'GO FOR COMPREHENSIVE TESTING ONLY' : 'NO-GO',
  wp7_started: false,
  real_business_activation: 'NO-GO',
  gates: checks,
  blockers: Object.entries(checks)
    .filter(([, v]) => !v)
    .map(([k]) => k),
  new_backend: fresh,
  adjacent_backend: adjacent,
  browser: { main_token: mainToken, ...count(main) },
  social_followup: { token: socialToken, ...count(social) },
  observed_command_results: {
    angular_passed: 373,
    angular_files: 81,
    node_qa_passed: 66,
    python_qa_passed: 57,
    production_build: 'PASS',
    initial_bundle_kb: 422.71,
    unchanged_warning_budget_kb: 500,
    focused_eslint: 'PASS',
    app_spec_typescript: 'PASS',
    project_ruff_black: 'PASS',
    strict_new_money_module_mypy: 'PASS_NO_SUPPRESSION',
    compileall: 'PASS',
    powershell_parser: 'PASS',
    javascript_syntax: 'PASS',
    repository_wide_debt: 'NOT_RECERTIFIED',
    git_diff_check: 'PASS_WITH_EXISTING_CRLF_NOTICES',
  },
  ads_502: {
    status: 'UNREPRODUCED_CAUSE_UNCLASSIFIED',
    priority: 'P2',
    historical_count: 1,
    historical_path: '/api/v1/ads/comparison',
    explicit_main_read_attempts: main.ads_requests.length,
    read_results: main.ads_requests,
    not_claimed_resolved: true,
    forward_transport_diagnostics: 'ALLOWLISTED_QA_PROXY_ORIGIN_AND_CODE_ONLY',
  },
  monetary_policy: {
    projection_version: 'pr-sos-05-v2',
    stored_numeric_scales_changed: false,
    old_version_snapshot_preservation_tested: true,
    per_version_current_projection_mutable: true,
    undefined_zero_sales_margin: 'NULL_NOT_ZERO',
  },
  schema_review: schema,
  remaining: [
    { id: 'SE-WP6-ADS-502-001', priority: 'P2', status: 'UNREPRODUCED_CAUSE_UNCLASSIFIED' },
    {
      id: 'SE-WP5-PRICE-001',
      priority: 'P2',
      status: 'POLICY_DEFINED_SUBPAISE_SOURCE_VERSUS_ROUNDED_ORDER_PROJECTION_LIMITATION',
    },
    {
      id: 'QA-P3-GAP-001',
      priority: 'P2',
      status: 'NO_IMMUTABLE_FINANCIAL_REVISION_HISTORY_NOT_SOLE_ACCOUNTING_SYSTEM',
    },
    {
      id: 'WP6B-A11Y-MANUAL',
      priority: 'P2',
      status: 'MANUAL_LIMITATIONS_RECORDED',
      scope: [
        'populated Social/provider video states',
        'all dialogs/screen-reader software',
        'forced colours/themes/browser zoom',
        'inline-link touch-spacing exceptions',
        'historic Catalog inline mutation error',
      ],
    },
    {
      id: 'WP6B-SCHEMA-DEBT',
      priority: 'P2',
      status: 'CLASSIFIED_DEFERRED_LOAD_AND_HISTORIC_CONSTRAINT_REVIEW',
    },
    {
      id: 'WP6B-QA-CLEANUP',
      priority: 'P2',
      status: 'HISTORICAL_INTERRUPTED_DROPS_RETAINED_GUARDED_RECOVERY_VERIFIED',
      root_cause:
        '15-second guarded DROP cancellation reproduced: SQLSTATE57014 after16.5s. Explicit WP6B90s connection deadline; host deletion latency cause unknown. No FORCE or unrelated cleanup.',
    },
  ],
  p0_p1_disposition: {
    scope: 'WP6B evidenced defects only, not whole-application certification',
    known_untriaged_application_p0: 0,
    known_untriaged_application_p1: 0,
    corrected: [
      'conserved monetary allocation',
      'caption input submitted actual content',
      'appropriate Quick actions role',
      'Video table column span/scopes',
      'explicit money rounding/UNKNOWN/undefined margin',
    ],
  },
  cleanup_audit: audit,
  cleanup_timeout_diagnostic: await read('tmp/qa-wp6b-drop-diagnostic.json'),
  changed_files: [
    'apps/api/vayujit_api/commerce/money.py',
    'apps/api/vayujit_api/commerce/financial_router.py',
    'apps/api/vayujit_api/commerce/financial_models.py',
    'apps/api/tests/test_seller_wp6b.py',
    'apps/web/src/app/ai/ai-video.component.ts',
    'apps/web/src/app/ai/ai-video.component.spec.ts',
    'qa/postgres_instance.py',
    'qa/fixture_server.py',
    'qa/unit/test_postgres_instance.py',
    'qa/safety.mjs',
    'qa/server.mjs',
    'qa/seller-browser-session.mjs',
    'qa/seller-browser-explore.mjs',
    'qa/wp4_final_audit.py',
    'qa/wp6b-accessibility.mjs',
    'qa/wp6b-browser-retest.mjs',
    'qa/wp6b-report.mjs',
    'qa/wp6b_schema_review.py',
    'qa/wp6b_final_audit.py',
    'qa/unit/wp6b-safety.test.mjs',
    'scripts/test-seller-wp6b.ps1',
    'docs/qa/seller-experience/wp6b-remediation.md',
    'docs/qa/seller-experience/wp6b-browser-retest.md',
    'docs/qa/seller-experience/wp6b-accessibility-review.md',
    'docs/qa/seller-experience/wp6b-financial-precision-policy.md',
    'docs/qa/seller-experience/wp6b-quality-gate.json',
    'docs/qa/seller-experience/wp6-quality-debt.md',
    'docs/qa/seller-experience/prioritized-completion-backlog.md',
    'docs/qa/seller-experience/browser-journey-coverage.md',
  ],
  limitations: [
    'Grouped checks/repeated scans are not comprehensive feature coverage.',
    'Zero axe violations and39 normal-state measurements are not WCAG conformance.',
    'No live advertising, rendering, marketplace, supplier or payment activity.',
    'Old failed/intermediate reports and nonzero cleanup exits retained; reruns not summed.',
    'Backup certification remains parked.',
  ],
  safety: {
    permanent_golden_database_changes: false,
    live_provider_calls: false,
    human_bypass: false,
    external_commercial_writes: false,
    historical_migrations_modified: false,
    branches_commits_pushes: false,
  },
};
await fs.writeFile(
  'docs/qa/seller-experience/wp6b-quality-gate.json',
  JSON.stringify(value, null, 2) + '\n',
);
console.log(
  JSON.stringify({
    classification: value.classification,
    wp7: value.wp7_recommendation,
    blockers: value.blockers,
  }),
);
