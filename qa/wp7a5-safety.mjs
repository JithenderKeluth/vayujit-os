// Only metadata/review/recovery through canonical local authorities. No dispatch.
export function wp7a5Path(p, m) {
  if (p === '/__qa/wp7a3/control') return m === 'POST';
  if (!['POST', 'PUT', 'PATCH'].includes(m)) return false;
  return [
    /^\/api\/v1\/ai\/video\/channels\/(preview|prepare|[a-f0-9-]+\/confirm)$/,
    /^\/api\/v1\/intelligence\/trends\/contexts$/,
    /^\/api\/v1\/ai\/seo\/(keywords|tags)(?:\/[a-f0-9-]+)?$/,
    /^\/api\/v1\/ai\/seo\/(analyze|analyses\/[a-f0-9-]+\/reanalyze)$/,
    /^\/api\/v1\/intelligence\/trends\/contexts\/[a-f0-9-]+\/observations$/,
    /^\/api\/v1\/intelligence\/sources$/,
    /^\/api\/v1\/social\/accounts\/[a-f0-9-]+\/(enable|validate)$/,
    /^\/api\/v1\/social\/posts\/[a-f0-9-]+$/,
    /^\/api\/v1\/ads\/marketing\/plans\/[a-f0-9-]+\/budget\/(preview|confirm)$/,
  ].some((r) => r.test(p));
}
export function safeWp7a5Payload(p, b) {
  if (!b || typeof b !== 'object' || Array.isArray(b)) return false;
  if (
    [
      'credentials',
      'api_key',
      'token',
      'access_token',
      'password',
      'execute',
      'dispatch',
      'publish_now',
    ].some((k) => k in b)
  )
    return false;
  if (/\/video\/channels\/[a-f0-9-]+\/confirm$/.test(p))
    return (
      b.confirm === true &&
      /^[a-f0-9]{64}$/.test(b.fingerprint) &&
      Object.keys(b).every((k) => ['confirm', 'fingerprint'].includes(k))
    );
  if (p.includes('/video/channels/'))
    return (
      ['youtube', 'instagram', 'facebook'].includes(b.channel) &&
      b.idempotency_key?.startsWith('social-video-prepare-') &&
      !b.execute
    );
  if (p.endsWith('/trends/contexts'))
    return (
      b.name?.startsWith('[QA SYNTHETIC] WP7A5') && b.idempotency_key?.startsWith('wp7a5-trend-')
    );
  if (p === '/__qa/wp7a3/control')
    return (
      ['WORKER_SUCCESS', 'WORKER_FAIL'].includes(b.scenario) &&
      Object.keys(b).every((k) => ['scenario', 'limit'].includes(k)) &&
      (b.limit == null || (Number.isInteger(b.limit) && b.limit >= 1 && b.limit <= 16))
    );
  if (p.endsWith('/observations'))
    return (
      b.raw_metadata?.synthetic === true &&
      b.verification_state === 'UNKNOWN' &&
      b.provenance_note?.startsWith('[QA SYNTHETIC]')
    );
  if (p.endsWith('/intelligence/sources'))
    return (
      b.provider === 'LOCAL_FIXTURE' &&
      b.access_method === 'manual_entry' &&
      b.display_name?.startsWith('[QA SYNTHETIC]') &&
      !b.base_url
    );
  return true;
}
