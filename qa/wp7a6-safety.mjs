// Offline metadata, exact review and authorization only. No submit/dispatch/import/execute/release.
const uuid = '[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}';
export function wp7a6Path(p, m) {
  if (!['POST', 'PATCH', 'PUT', 'DELETE'].includes(m)) return false;
  if (m === 'DELETE')
    return new RegExp(
      `^/api/v1/(ads/accounts/${uuid}/credentials|campaigns/${uuid}/dependencies/${uuid})$`,
    ).test(p);
  const patterns = [
    `^/api/v1/marketplaces/(amazon|flipkart|meesho)/accounts(?:/${uuid}(?:/(validate|revalidate|enable|disable|credentials?|disconnect))?)?$`,
    `^/api/v1/marketplaces/(amazon|flipkart|meesho)/listings/${uuid}/(preview|prepare|review|execution-authorizations(?:/${uuid}/revoke)?)$`,
    `^/api/v1/marketplaces/listings/${uuid}(?:/(variants|media|price))?$`,
    `^/api/v1/campaigns/${uuid}/(dependencies(?:/${uuid})?|activities/${uuid}|recovery/(reschedule-activity|create-one-catch-up)/(preview|confirm))$`,
    `^/api/v1/ads/(creatives(?:/${uuid})?|accounts/${uuid}(?:/(disable|credentials))?)$`,
    `^/api/v1/social/posts/${uuid}(?:/(approve|revoke))?$`,
  ];
  return patterns.some((v) => new RegExp(v).test(p));
}
export function safeWp7a6Payload(p, b) {
  if (!b || typeof b !== 'object' || Array.isArray(b)) return false;
  if (
    ['execute', 'dispatch', 'publish_now', 'api_key', 'password', 'access_token'].some(
      (k) => k in b,
    )
  )
    return false;
  if (
    b.credentials &&
    !(
      Object.keys(b.credentials).length === 0 ||
      (Object.keys(b.credentials).length === 1 &&
        b.credentials.token === 'QA-SYNTHETIC-NOT-A-REAL-CREDENTIAL')
    )
  )
    return false;
  if (p.startsWith('/__qa/')) return false;
  if (/\/accounts$/.test(p))
    return (
      ['local', 'sandbox'].includes(b.environment) &&
      b.display_name?.startsWith('[QA SYNTHETIC]') &&
      b.seller_account_id?.startsWith('qa6-')
    );
  if (p.includes('execution-authorizations')) {
    if (p.endsWith('/revoke'))
      return Object.keys(b).every((k) => k === 'confirm') && b.confirm === true;
    return (
      b.confirm === true &&
      /^[a-f0-9-]{36}$/.test(b.review_id) &&
      /^(wp7a6-|amazon-ui-submit-|flipkart-ui-submit-)/.test(b.idempotency_key || '') &&
      Number.isInteger(b.expires_seconds) &&
      b.expires_seconds >= 60 &&
      b.expires_seconds <= 900
    );
  }
  return true;
}
