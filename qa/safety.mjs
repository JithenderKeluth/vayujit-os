import { wp7aPath } from './wp7a-safety.mjs';
import { wp7a3Path } from './wp7a3-safety.mjs';
import { wp7a4Path } from './wp7a4-safety.mjs';
import { wp7a5Path } from './wp7a5-safety.mjs';
import { wp7a6Path } from './wp7a6-safety.mjs';
import { wp7a7Path } from './wp7a7-safety.mjs';
import { wp7a2Path } from './wp7a2-safety.mjs';
export const allowedMutations = [
  /^\/api\/v1\/auth\/(setup-owner|login|logout)$/,
  /^\/api\/v1\/brands(?:\/[a-f0-9-]+)?$/,
  /^\/api\/v1\/products(?:\/[a-f0-9-]+)?$/,
  /^\/api\/v1\/intelligence\/business-agent\/goals$/,
  /^\/api\/v1\/intelligence\/business-agent\/goals\/[a-f0-9-]+\/plan$/,
];

// The host must allow the already bounded guarded DROP to finish before killing
// its own fixture child. This changes no database identity/deletion authority.
export function cleanupWaitMs(value) {
  if (value === undefined) return 45000;
  if (!/^\d+$/.test(String(value))) throw new Error('QA_DELETE_TIMEOUT_DENIED');
  const timeout = Number(value);
  if (!Number.isInteger(timeout) || timeout < 15000 || timeout > 90000)
    throw new Error('QA_DELETE_TIMEOUT_DENIED');
  return timeout + 30000;
}

export const phase2Mutations = [
  // Local preparation records only: never dispatch, contact, execute or approve.
  /^\/api\/v1\/intelligence\/sourcing\/(requirements|rfqs|quotes)$/,
  /^\/api\/v1\/intelligence\/product-opportunities\/score\/(compare|rank)$/,
  /^\/api\/v1\/intelligence\/business-agent\/goals\/[a-f0-9-]+\/runs$/,
  /^\/api\/v1\/intelligence\/sourcing-economics\/customs-tax\/(contexts|rates|snapshots)$/,
  /^\/api\/v1\/intelligence\/sourcing-economics\/(contexts|snapshots(?:\/[a-f0-9-]+\/calculate)?)$/,
  /^\/api\/v1\/intelligence\/product-opportunities(?:\/[a-f0-9-]+)?$/,
  /^\/api\/v1\/intelligence\/product-opportunities\/[a-f0-9-]+\/(constraints|assessments|recommendation-assessment|human-decision)$/,
  /^\/api\/v1\/intelligence\/product-opportunities\/[a-f0-9-]+\/assessments\/[a-f0-9-]+\/(score|decision|commercial-readiness|landed-cost|commercial\/unit-economics)$/,
  /^\/api\/v1\/intelligence\/suppliers\/research$/,
  /^\/api\/v1\/intelligence\/cross-marketplace\/suppliers\/reconcile$/,
  /^\/api\/v1\/intelligence\/supplier-shortlisting\/contexts(?:\/[a-f0-9-]+\/(shortlists|decisions))?$/,
  /^\/api\/v1\/intelligence\/supplier-due-diligence\/contexts\/[a-f0-9-]+\/assess$/,
  /^\/api\/v1\/catalog\/opportunities\/[a-f0-9-]+\/convert$/,
  /^\/api\/v1\/commerce-journeys\/[a-f0-9-]+\/(context-confirmation|decision)$/,
];

// Phase 3 operates only on the runner's freshly marked installation. No connector,
// worker, credential, dispatch, publication or remote-execution routes are allowed.
export const phase3Mutations = [
  /^\/__qa\/restart$/,
  /^\/api\/v1\/marketplaces\/accounts$/,
  /^\/api\/v1\/inventory\/(items|mappings)$/,
  /^\/api\/v1\/inventory\/[a-f0-9-]+\/(adjust|reserve)$/,
  /^\/api\/v1\/inventory\/reservations\/[a-f0-9-]+\/(release|consume)$/,
  /^\/api\/v1\/orders\/fake\/events$/,
  /^\/api\/v1\/financial\/(events|costs|fee-rules|settlements\/reconcile|calculations\/recalculate)$/,
  /^\/api\/v1\/operations\/action-center\/scan$/,
  /^\/api\/v1\/operations\/action-center\/signals\/[a-f0-9-]+\/(acknowledge|resolve|reopen|snooze|action)$/,
];

// WP4 local preparation only. No marketplace adapters, account authorization,
// execution, publishing, imports or arbitrary media mutations are admitted.
export function wp4PreparationRequest(path, method) {
  return (
    (method === 'POST' && /^\/api\/v1\/media$/.test(path)) ||
    (method === 'POST' && /^\/api\/v1\/inventory\/items$/.test(path)) ||
    (method === 'POST' &&
      /^\/api\/v1\/catalog\/products\/[a-f0-9-]+\/(variants|images|listing-drafts)$/.test(path)) ||
    (method === 'PATCH' &&
      /^\/api\/v1\/catalog\/(variants|images|listing-drafts)\/[a-f0-9-]+$/.test(path)) ||
    (method === 'DELETE' && /^\/api\/v1\/catalog\/images\/[a-f0-9-]+$/.test(path)) ||
    (method === 'POST' && /^\/api\/v1\/catalog\/listing-drafts\/[a-f0-9-]+\/review$/.test(path)) ||
    (method === 'POST' && /^\/api\/v1\/intelligence\/sourcing-economics\/quotes$/.test(path))
  );
}

export const journeyContextPath =
  /^\/api\/v1\/intelligence\/(trends|reviews|competitors)\/contexts$/;
export function safeWp6ActivationPayload(payload) {
  return !!payload && !Array.isArray(payload) && typeof payload === 'object' && Object.keys(payload).length === 0;
}
export function wp6aPreparationPath(path, method) {
  return (method === 'POST' && ['/api/v1/ads/accounts','/api/v1/ads/campaigns/preview','/api/v1/ai/video/storyboards','/api/v1/ai/video/styles','/api/v1/ai/video/scripts'].includes(path)) || (method === 'PUT' && /^\/api\/v1\/ai\/video\/storyboards\/[a-f0-9-]+$/.test(path));
}
export function safeWp6aPayload(path, payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return false;
  if (path === '/api/v1/ads/accounts') return payload.environment === 'local' && payload.provider === 'meta' && payload.external_account_id?.startsWith('qa-wp6a-') && payload.display_name?.startsWith('[QA SYNTHETIC] WP6A') && payload.credentials && Object.keys(payload.credentials).length === 0 && Object.keys(payload).every(k=>['provider','environment','external_account_id','display_name','credentials'].includes(k));
  if (path === '/api/v1/ads/campaigns/preview') return payload.name?.startsWith('[QA SYNTHETIC] WP6A') && payload.provider === 'meta' && !payload.confirm && !payload.credentials;
  if (path.endsWith('/styles') || path.endsWith('/scripts')) return payload.name?.startsWith('[QA SYNTHETIC] WP6A') && !payload.credentials;
  return Object.keys(payload).every(k=>['brand_id','product_id','video_type','target_channel','locale','aspect_ratio','resolution','scenes','expected_row_version'].includes(k)) && Array.isArray(payload.scenes) && payload.scenes.every(s=>!s.source_media_id && (s.scene_text || '').startsWith('[QA SYNTHETIC]'));
}
export function safeWp5DestinationPayload(payload) {
  return (
    payload?.connector_key === 'mock_publisher_v1' &&
    typeof payload.name === 'string' &&
    payload.name?.startsWith('[QA SYNTHETIC] WP5') &&
    Object.keys(payload).every((k) => ['connector_key', 'name', 'configuration'].includes(k)) &&
    payload.configuration?.channel_name === 'QA-WP5-LOCAL' &&
    Object.keys(payload.configuration).every((k) => k === 'channel_name')
  );
}
export function safeJourneyContextPayload(path, payload) {
  const kind = path.match(journeyContextPath)?.[1];
  if (!kind || !payload || Array.isArray(payload) || typeof payload !== 'object') return false;
  const fields = {
    trends: [
      'name',
      'subject_type',
      'subject_key',
      'product_id',
      'product_opportunity_id',
      'idempotency_key',
    ],
    reviews: [
      'name',
      'product_id',
      'product_opportunity_id',
      'marketplace',
      'market',
      'status',
      'idempotency_key',
    ],
    competitors: ['subject_type', 'subject_reference', 'marketplace', 'market', 'idempotency_key'],
  }[kind];
  if (!Object.keys(payload).every((k) => fields.includes(k))) return false;
  const id =
    kind === 'competitors'
      ? payload.subject_reference
      : payload.product_opportunity_id || payload.product_id;
  const prefix = { trends: 'trend', reviews: 'review', competitors: 'competitor' }[kind];
  return (
    typeof id === 'string' &&
    /^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(id) &&
    typeof payload.idempotency_key === 'string' &&
    payload.idempotency_key.startsWith(`ux-r11a-${prefix}-${id}`) &&
    (kind !== 'competitors' || ['PRODUCT', 'PRODUCT_OPPORTUNITY'].includes(payload.subject_type)) &&
    (kind !== 'reviews' || payload.status === 'ACTIVE')
  );
}

export function allowRequest(url, method, origin, phase = '1') {
  const parsed = new URL(url);
  if (parsed.origin !== origin) return false;
  if (phase === 'WP7A7') return wp7a7Path(parsed.pathname, method) || allowRequest(url, method, origin, 'WP7A6');
  if (phase === 'WP7A6') return wp7a6Path(parsed.pathname, method) || allowRequest(url, method, origin, 'WP7A5');
  if (phase === 'WP7A5') return wp7a5Path(parsed.pathname, method) || allowRequest(url, method, origin, 'WP7A4');
  if (phase === 'WP7A4') return wp7a4Path(parsed.pathname, method) || allowRequest(url, method, origin, 'WP7A3');
  if (phase === 'WP7A3') return wp7a3Path(parsed.pathname, method) || allowRequest(url, method, origin, 'WP7A2');
  if (phase === 'WP7A2') return wp7a2Path(parsed.pathname, method) || allowRequest(url, method, origin, 'WP7A');
  if (phase === 'WP7A') return wp7aPath(parsed.pathname, method) || allowRequest(url, method, origin, 'WP6B');
  if (phase === 'WP6B') return allowRequest(url, method, origin, 'WP6A');
  if (phase === 'WP6A') return wp6aPreparationPath(parsed.pathname,method) || allowRequest(url,method,origin,'WP6');
  if (phase === 'WP6') {
    return (method === 'POST' && /^\/api\/v1\/products\/[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\/activate$/.test(parsed.pathname)) || allowRequest(url, method, origin, '4');
  }
  if (phase === 'WP5') {
    return (
      (method === 'POST' && parsed.pathname === '/api/v1/publishing/destinations') ||
      allowRequest(url, method, origin, '4')
    );
  }
  if (phase === '4B') {
    return (
      ['GET', 'HEAD', 'OPTIONS'].includes(method) ||
      (['POST', 'PATCH'].includes(method) &&
        allowedMutations.slice(0, 3).some((rule) => rule.test(parsed.pathname))) ||
      (method === 'POST' && /^\/api\/v1\/inventory\/items$/.test(parsed.pathname)) ||
      (method === 'POST' && /^\/api\/v1\/products\/[a-f0-9-]+\/archive$/.test(parsed.pathname)) ||
      (method === 'POST' &&
        /^\/api\/v1\/catalog\/products\/[a-f0-9-]+\/variants$/.test(parsed.pathname))
    );
  }
  // Phase 4 reuses bounded preparation authorities, never owned restart. Account
  // creation is restricted to credential-free synthetic sandbox payloads by proxy.
  if (phase === '4') {
    if (parsed.pathname === '/__qa/restart') return false;
    return (
      wp4PreparationRequest(parsed.pathname, method) ||
      (method === 'POST' && journeyContextPath.test(parsed.pathname)) ||
      allowRequest(url, method, origin, '2') ||
      (method === 'POST' && phase3Mutations.some((r) => r.test(parsed.pathname)))
    );
  }
  return (
    ['GET', 'HEAD', 'OPTIONS'].includes(method) ||
    allowedMutations.some((rule) => rule.test(parsed.pathname)) ||
    (['2', '3'].includes(phase) &&
      ['POST', 'PATCH', 'PUT'].includes(method) &&
      phase2Mutations.some((rule) => rule.test(parsed.pathname))) ||
    (phase === '3' && method === 'POST' && phase3Mutations.some((r) => r.test(parsed.pathname)))
  );
}

export function safeRoute(url) {
  const parsed = new URL(url);
  return parsed.pathname; // Never persist query strings, headers, request bodies, cookies.
}

export function unexpectedServerErrors(signals) {
  return signals.http_errors.filter(
    (error) =>
      error.status >= 500 &&
      !signals.expected_http_errors.some(
        (expected) => expected.path === error.path && expected.status === error.status,
      ),
  );
}

export function certificationStatus(reports, cleanup, perProject = 4) {
  const tests = reports.flatMap((report) => report.tests);
  const complete =
    reports.length === 2 &&
    tests.length === perProject * 2 &&
    reports.every(
      (report) =>
        report.status === 'passed' &&
        report.process_exit_code === 0 &&
        report.tests.length === perProject,
    ) &&
    tests.every((test) => test.status === 'passed') &&
    cleanup.length === 2 &&
    cleanup.every(
      (entry) =>
        entry.status === 'PASS' && entry.child_exit === 0 && entry.proof?.database_absent === true,
    );
  return complete ? 'PASS_BOUNDED_SMOKE' : 'INCOMPLETE';
}

export function phase3ApiComplete(result) {
  return (
    result?.process_exit_code === 0 &&
    result?.tests?.length === 18 &&
    result.tests.every((r) => r.status === 'PASS') &&
    result.passed === 18 &&
    result.failed === 0 &&
    result.errors === 0 &&
    result.skipped === 0
  );
}

export function phase2ApiComplete(result) {
  return (
    result?.process_exit_code === 0 &&
    result?.tests?.length === 11 &&
    result.tests.every((row) => row.status === 'PASS') &&
    result.passed === 11 &&
    result.failed === 0 &&
    result.errors === 0 &&
    result.skipped === 0
  );
}

export function finding(id, values) {
  const required = [
    'feature',
    'route',
    'type',
    'severity',
    'priority',
    'expected',
    'actual',
    'reproduction_steps',
    'evidence',
    'confidence',
    'suggested_fix',
    'retest_status',
  ];
  if (!/^QA-[A-Z0-9-]+$/.test(id) || required.some((key) => values[key] === undefined)) {
    throw new Error('INVALID_QA_FINDING');
  }
  if (!['CONFIRMED', 'SUSPECTED', 'RECOMMENDATION'].includes(values.confidence))
    throw new Error('INVALID_QA_CONFIDENCE');
  return { id, ...values };
}
