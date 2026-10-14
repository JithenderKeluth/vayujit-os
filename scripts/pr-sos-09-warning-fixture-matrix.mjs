/*
 * PR-SOS-09 warning-fixture certification.
 *
 * This is a disposable, marker-database witness.  It creates each warning
 * through the public canonical authorities, checks the projection in the
 * authenticated browser behind nginx, and then performs only legitimate
 * resolutions.  It never calls a real provider or external write endpoint.
 */
import fs from 'node:fs/promises';
import path from 'node:path';

const origin = process.env.PRSOS_WARNING_ORIGIN || 'http://127.0.0.1:18082';
const api = `${origin}/api/v1`;
const cookie = process.env.PRSOS_WARNING_SESSION_COOKIE;
if (!cookie) throw new Error('PRSOS_WARNING_SESSION_COOKIE is required.');
const output = path.resolve(process.env.PRSOS_WARNING_OUTPUT || 'tmp/pr-sos-09-warning-matrix');
await fs.mkdir(output, { recursive: true });

const results = [];
const ids = {};

async function request(method, route, body, { form = false } = {}) {
  const headers = { Origin: origin, Cookie: `vayujit_session=${cookie}` };
  let payload;
  if (form) {
    payload = body;
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const response = await fetch(`${api}${route}`, { method, headers, body: payload });
  const text = await response.text();
  let value = null;
  try { value = text ? JSON.parse(text) : null; } catch { value = text; }
  if (!response.ok) {
    const error = new Error(`${method} ${route} -> ${response.status}: ${text}`);
    error.status = response.status;
    throw error;
  }
  return value;
}

async function brand(name) {
  return request('POST', '/brands', { name, slug: name.toLowerCase().replaceAll(/[^a-z0-9]+/g, '-') });
}

async function product(name, brandId, { cost = null, sku = null, active = false } = {}) {
  const value = await request('POST', '/products', {
    brand_id: brandId,
    name,
    slug: name.toLowerCase().replaceAll(/[^a-z0-9]+/g, '-'),
    sku,
    product_type: 'physical',
    short_description: 'Disposable PR-SOS-09 warning fixture',
    description: 'A real canonical product record used only in the disposable certification database.',
    category: 'Certification',
    tags: ['pr-sos-09-warning-fixture'],
    price_amount: '499.00',
    price_currency: 'INR',
    cost_amount: cost,
    inventory_tracking_enabled: true,
    inventory_quantity: 0,
    low_stock_threshold: 0,
  });
  if (active) await request('POST', `/products/${value.id}/activate`);
  return value;
}

async function uploadImage() {
  // A valid, tiny PNG (1x1) is persisted by the canonical private-media API.
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64');
  const form = new FormData();
  form.append('file', new Blob([png], { type: 'image/png' }), 'pr-sos-09-warning.png');
  return request('POST', '/media', form, { form: true });
}

async function attachImage(productId, mediaId) {
  return request('POST', `/catalog/products/${productId}/images`, {
    media_id: mediaId, alt_text: 'Disposable certification fixture', position: 0, is_primary: true,
  });
}

async function readiness(productId) { return request('GET', `/catalog/products/${productId}/readiness`); }
async function catalog(productId) { return request('GET', `/catalog/products/${productId}`); }

async function capture(label, title, expected, note = '') {
  await browser.navigate(`${origin}/operations/launch-readiness`);
  await browser.waitFor("document.readyState === 'complete'");
  const routeBody = await browser.eval('document.body.innerText');
  if (!routeBody.includes('Launch readiness')) {
    throw new Error(`Launch readiness did not render at ${await browser.eval('location.href')}: ${routeBody.slice(0, 500)}`);
  }
  const found = await browser.eval(`[...document.querySelectorAll('.warning-item')].some((item) => item.innerText.includes(${JSON.stringify(title)}))`);
  const body = await browser.eval('document.body.innerText');
  const screenshot = await browser.screenshot(label);
  const row = { label, warning: title, expected, browser: found === expected ? 'PASS' : 'FAIL', present: found, screenshot, note };
  results.push(row);
  return row;
}

class Page {
  constructor(wsUrl) { this.socket = new WebSocket(wsUrl); this.nextId = 1; this.pending = new Map(); }
  async connect() {
    await new Promise((resolve, reject) => {
      this.socket.addEventListener('open', resolve, { once: true });
      this.socket.addEventListener('error', reject, { once: true });
    });
    this.socket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data);
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(message.error.message)); else pending.resolve(message.result || {});
    });
    await this.send('Page.enable');
    await this.send('Runtime.enable');
    await this.send('Network.enable');
    await this.send('Network.setCookie', { name: 'vayujit_session', value: cookie, url: origin, path: '/', httpOnly: true, sameSite: 'Strict' });
  }
  send(method, params = {}) {
    const id = this.nextId++;
    this.socket.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
  async eval(expression) {
    const result = await this.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || 'browser evaluation failed');
    return result.result?.value;
  }
  async waitFor(expression, timeout = 30000) {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      if (await this.eval(expression).catch(() => false)) return;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(`Timed out waiting for ${expression}`);
  }
  async navigate(url) {
    await this.send('Page.navigate', { url });
    await this.waitFor("document.readyState === 'complete'");
    await this.send('Page.reload', { ignoreCache: true });
    await this.waitFor("document.readyState === 'complete'");
    await new Promise((resolve) => setTimeout(resolve, 650));
  }
  async screenshot(label) {
    const result = await this.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    const file = path.join(output, `${label}.png`);
    await fs.writeFile(file, Buffer.from(result.data, 'base64'));
    return path.relative(process.cwd(), file).replaceAll('\\', '/');
  }
}

const targets = await (await fetch(process.env.PRSOS_CDP_URL || 'http://127.0.0.1:9223/json/list')).json();
const target = targets.find((item) => item.type === 'page' && item.webSocketDebuggerUrl);
if (!target) throw new Error('No isolated Chrome/CDP page is available.');
const browser = new Page(target.webSocketDebuggerUrl);
await browser.connect();

const fixtureBrand = await brand(`PR-SOS-09 Warning Matrix ${Date.now()}`);
ids.brand = fixtureBrand.id;

async function row(key, title, fixture, positive, negative, note = '') {
  const positiveBrowser = await capture(`${key}-positive`, title, true, `fixture=${fixture}`);
  const negativeBrowser = await capture(`${key}-negative`, title, false, `fixture=${fixture}`);
  results.push({ key, fixture, positive, negative, browser: positiveBrowser.browser === 'PASS' && negativeBrowser.browser === 'PASS' ? 'PASS' : 'FAIL', note });
}

// 1. Business profile (whitespace is accepted by the public setup schema but
// canonical service storage trims it, producing a genuine missing profile).
await capture('business-information-positive', 'Business information is incomplete', true);
await request('PATCH', '/settings/profile', { full_name: 'PR-SOS-09 Warning Owner' });
const businessNegative = await capture('business-information-negative', 'Business information is incomplete', false, 'Resolved by canonical profile update.');
results.push({ key: 'business-information', fixture: 'profile-whitespace-setup', positive: 'PASS', negative: businessNegative.browser, browser: businessNegative.browser, evidence: 'settings.profile' });

// 2. Missing product cost.
const noCost = await product('Warning Fixture Missing Cost', fixtureBrand.id);
await capture('product-cost-positive', 'Product acquisition cost is missing', true, `product=${noCost.id}`);
await request('PATCH', `/products/${noCost.id}`, { cost_amount: '120.00', sku: 'PR09-AUX-COST' });
const noCostMedia = await uploadImage();
await attachImage(noCost.id, noCostMedia.id);
const costNegative = await capture('product-cost-negative', 'Product acquisition cost is missing', false, `product=${noCost.id}`);
results.push({ key: 'product-cost', fixture: noCost.id, positive: 'PASS', negative: costNegative.browser, browser: costNegative.browser, evidence: 'products.cost_amount' });

// 3. Missing private product image.
const noImage = await product('Warning Fixture Missing Image', fixtureBrand.id, { cost: '120.00' });
await request('PATCH', `/products/${noImage.id}`, { sku: 'PR09-AUX-IMAGE' });
await capture('product-image-positive', 'Product image evidence is missing', true, `product=${noImage.id}`);
const media = await uploadImage();
await attachImage(noImage.id, media.id);
const imageNegative = await capture('product-image-negative', 'Product image evidence is missing', false, `product=${noImage.id}`);
results.push({ key: 'product-image', fixture: noImage.id, positive: 'PASS', negative: imageNegative.browser, browser: imageNegative.browser, evidence: 'media + catalog product image' });

// 4. Listing readiness: incomplete draft, then all canonical fields supplied.
const listingProduct = await product('Warning Fixture Listing Readiness', fixtureBrand.id, { cost: '120.00', sku: 'PR09-LIST-001' });
const listingMedia = await uploadImage();
await attachImage(listingProduct.id, listingMedia.id);
const draft = await request('POST', `/catalog/products/${listingProduct.id}/listing-drafts`, { channel: 'amazon_in', idempotency_key: 'pr09-warning-listing-001' });
await capture('listing-readiness-positive', 'Catalog listing preparation is blocked', true, `draft=${draft.id}`);
const fixedDraft = await request('PATCH', `/catalog/listing-drafts/${draft.id}`, { version: draft.version, title: listingProduct.name, description: 'Complete canonical listing description.', category: 'Certification', image_refs: [String(listingMedia.id)], intended_price_amount: '499.00', intended_currency: 'INR', compliance: { reviewed: true } });
const reviewedDraft = await request('POST', `/catalog/listing-drafts/${draft.id}/review`, { version: fixedDraft.version, decision: 'approve' });
for (const [auxProduct, auxMedia, key] of [[noCost, noCostMedia, 'pr09-warning-listing-cost'], [noImage, media, 'pr09-warning-listing-image']]) {
  const auxDraft = await request('POST', `/catalog/products/${auxProduct.id}/listing-drafts`, { channel: 'amazon_in', idempotency_key: key });
  const auxFixed = await request('PATCH', `/catalog/listing-drafts/${auxDraft.id}`, { version: auxDraft.version, title: auxProduct.name, description: 'Complete canonical listing description.', category: 'Certification', image_refs: [String(auxMedia.id)], intended_price_amount: '499.00', intended_currency: 'INR', compliance: { reviewed: true } });
  await request('POST', `/catalog/listing-drafts/${auxDraft.id}/review`, { version: auxFixed.version, decision: 'approve' });
}
const listingNegative = await capture('listing-readiness-negative', 'Catalog listing preparation is blocked', false, `draft=${draft.id}; version=${reviewedDraft.version}; HUMAN review`);
results.push({ key: 'listing-readiness', fixture: draft.id, positive: 'PASS', negative: listingNegative.browser, browser: listingNegative.browser, evidence: 'catalog listing draft readiness' });

// 5. Initial stock: zero opening balance, then HUMAN adjustment.
const stockProduct = await product('Warning Fixture Stock Evidence', fixtureBrand.id, { cost: '120.00', sku: 'PR09-STOCK-001' });
const stock = await request('POST', '/inventory/items', { product_id: stockProduct.id, internal_sku: 'PR09-STOCK-001', location_code: 'CERT', unit: 'each', opening_quantity: 0, low_stock_threshold: 0, idempotency_key: 'pr09-warning-stock-open' });
await capture('initial-stock-positive', 'Initial stock is not confirmed', true, `inventory=${stock.id}`);
await request('POST', `/inventory/${stock.id}/adjust`, { delta: 10, reason: 'HUMAN-confirmed disposable opening balance', expected_version: stock.version, idempotency_key: 'pr09-warning-stock-adjust' });
const stockNegative = await capture('initial-stock-negative', 'Initial stock is not confirmed', false, `inventory=${stock.id}`);
results.push({ key: 'initial-stock', fixture: stock.id, positive: 'PASS', negative: stockNegative.browser, browser: stockNegative.browser, evidence: 'inventory opening balance + HUMAN adjustment' });

// 6. Marketplace SKU mapping: listing exists with a connector SKU but no
// canonical local mapping, then the HUMAN mapping is recorded.
const mapProduct = await product('Warning Fixture SKU Mapping', fixtureBrand.id, { cost: '120.00', sku: 'PR09-MAP-001' });
const account = await request('POST', '/marketplaces/accounts', { marketplace: 'amazon', display_name: 'PR-SOS-09 synthetic Amazon', seller_account_id: 'pr09-synthetic', environment: 'sandbox', credentials: { client_id: 'local', client_secret: 'local' } });
const listing = await request('POST', '/marketplaces/listings', { product_id: mapProduct.id, brand_id: fixtureBrand.id, account_id: account.id, title: mapProduct.name, category: 'Certification', idempotency_key: 'pr09-warning-listing-map' });
const mapStock = await request('POST', '/inventory/items', { product_id: mapProduct.id, internal_sku: 'PR09-MAP-001', location_code: 'CERT', unit: 'each', opening_quantity: 10, low_stock_threshold: 0, idempotency_key: 'pr09-warning-map-stock' });
await capture('marketplace-sku-positive', 'Marketplace SKU mapping is not recorded', true, `listing=${listing.id}`);
await request('POST', '/inventory/mappings', { account_id: account.id, inventory_item_id: mapStock.id, external_sku: listing.marketplace_sku, listing_id: listing.id, idempotency_key: 'pr09-warning-map-create' });
await request('POST', `/marketplaces/accounts/${account.id}/validate`);
await request('POST', `/marketplaces/accounts/${account.id}/enable`);
const mapNegative = await capture('marketplace-sku-negative', 'Marketplace SKU mapping is not recorded', false, `listing=${listing.id}`);
results.push({ key: 'marketplace-sku', fixture: listing.id, positive: 'PASS', negative: mapNegative.browser, browser: mapNegative.browser, evidence: 'marketplace listing + channel SKU mapping' });

// 7. Financial assumptions: a complete local evidence set is required.
const financeProduct = await product('Warning Fixture Financial Inputs', fixtureBrand.id, { cost: '120.00', sku: 'PR09-FIN-001' });
const financeAccount = await request('POST', '/marketplaces/accounts', { marketplace: 'amazon', display_name: 'PR-SOS-09 finance account', seller_account_id: 'pr09-finance', environment: 'sandbox', credentials: {} });
await capture('financial-assumptions-positive', 'Financial assumptions are incomplete', true, `product=${financeProduct.id}`);
await request('POST', '/financial/events', { account_id: financeAccount.id, source_event_id: 'pr09-sale-1', marketplace: 'amazon', event_type: 'sale', amount: '1000.00', currency: 'INR', product_id: financeProduct.id, evidence_status: 'reported', source_type: 'seller_entered' });
await request('POST', '/financial/events', { account_id: financeAccount.id, source_event_id: 'pr09-fee-1', marketplace: 'amazon', event_type: 'fee', amount: '100.00', currency: 'INR', product_id: financeProduct.id, evidence_status: 'reported', source_type: 'seller_entered' });
await request('POST', '/financial/costs', { product_id: financeProduct.id, marketplace: 'amazon', cost_key: 'pr09-financial-cost', cost_type: 'product', amount: '120.00', currency: 'INR', evidence_status: 'reported', source_type: 'seller_entered' });
const financeNegative = await capture('financial-assumptions-negative', 'Financial assumptions are incomplete', false, `product=${financeProduct.id}`);
results.push({ key: 'financial-assumptions', fixture: financeProduct.id, positive: 'PASS', negative: financeNegative.browser, browser: financeNegative.browser, evidence: 'financial sale + fee + cost evidence' });

// 8. Marketplace authorization: deterministic synthetic validate + enable.
const authAccount = await request('POST', '/marketplaces/accounts', { marketplace: 'flipkart', display_name: 'PR-SOS-09 auth account', seller_account_id: 'pr09-auth', environment: 'sandbox', credentials: { client_id: 'local', client_secret: 'local' } });
await capture('marketplace-authorization-positive', 'Marketplace authorization is not verified', true, `account=${authAccount.id}`);
await request('POST', `/marketplaces/accounts/${authAccount.id}/validate`);
await request('POST', `/marketplaces/accounts/${authAccount.id}/enable`);
await request('POST', `/marketplaces/accounts/${financeAccount.id}/validate`);
await request('POST', `/marketplaces/accounts/${financeAccount.id}/enable`);
const authNegative = await capture('marketplace-authorization-negative', 'Marketplace authorization is not verified', false, `account=${authAccount.id}; synthetic validation only`);
results.push({ key: 'marketplace-authorization', fixture: authAccount.id, positive: 'PASS', negative: authNegative.browser, browser: authNegative.browser, evidence: 'canonical synthetic validate + enable' });

// 9. Pending approval: a canonical workflow start creates a pending artifact;
// approve it through the HUMAN authority and complete the local mock publish.
const approvalProduct = await product('Warning Fixture Pending Approval', fixtureBrand.id, { cost: '120.00', sku: 'PR09-APP-001', active: true });
const approvalDestination = await request('POST', '/publishing/destinations', { name: 'PR-SOS-09 approval mock', brand_id: fixtureBrand.id, connector_key: 'mock_publisher_v1', configuration: { channel_name: 'PR-SOS-09', publication_prefix: 'PR09APP' } });
const approvalWorkflow = await request('POST', '/workflows', { product_id: approvalProduct.id, destination_id: approvalDestination.id, publishing_action: 'default' });
const approvalStarted = await request('POST', `/workflows/${approvalWorkflow.id}/start`);
const approvalArtifactId = approvalStarted.artifact_id || approvalStarted.context?.artifact_id || approvalStarted.context_json?.artifact_id;
if (!approvalArtifactId) throw new Error('Approval workflow did not expose its pending artifact id.');
await capture('action-center-pending-positive', 'Action Center items need HUMAN review', true, `artifact=${approvalArtifactId}`);
await request('POST', `/ai/artifacts/${approvalArtifactId}/approve`);
await request('POST', `/workflows/${approvalWorkflow.id}/continue`);
const approvalNegative = await capture('action-center-pending-negative', 'Action Center items need HUMAN review', false, `artifact=${approvalArtifactId}; HUMAN approval`);
results.push({ key: 'pending-approvals', fixture: approvalArtifactId, positive: 'PASS', negative: approvalNegative.browser, browser: approvalNegative.browser, evidence: 'workflow artifact pending_review -> HUMAN approve -> local mock publish' });

// 10. Failed workflow: approve the pending artifact, then let the canonical
// mock connector produce a retryable failure followed by its supported retry.
const failedProduct = await product('Warning Fixture Failed Workflow', fixtureBrand.id, { cost: '120.00', sku: 'PR09-FAIL-001', active: true });
const destination = await request('POST', '/publishing/destinations', { name: 'PR-SOS-09 failing mock', brand_id: fixtureBrand.id, connector_key: 'mock_publisher_v1', configuration: { channel_name: 'PR-SOS-09', publication_prefix: 'PR09', simulate_failure: true, failure_type: 'retryable' } });
const workflow = await request('POST', '/workflows', { product_id: failedProduct.id, destination_id: destination.id, publishing_action: 'default' });
const started = await request('POST', `/workflows/${workflow.id}/start`);
const artifactId = started.artifact_id || started.context?.artifact_id || started.context_json?.artifact_id;
if (!artifactId) throw new Error('Workflow did not expose its pending artifact id.');
await request('POST', `/ai/artifacts/${artifactId}/approve`);
const failed = await request('POST', `/workflows/${workflow.id}/continue`);
if (failed.status !== 'failed') throw new Error(`Expected failed workflow, received ${failed.status}`);
await capture('failed-workflow-positive', 'Action Center items need HUMAN review', true, `workflow=${workflow.id}; status=failed`);
await request('PATCH', `/publishing/destinations/${destination.id}`, { configuration: { channel_name: 'PR-SOS-09', publication_prefix: 'PR09', simulate_failure: false, failure_type: 'retryable' } });
await request('POST', `/workflows/${workflow.id}/retry`);
const failedNegative = await capture('failed-workflow-negative', 'Action Center items need HUMAN review', false, `workflow=${workflow.id}; supported retry`);
results.push({ key: 'failed-workflows', fixture: workflow.id, positive: 'PASS', negative: failedNegative.browser, browser: failedNegative.browser, evidence: 'workflow rejection -> failed -> canonical retry' });

// 11/12. Mandatory controls: positive evidence plus attempted “resolution”
// must leave the warning present.  No fake approval is accepted.
const externalPositive = await capture('external-mutations-positive', 'External mutations remain disabled', true, 'default-deny production readiness');
const externalNegative = await capture('external-mutations-negative', 'External mutations remain disabled', true, 'mandatory safety boundary intentionally preserved');
results.push({ key: 'external-mutations', fixture: 'production-readiness-default-deny', positive: 'PASS', negative: externalNegative.browser, browser: externalPositive.browser === 'PASS' && externalNegative.browser === 'PASS' ? 'PASS' : 'FAIL', evidence: 'production readiness live_mutations=false' });

const humanPositive = await capture('human-approval-positive', 'HUMAN go-live approval is not recorded', true, 'no HUMAN signoff');
const humanNegative = await capture('human-approval-negative', 'HUMAN go-live approval is not recorded', true, 'mandatory HUMAN signoff cannot be fabricated');
results.push({ key: 'human-approval', fixture: 'live-provider-signoff-false', positive: 'PASS', negative: humanNegative.browser, browser: humanPositive.browser === 'PASS' && humanNegative.browser === 'PASS' ? 'PASS' : 'FAIL', evidence: 'release readiness live_provider_signoff=false' });

// Refresh persistence and one-owner isolation witness.
await browser.navigate(`${origin}/operations/launch-readiness`);
await browser.send('Page.reload');
await browser.waitFor("document.body.innerText.includes('External mutations remain disabled')");
const refreshBody = await browser.eval('document.body.innerText');
const refreshPass = refreshBody.includes('External mutations remain disabled') && refreshBody.includes('HUMAN go-live approval is not recorded');
results.push({ key: 'refresh-persistence', fixture: 'all-warning-state', positive: refreshPass ? 'PASS' : 'FAIL', negative: 'N/A', browser: refreshPass ? 'PASS' : 'FAIL', evidence: refreshPass ? 'browser refresh retains persisted warning projection' : `refresh body did not contain both mandatory warnings: ${refreshBody.slice(0, 500)}`, screenshot: await browser.screenshot('refresh-persistence') });

// A foreign resource id is rejected under the owner-scoped API; the single
// owner architecture intentionally does not create a second local owner.
let isolationStatus = null;
try { await request('GET', '/products/00000000-0000-4000-8000-000000000001'); } catch (error) { isolationStatus = error.status; }
results.push({ key: 'owner-isolation', fixture: 'foreign-resource-id', positive: isolationStatus === 404 ? 'PASS' : 'FAIL', negative: 'N/A', browser: 'PASS', evidence: `owner-scoped product lookup returned ${isolationStatus}` });

const axeSource = await fs.readFile(path.resolve(process.env.PRSOS_AXE_PATH || 'node_modules/axe-core/axe.min.js'), 'utf8');
await browser.navigate(`${origin}/operations/launch-readiness`);
await browser.eval(axeSource);
const axe = await browser.eval("axe.run(document, { resultTypes: ['violations', 'incomplete'] })");
results.push({ key: 'axe-launch-readiness', fixture: 'warning-projection', positive: axe.violations.length === 0 ? 'PASS' : 'FAIL', negative: axe.incomplete.length === 0 ? 'PASS' : 'FAIL', browser: axe.violations.length === 0 && axe.incomplete.length === 0 ? 'PASS' : 'FAIL', evidence: { violations: axe.violations.map((item) => ({ id: item.id, impact: item.impact, nodes: item.nodes.length })), incomplete: axe.incomplete.map((item) => ({ id: item.id, impact: item.impact, nodes: item.nodes.length })) }, screenshot: await browser.screenshot('axe-launch-readiness') });

const failedRows = results.filter((item) => item.browser === 'FAIL' || item.positive === 'FAIL' || item.negative === 'FAIL');
const report = {
  marker_database: 'prsos09_warning_matrix_20261014',
  origin,
  external_writes: false,
  provider_calls: false,
  warnings: results,
  passed: results.length - failedRows.length,
  failed: failedRows.length,
  fresh_profile: 'NOT AVAILABLE: second CDP endpoint did not expose in this environment; existing dedicated isolated profile used.',
};
await fs.writeFile(path.join(output, 'summary.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
browser.socket.close();
if (failedRows.length) process.exitCode = 1;
