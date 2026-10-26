export const allowedMutations = [
  /^\/api\/v1\/auth\/(setup-owner|login|logout)$/,
  /^\/api\/v1\/brands(?:\/[a-f0-9-]+)?$/,
  /^\/api\/v1\/products(?:\/[a-f0-9-]+)?$/,
  /^\/api\/v1\/intelligence\/business-agent\/goals$/,
  /^\/api\/v1\/intelligence\/business-agent\/goals\/[a-f0-9-]+\/plan$/,
];

export const phase2Mutations = [
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

export const journeyContextPath =
  /^\/api\/v1\/intelligence\/(trends|reviews|competitors)\/contexts$/;
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
