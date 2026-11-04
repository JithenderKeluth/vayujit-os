import fs from 'node:fs/promises';
import crypto from 'node:crypto';
const root = 'docs/qa/seller-experience/';
const names = [
  'wp7-certification-report.md',
  'wp7-journey-coverage-matrix.md',
  'wp7-defect-register.md',
  'wp7a-coverage-closure.md',
  'wp7a-browser-evidence.md',
  'wp7a-defect-resolution.md',
  'wp7a-gate.json',
  'wp7a2-coverage-closure.md',
  'wp7a2-browser-evidence.md',
  'wp7a2-defect-resolution.md',
  'wp7a2-gate.json',
  'wp7-journey-coverage-matrix-wp7a2-addendum.md',
];
const files = [];
for (const name of names) {
  const b = await fs.readFile(root + name);
  files.push({ file: root + name, sha256: crypto.createHash('sha256').update(b).digest('hex') });
}
const text = await fs.readFile(root + 'wp7-journey-coverage-matrix.md', 'utf8');
const rows = text
  .split('\n')
  .filter((l) => l.startsWith('| /'))
  .map((l) =>
    l
      .split('|')
      .slice(1, -1)
      .map((c) => c.trim()),
  );
const remaining = rows
  .filter((c) => c.at(-1) === 'NOT_TESTED')
  .map((c) => ({
    id: 'R-' + crypto.createHash('sha256').update(c[0]).digest('hex').slice(0, 8),
    route: c[0],
    capability: c[1],
    current_status: 'NOT_TESTED',
    why: 'Original parameterized/action route lacks populated functional evidence; route rendering elsewhere is insufficient.',
    required_evidence:
      'Authenticated UI action, owned persisted resource, reload and negative/context checks; screenshot/trace plus canonical API/ORM invariants.',
    dependencies:
      'Signed disposable PostgreSQL, synthetic owner and matching product/brand/artifact/job; inspect the concrete route contract before creating state.',
    safe_without_live_providers:
      !c[0].includes('/destinations/shopify') &&
      !c[0].includes('/destinations/wordpress') &&
      !c[0].includes('/publishing/connectors'),
    closure:
      'PASS only after actual supported UI/persistence/negative verification, or a separately reasoned NOT_SUPPORTED exclusion; never from navigation alone.',
    status: 'NOT_TESTED',
  }));
const core = [
  [
    'L-09',
    '/ai/generate',
    'Legacy deterministic content creation, validation, review, regeneration, history and approved-source revision rejection',
  ],
  [
    'L-10',
    '/ai/studio',
    'Queued multi-channel studio worker, failure/retry, versioned context and synthetic provenance',
  ],
  [
    'L-11',
    '/ai/artifacts/:id',
    'Draft human edit, immutable approved content, comparison, correct revision navigation and source lineage',
  ],
  [
    'L-12',
    '/ai/images',
    'Private upload, deterministic image job, output review/approval, regenerate/version lineage and failure boundaries',
  ],
  [
    'L-13',
    '/ai/studio/bulk',
    'Bulk text preview, enqueue, cancellation/retry and partial/reload consistency',
  ],
  [
    'L-14',
    '/ai/images/bulk',
    'Bulk image prerequisites, fingerprint/queue/retry and exact media/output identities',
  ],
  [
    'L-15',
    '/ai/studio/seo',
    'Persisted scoped SEO and keyword/tag actions with UNKNOWN commercial claims',
  ],
  [
    'L-16',
    '/campaigns/new',
    'Campaign creation, product/approved-artifact activity bindings, prerequisites, readiness, dependency and reload',
  ],
  [
    'L-17',
    '/ads/campaigns/:id',
    'Content/image creative preparation, missing/disabled authorization, stale references and no remote execution',
  ],
  ['L-18', '/ai/brand-voices', 'Brand voice creation/version/default/archive and application to new content context'],
  ['L-19', '/ai/presets', 'Preset creation/default/duplicate/archive and versioned generation configuration'],
  ['L-20', '/ai/usage', 'Persisted usage provenance, UNKNOWN cost, product/provider filtering and reload'],
  ['L-21', '/ai/video/bulk', 'Bulk video planning, prerequisites, lineage, partial failure/cancel/retry (not single-video WP7A2)'],
  ['L-22', '/social/compose', 'Social draft preparation/review and exact product/content/image identities; no dispatch'],
  ['L-23', '/ads/marketing', 'Supported marketing plan preparation, modeling assumptions, versions and HUMAN boundaries'],
  ['L-24', '/settings/ai/providers', 'Unavailable-provider states and safe configuration validation; no real credentials or external validation'],
  ['L-25', '/ai/artifacts/:id', 'Translation/localization, approved-source regeneration and exact-source lineage; no approval inheritance'],
];
await fs.mkdir('tmp/qa-wp7a3', { recursive: true });
await fs
  .writeFile(
    'tmp/qa-wp7a3/baseline.json',
    JSON.stringify({ files, previous_gate: 'INCOMPLETE' }, null, 2),
    { flag: 'wx' },
  )
  .catch((e) => {
    if (e.code !== 'EEXIST') throw e;
  });
await fs.writeFile(
  'tmp/qa-wp7a3/required-coverage.json',
  JSON.stringify(
    {
      counting_method:
        'Original 32 NOT_TESTED route leaves plus 17 explicit state/action groups in the open creative family. The separate 156-route reconciliation retains every original row including 124 route-review-only records. Route and action dimensions overlap and are not interchangeable; parent families are not counted again.',
      original_route_gaps: remaining.length,
      core_action_requirements: core.length,
      entries: [
        ...remaining,
        ...core.map(([id, route, capability]) => ({
          id,
          route,
          capability,
          status: 'NOT_TESTED',
          why: 'Explicit original L supported-action gap, not satisfied by rendered empty views.',
          required_evidence:
            'Chrome/Edge desktop/mobile owner actions, state/reload/negative assertions, canonical persisted snapshots and axe.',
          dependencies:
            'Approved marked QA installation; synthetic product and local provider; HUMAN review through existing UI only.',
          safe_without_live_providers: true,
          closure:
            'All applicable supported states tested; unavailable live behavior truthfully blocked, never fabricated.',
        })),
      ],
    },
    null,
    2,
  ),
);
console.log(
  JSON.stringify({
    historical_files: files.length,
    original_route_gaps: remaining.length,
    core_action_requirements: core.length,
  }),
);
await fs.writeFile('tmp/qa-wp7a3/all-route-reconciliation.json', JSON.stringify(rows.map(c => ({
  id: 'R-' + crypto.createHash('sha256').update(c[0]).digest('hex').slice(0, 8),
  route: c[0], capability: c[1], original_status: c.at(-1),
  original_positive_scope: c[4], original_negative_scope: c[5], original_stale_scope: c[6], original_security_scope: c[7],
  inherited_evidence: c[8], current_status: c.at(-1) === 'NOT_TESTED' ? 'NOT_TESTED' : 'INHERITED_BOUNDED_ROUTE_REVIEW_ONLY',
  why: 'Rendering does not certify every supported action. Preserve original scoped evidence, not a new functional PASS.',
  required_evidence: 'Exact owned synthetic artifact; authenticated UI action, supported failure/recovery, reload, persistence and scope checks.',
  dependencies: 'Attested QA-only PostgreSQL; canonical API/domain fixtures; existing HUMAN authorities.',
  safe_without_live_providers: 'Local deterministic preparation only; real provider credentials, acquisition and dispatch remain blocked.',
  closure: 'Close only the precise supported state demonstrated by browser/API/ORM evidence; retain unexecuted actions.'
})), null, 2));
