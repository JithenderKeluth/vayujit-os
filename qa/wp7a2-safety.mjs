// Additional *offline disposable* actions only. Production authorities stay intact.
export function wp7a2Path(p, m) {
  return (
    m === 'POST' &&
    (p === '/__qa/wp7a2/control' ||
      /^\/api\/v1\/ai\/video\/storyboards\/[a-f0-9-]+\/approve$/.test(p) ||
      /^\/api\/v1\/ai\/video\/generations\/[a-f0-9-]+\/recovery$/.test(p) ||
      [
        '/api/v1/ads/accounts',
        '/api/v1/ads/campaigns/preview',
        '/api/v1/ads/campaigns/confirm',
        '/api/v1/ads/recovery',
      ].includes(p) ||
      /^\/api\/v1\/ads\/accounts\/[a-f0-9-]+\/(validate|enable)$/.test(p))
  );
}
export function safeWp7a2Payload(p, b) {
  if (!b || typeof b !== 'object' || Array.isArray(b)) return false;
  if (p === '/__qa/wp7a2/control')
    return (
      ['VIDEO_FAILURE', 'ADS_FAILURE'].includes(b.scenario) &&
      Object.keys(b).every((k) => ['scenario', 'id'].includes(k)) &&
      /^[a-f0-9-]{36}$/.test(b.id)
    );
  if (p.endsWith('/approve'))
    return (
      Number.isInteger(b.expected_row_version) &&
      b.expected_row_version > 0 &&
      Object.keys(b).length === 1
    );
  if (p.includes('/video/') && p.endsWith('/recovery'))
    return (
      b.action === 'retry_generation' &&
      b.idempotency_key?.startsWith('video-retry:') &&
      ['failed', 'retry_wait'].includes(b.expected_status) &&
      b.expected_failure_code === 'ai.video.provider_unavailable' &&
      Object.keys(b).every((k) =>
        ['action', 'idempotency_key', 'expected_status', 'expected_failure_code'].includes(k),
      )
    );
  if (p === '/api/v1/ads/accounts')
    return (
      b.environment === 'local' &&
      b.provider === 'meta' &&
      b.external_account_id?.startsWith('qa-wp7a2-') &&
      b.display_name?.startsWith('[QA SYNTHETIC] WP7A2') &&
      b.credentials?.token === 'QA-SYNTHETIC-NOT-A-REAL-CREDENTIAL' &&
      Object.keys(b.credentials).length === 1
    );
  if (p.endsWith('/preview'))
    return (
      b.provider === 'meta' &&
      b.name?.startsWith('[QA SYNTHETIC] WP7A2') &&
      !b.confirm &&
      !b.credentials
    );
  if (p.endsWith('/confirm'))
    return (
      b.confirm === true &&
      typeof b.preview_fingerprint === 'string' &&
      safeWp7a2Payload('/api/v1/ads/campaigns/preview', b.campaign)
    );
  if (p === '/api/v1/ads/recovery')
    return (
      b.confirm === true &&
      b.action === 'retry' &&
      b.entity_type === 'campaign' &&
      b.failure_code === 'ads.connector_unavailable' &&
      b.idempotency_key?.startsWith('ads-recovery-retry-')
    );
  return Object.keys(b).length === 0;
}
