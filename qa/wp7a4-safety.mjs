// Local preparation/review only; no real credentials, dispatch or publication.
export function wp7a4Path(p, m) {
  if (p === '/__qa/wp7a4/prepare') return m === 'POST';
  if (!['POST', 'PATCH', 'PUT'].includes(m)) return false;
  return [
    /^\/api\/v1\/ai\/studio\/(brand-voices|presets)(?:\/[a-f0-9-]+(?:\/(duplicate|default|archive|restore|preview))?)?$/,
    /^\/api\/v1\/ai\/seo\/(keywords|tags)(?:\/[a-f0-9-]+\/(duplicate|archive))?$/,
    /^\/api\/v1\/ai\/seo\/analyses\/[a-f0-9-]+\/reanalyze$/,
    /^\/api\/v1\/ai\/images\/bulk\/[a-f0-9-]+\/(retry-failed|cancel)$/,
    /^\/api\/v1\/ai\/video\/bulk(?:\/(preview|enqueue))?$/,
    /^\/api\/v1\/ai\/video\/generations\/[a-f0-9-]+\/approve$/,
    /^\/api\/v1\/ai\/video\/bulk\/[a-f0-9-]+\/(retry-failed|cancel)$/,
    /^\/api\/v1\/publishing\/destinations(?:\/[a-f0-9-]+(?:\/(enable|disable))?)?$/,
    /^\/api\/v1\/social\/(accounts|posts)$/,
    /^\/api\/v1\/social\/posts\/[a-f0-9-]+\/(preview|approve)$/,
    /^\/api\/v1\/workflows(?:\/[a-f0-9-]+\/(start|cancel))?$/,
    /^\/api\/v1\/intelligence\/supplier-portfolios$/,
    /^\/api\/v1\/intelligence\/supplier-portfolios\/[a-f0-9-]+\/assess$/,
    /^\/api\/v1\/intelligence\/supplier-portfolios\/[a-f0-9-]+\/members$/,
    /^\/api\/v1\/intelligence\/suppliers\/manual$/,
    /^\/api\/v1\/intelligence\/cross-marketplace\/suppliers\/reconcile$/,
    /^\/api\/v1\/intelligence\/trends\/contexts\/[a-f0-9-]+\/(snapshots|analyses)$/,
    /^\/api\/v1\/campaigns\/[a-f0-9-]+\/activities$/,
    /^\/api\/v1\/brands\/[a-f0-9-]+\/activate$/,
    /^\/api\/v1\/marketplaces\/listings$/,
    /^\/api\/v1\/ads\/marketing\/plans\/(preview|confirm)$/,
  ].some((r) => r.test(p));
}
export function safeWp7a4Payload(p, b) {
  if (!b || typeof b !== 'object' || Array.isArray(b)) return false;
  if (p === '/__qa/wp7a4/prepare')
    return (
      Object.keys(b).every((k) => ['artifact_id'].includes(k)) &&
      /^[a-f0-9-]{36}$/.test(b.artifact_id)
    );
  if (b.credentials && Object.keys(b.credentials).length) return false;
  if (
    b.api_key ||
    b.access_token ||
    b.password ||
    b.dispatch ||
    b.publish_now ||
    b.execute ||
    b.provider_key === 'openai_compatible'
  )
    return false;
  if (p === '/api/v1/marketplaces/listings')
    return (
      b.idempotency_key?.startsWith('wp7a4-listing-') &&
      b.title?.startsWith('[QA SYNTHETIC]') &&
      Boolean(b.account_id && b.product_id && b.brand_id && b.artifact_id)
    );
  if (p.includes('/marketing/plans/'))
    return (
      b.plan?.automation_mode === 'manual' &&
      b.plan?.strategy_mode === 'manual' &&
      b.plan?.product_ids?.length === 1 &&
      b.plan?.idempotency_key?.startsWith('web-marketing-plan-')
    );
  if (p.includes('/publishing/destinations'))
    return !b.connector_key || b.connector_key === 'mock_publisher_v1';
  if (/\/video\/generations\/[a-f0-9-]+\/approve$/.test(p))
    return (
      Object.keys(b).every((k) => k === 'feedback') &&
      (b.feedback == null || typeof b.feedback === 'string')
    );
  if (p.endsWith('/suppliers/manual'))
    return (
      b.display_name?.startsWith('[QA SYNTHETIC] WP7A4') &&
      b.provenance?.includes('synthetic') &&
      !b.website
    );
  if (p.endsWith('/suppliers/reconcile'))
    return Array.isArray(b.supplier_ids) && b.supplier_ids.length === 1;
  if (/\/supplier-portfolios\/[a-f0-9-]+\/members$/.test(p))
    return (
      b.evidence_freshness === 'unknown' && b.allocation_percent == null && b.confidence == null
    );
  if (/\/brands\/[a-f0-9-]+\/activate$/.test(p)) return Object.keys(b).length === 0;
  if (p.endsWith('/activities'))
    return (
      ['review_checkpoint', 'approval_checkpoint', 'mock_publish'].includes(b.activity_type) ||
      (b.activity_type === 'video_campaign' &&
        Boolean(b.video_generation_id && b.video_output_id && b.video_media_id) &&
        !b.video_target_account_id &&
        !b.video_target_listing_id)
    );
  if (p === '/api/v1/social/accounts')
    return (
      b.environment === 'local' &&
      b.display_name?.startsWith('[QA SYNTHETIC]') &&
      b.remote_account_id?.startsWith('qa-')
    );
  if (p.includes('/video/bulk'))
    return (
      (!b.product_ids || b.product_ids.length === 1) &&
      (!b.video_types || (b.video_types.length >= 1 && b.video_types.length <= 2)) &&
      (!b.targets || b.targets.length === 1) &&
      (!b.duration_seconds || b.duration_seconds <= 3)
    );
  return true;
}
