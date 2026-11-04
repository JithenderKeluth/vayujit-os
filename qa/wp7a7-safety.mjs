// Only local preparation/review. Remote submission, dispatch and publication stay denied.
const id = '[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}';
export function wp7a7Path(p, m) {
  if (p === '/__qa/wp7a7/expire-authorization') return m === 'POST';
  if (p === '/__qa/wp7a7/interrupted-activity') return m === 'POST';
  if (m === 'POST') return [
    `^/api/v1/marketplaces/listings$`,
    `^/api/v1/marketplaces/(flipkart|meesho)/listings$`,
    `^/api/v1/ai/images/outputs/${id}/handoff(?:/preview)?$`,
    `^/api/v1/ai/studio/artifacts/${id}/campaign-handoff$`,
    `^/api/v1/ads/(creatives/readiness|campaigns/${id}/creatives)$`,
    `^/api/v1/campaigns/recovery/actions$`,
  ].some(r => new RegExp(r).test(p));
  return m === 'PUT' && new RegExp(`^/api/v1/marketplaces/(amazon|flipkart|meesho)/listings/${id}/(variants|media|pricing)$`).test(p) && !p.includes('/amazon/') ||
    m === 'PUT' && new RegExp(`^/api/v1/marketplaces/amazon/listings/${id}/(variants|pricing)$`).test(p);
}
export function safeWp7a7Payload(p, b) {
  if (!b || typeof b !== 'object' || Array.isArray(b)) return false;
  if (['credentials','api_key','password','token','access_token','execute','dispatch','publish_now'].some(k => k in b)) return false;
  if (p === '/__qa/wp7a7/expire-authorization') return ['amazon','flipkart'].includes(b.channel) && new RegExp('^'+id+'$').test(b.authorization_id) && Object.keys(b).every(k=>['channel','authorization_id'].includes(k));
  if (p === '/__qa/wp7a7/interrupted-activity') return new RegExp('^'+id+'$').test(b.activity_id) && Object.keys(b).length===1;
  if (p === '/api/v1/campaigns/recovery/actions') return b.action === 'reschedule_activity' && b.confirm === true &&
    new RegExp('^'+id+'$').test(b.campaign_id) && new RegExp('^'+id+'$').test(b.activity_id) &&
    Number.isInteger(b.expected_activity_row_version) && b.expected_activity_row_version > 0 &&
    /^[a-f0-9]{64}$/.test(b.preview_fingerprint || '') && b.reason?.startsWith('[QA SYNTHETIC]') &&
    Object.keys(b).every(k=>['action','campaign_id','activity_id','expected_activity_row_version','reason','confirm','proposed_local_datetime','proposed_timezone','fold','preview_fingerprint'].includes(k));
  if (/\/listings$/.test(p)) return (p !== '/api/v1/marketplaces/listings' || b.prepare_only === true) && b.title?.startsWith('[QA SYNTHETIC]') && [b.product_id,b.brand_id,b.account_id,b.artifact_id].every(v => new RegExp('^'+id+'$').test(v));
  if (p.includes('/handoff')) return ['amazon','flipkart','meesho'].includes(b.marketplace) && new RegExp('^'+id+'$').test(b.listing_id) && /^(wp7a7-|amazon-image-)/.test(b.idempotency_key || '');
  return true;
}
