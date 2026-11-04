import fs from 'node:fs/promises';
import crypto from 'node:crypto';
const root = 'docs/qa/seller-experience/';
const prior = JSON.parse(await fs.readFile(root + 'wp7a4-coverage-ledger.json', 'utf8'));
const entries = prior.entries.filter((e) => e.status === 'PARTIAL');
const conditions = {
  'R-184826c3': [
    'research',
    'Populate synthetic observations using the canonical ingestion contract; snapshot/analyze the exact context; reject invalid context; reload provenance and UNKNOWN claims.',
  ],
  'R-794214d7': [
    'video-campaign',
    'Resolve exact campaign/activity binding, navigate its exact generation/output, reject foreign/missing activity, persist reload and show failed/retried history without dispatch.',
  ],
  'R-3feda36d': [
    'social',
    'Prepare image and approved-Video drafts, preview/review exact references, reject stale versions, retain unavailable external state and no remote publication.',
  ],
  'R-55e822d5': [
    'marketplace',
    'Distinguish configured fake sandbox accounts from connected/live certification; missing/revoked authorization; reload snapshots and default deny.',
  ],
  'R-551d2f8c': [
    'marketplace',
    'Exact Flipkart draft, canonical readiness prerequisite correction, HUMAN review/authorization expiry/revocation/staleness and reload; no transport execution.',
  ],
  'R-db243c36': [
    'marketplace',
    'Exact Meesho draft, supported readiness/manual preparation/HUMAN review boundaries, unavailable integration and reload; do not invent OAuth or dispatch.',
  ],
  'R-d6a495d5': [
    'marketplace',
    'Exact Amazon draft, canonical readiness prerequisite correction, HUMAN review/authorization expiry/revocation/staleness and reload; no SP-API calls.',
  ],
  'L-10': [
    'ai-text',
    'Inject bounded local provider failure, canonical retry/supersession, stale inputs and exact pending-review child lineage; no inherited approval, reload.',
  ],
  'L-12': [
    'ai-image',
    'Inject failure in the exact image child, retry deterministically, show latest error/history, regeneration lineage and private output persistence; no approval inheritance.',
  ],
  'L-13': [
    'ai-text',
    'Bulk text partial success/failure, retry-failed, repeated/concurrent recovery and cancellation; persisted outputs/progress/reload and no duplicate work.',
  ],
  'L-15': [
    'seo',
    'Scoped keyword/tag management, analysis/reanalysis immutable history, validation/conflicts where supported, save/reload and related artifact navigation; unknown commercial metrics.',
  ],
  'L-16': [
    'video-campaign',
    'Create campaign with exact approved artifact/product bindings; change input, expose stale prerequisite, recover via legitimate new review, verify dependency and reload.',
  ],
  'L-17': [
    'ads',
    'Local fake content/image creative preview, missing/expired/disabled authorization, stale references and HUMAN confirmation; never remote execution.',
  ],
  'L-21': [
    'video-campaign',
    'Persist/reopen bulk Video via URL, partial failure/retry history, repeated/concurrent recovery, cancellation and reload; exact child identity and no duplicate execution.',
  ],
  'L-22': [
    'social',
    'Compose exact approved Video and image drafts through UI, preserve brand/product/account/media identity, validation/stale approval and reload; no dispatch.',
  ],
  'L-23': [
    'ads',
    'Manual modeling plus supported recommendation/version/update workflow; explicit UNKNOWN allocations, changed-input freshness, HUMAN confirmation and reload; no spend.',
  ],
};
if (prior.entries.length !== 48 || entries.length !== 16 || entries.some((e) => !conditions[e.id]))
  throw Error('EXACT_WP7A5_SCOPE_REQUIRED');
await fs.mkdir('tmp/qa-wp7a5', { recursive: true });
const files = (await fs.readdir(root)).filter(
  (n) => /^wp7a4-/.test(n) || /^wp7-journey-coverage-matrix/.test(n),
);
const baseline = [];
for (const name of files)
  baseline.push({
    file: root + name,
    sha256: crypto
      .createHash('sha256')
      .update(await fs.readFile(root + name))
      .digest('hex'),
  });
await fs
  .writeFile('tmp/qa-wp7a5/baseline.json', JSON.stringify({ files: baseline }, null, 2), {
    flag: 'wx',
  })
  .catch((e) => {
    if (e.code !== 'EEXIST') throw e;
  });
const ledger = {
  package: 'WP7A-5',
  original_denominator: 48,
  inherited_closed: 32,
  targeted: 16,
  status: 'PLANNED',
  source: root + 'wp7a4-coverage-ledger.json',
  entries: entries.map((e) => ({
    ...e,
    prior_status: 'PARTIAL',
    status: 'NOT_TESTED',
    full_closure: false,
    already_verified: e.final_disposition,
    group: conditions[e.id][0],
    acceptance: conditions[e.id][1],
    existing_evidence: e.evidence,
    evidence: [],
    attempts: [],
    required_browser:
      'Authenticated installed Chrome/Edge, 1440px desktop and 390px touch/mobile; actual actions, reload, screenshots, traces and axe. API-only proof is insufficient.',
    required_persistence:
      'Owned canonical API identities plus read-only ORM snapshots; exact versions/status/history/provenance; anonymous denial. No raw SQL fixture fabrication.',
    final_disposition: 'PENDING_EXECUTION',
  })),
};
await fs
  .writeFile(root + 'wp7a5-coverage-ledger.json', JSON.stringify(ledger, null, 2), { flag: 'wx' })
  .catch((e) => {
    if (e.code !== 'EEXIST') throw e;
  });
console.log(
  JSON.stringify({ original: 48, inherited_closed: 32, targeted: entries.map((e) => e.id) }),
);
