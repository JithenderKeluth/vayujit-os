// WP7A3 permits local artifact preparation/review only; never dispatch or credentials.
export function wp7a3Path(p, m) {
  if (p === '/__qa/wp7a3/control') return m === 'POST';
  if (m === 'PATCH' && /^\/api\/v1\/ai\/studio\/artifacts\/[a-f0-9-]+$/.test(p)) return true;
  if (m !== 'POST') return false;
  return [
    /^\/api\/v1\/ai\/generations$/,
    /^\/api\/v1\/ai\/(?:studio\/)?artifacts\/[a-f0-9-]+\/(approve|reject|regenerate|campaign-handoff)$/,
    /^\/api\/v1\/ai\/studio\/(generate|seo\/analyze|keywords|tags|bulk(?:\/preview)?|recovery\/actions)$/,
    /^\/api\/v1\/ai\/seo\/(analyze|keywords|keywords\/suggestions|tags)$/,
    /^\/api\/v1\/ai\/studio\/bulk\/[a-f0-9-]+\/(cancel|retry-failed)$/,
    /^\/api\/v1\/ai\/images\/(generate|bulk(?:\/preview)?)$/,
    /^\/api\/v1\/ai\/images\/outputs\/[a-f0-9-]+\/(approve|reject|regenerate)$/,
    /^\/api\/v1\/campaigns(?:\/[a-f0-9-]+\/(activities|validate|dependencies))?$/,
  ].some((r) => r.test(p));
}
export function safeWp7a3Payload(p, b) {
  if (!b || typeof b !== 'object' || Array.isArray(b)) return false;
  if (p === '/__qa/wp7a3/control')
    return (
      ['WORKER_SUCCESS', 'WORKER_FAIL'].includes(b.scenario) &&
      Object.keys(b).every((k) => k === 'scenario')
    );
  if (
    b.credentials ||
    b.confirm_execution ||
    b.publish ||
    b.dispatch ||
    b.provider_key === 'openai_compatible'
  )
    return false;
  if (b.provider && !['deterministic_mock_v1', 'meta'].includes(b.provider)) return false;
  if (p.endsWith('/recovery/actions'))
    return (
      ['retry_generation', 'review_failure'].includes(b.action) &&
      Object.keys(b).every((k) => ['action', 'job_id', 'generation_id'].includes(k))
    );
  if (p === '/api/v1/campaigns')
    return b.name?.startsWith('[QA SYNTHETIC] WP7A3') && b.timezone_name === 'Asia/Kolkata';
  if (p.endsWith('/activities'))
    return (
      ['review_checkpoint', 'approval_checkpoint'].includes(b.activity_type) && !b.destination_id
    );
  if (p.includes('/images/') && b.output_count > 2) return false;
  if (b.product_ids && b.product_ids.length > 2) return false;
  if (
    b.channels &&
    b.channels.some((c) => !['canonical', 'amazon', 'flipkart', 'meesho'].includes(c))
  )
    return false;
  return true;
}
