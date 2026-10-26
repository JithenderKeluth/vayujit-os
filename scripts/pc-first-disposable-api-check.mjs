import fs from 'node:fs/promises';

const mode = process.argv[2];
if (!['seed', 'verify'].includes(mode)) throw new Error('Use seed or verify mode.');
const origin = process.env.PC_CERT_ORIGIN;
const email = process.env.PC_CERT_EMAIL;
const password = process.env.PC_CERT_PASSWORD;
const productId = process.env.PC_CERT_PRODUCT_ID;
const mediaId = process.env.PC_CERT_MEDIA_ID;
const financialCostId = process.env.PC_CERT_COST_ID;
const inventoryItemId = process.env.PC_CERT_INVENTORY_ID;
const evidencePath = process.env.PC_CERT_EVIDENCE;
if (!origin || !email || !password || !evidencePath) throw new Error('Disposable PC certification inputs are incomplete.');

const record = { profile: 'pc-first-disposable-certification', mode, checks: [], product_id: productId || null };
const assert = (name, condition, detail = '') => {
  record.checks.push({ name, pass: Boolean(condition), detail });
  if (!condition) throw new Error(`Certification check failed: ${name}${detail ? ` (${detail})` : ''}`);
};
const request = async (path, { method = 'GET', body, cookie } = {}) => {
  const headers = { Origin: origin, Referer: `${origin}/` };
  if (cookie) headers.Cookie = cookie;
  let payload = body;
  if (body && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const response = await fetch(`${origin}/api/v1${path}`, { method, headers, body: payload });
  const text = await response.text();
  let json;
  try { json = text ? JSON.parse(text) : null; } catch { json = text; }
  return { response, json, text };
};
const cookieFrom = (response) => {
  const value = response.headers.get('set-cookie');
  if (!value) throw new Error('Owner setup/login response did not set its session cookie.');
  return value.split(';', 1)[0];
};
const login = async () => {
  const result = await request('/auth/login', { method: 'POST', body: { email, password } });
  assert('owner_login', result.response.status === 200, `HTTP ${result.response.status}`);
  return cookieFrom(result.response);
};

if (mode === 'seed') {
  const setup = await request('/auth/setup-owner', {
    method: 'POST',
    body: {
      full_name: 'PC Profile Disposable Certification Owner',
      email,
      password,
      password_confirmation: password,
    },
  });
  assert('first_owner_onboarding', setup.response.status === 201, `HTTP ${setup.response.status}: ${setup.text.slice(0, 240)}`);
  const cookie = cookieFrom(setup.response);
  const identity = await request('/auth/me', { cookie });
  assert('canonical_owner_identity', identity.response.ok && Boolean(identity.json.id));
  const brand = await request('/brands', {
    method: 'POST',
    cookie,
    body: {
      name: 'DISPOSABLE CERTIFICATION ONLY',
      description: 'Temporary fixture; not real business data.',
      tagline: 'Disposable test workspace',
    },
  });
  assert('canonical_brand_create', brand.response.status === 201, `HTTP ${brand.response.status}`);
  const product = await request('/products', {
    method: 'POST',
    cookie,
    body: {
      brand_id: brand.json.id,
      name: '[DISPOSABLE TEST] PC Persistence Sample Product',
      product_type: 'physical',
      short_description: 'Certification-only stock, cost, price and image record.',
      description: 'This record is synthetic and remains inside a disposable certification database.',
      category: 'Certification fixture',
      tags: ['disposable-certification'],
      sku: `PC-CERT-${Date.now()}`,
      price_amount: '299.00',
      price_currency: 'INR',
      cost_amount: '120.00',
      inventory_tracking_enabled: true,
      inventory_quantity: 7,
      low_stock_threshold: 2,
    },
  });
  assert('canonical_product_create', product.response.status === 201, `HTTP ${product.response.status}`);

  const inventory = await request('/inventory/items', {
    method: 'POST',
    cookie,
    body: {
      product_id: product.json.id,
      internal_sku: product.json.sku,
      location_code: 'pc-cert-location',
      unit: 'each',
      opening_quantity: 7,
      low_stock_threshold: 2,
      idempotency_key: `pc-cert-opening-${product.json.id}`,
    },
  });
  assert('canonical_inventory_opening_balance_create', inventory.response.status === 201, `HTTP ${inventory.response.status}`);

  const cost = await request('/financial/costs', {
    method: 'POST',
    cookie,
    body: {
      product_id: product.json.id,
      sku: product.json.sku,
      cost_key: `pc-cert-acquisition-${product.json.id}`,
      cost_type: 'acquisition',
      amount: '120.00',
      currency: 'INR',
      evidence_status: 'observed',
      source_type: 'seller_entered',
      source_reference: 'Disposable PC certification fixture only; not an actual business expense.',
      provenance: { certification_fixture: true, environment: 'pc_local_disposable' },
    },
  });
  assert('canonical_financial_cost_evidence_create', cost.response.status === 201, `HTTP ${cost.response.status}`);

  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WlH4p8AAAAASUVORK5CYII=', 'base64');
  const form = new FormData();
  form.set('file', new Blob([png], { type: 'image/png' }), 'pc-certification.png');
  const media = await request('/media', { method: 'POST', body: form, cookie });
  assert('canonical_media_upload', media.response.status === 201, `HTTP ${media.response.status}: ${media.text.slice(0, 180)}`);
  const image = await request(`/catalog/products/${product.json.id}/images`, {
    method: 'POST',
    cookie,
    body: { media_id: media.json.id, alt_text: 'Disposable certification sample image', position: 0, is_primary: true },
  });
  assert('canonical_product_media_attachment', image.response.status === 201, `HTTP ${image.response.status}`);
  record.product_id = product.json.id;
  record.owner_id = identity.json.id;
  record.inventory_item_id = inventory.json.id;
  record.media_id = media.json.id;
  record.financial_cost_id = cost.json.id;
  record.product_name = product.json.name;
  record.product_sku = product.json.sku;
  record.fixture_data = 'synthetic disposable only; never copy or promote to the owner database';
  process.env.PC_CERT_PRODUCT_ID = product.json.id;
  process.env.PC_CERT_INVENTORY_ID = inventory.json.id;
  process.env.PC_CERT_MEDIA_ID = media.json.id;
  process.env.PC_CERT_COST_ID = cost.json.id;
  await fs.writeFile(evidencePath, `${JSON.stringify(record, null, 2)}\n`, { encoding: 'utf8', flag: 'w' });
  console.log(JSON.stringify({
    mode,
    checks: record.checks.map(({ name, pass }) => ({ name, pass })),
    fixture: 'synthetic disposable only; never copy or promote to owner data',
  }));
  process.exit(0);
}

const saved = JSON.parse(await fs.readFile(evidencePath, 'utf8'));
const cookie = await login();
const setupStatus = await request('/auth/setup-status');
assert('one_owner_exists_after_restart', setupStatus.response.ok && setupStatus.json.ownerExists === true);
const unauthorized = await request('/products');
assert('unauthenticated_products_are_denied', unauthorized.response.status === 401, `HTTP ${unauthorized.response.status}`);

const productList = await request('/products?page=1&page_size=100', { cookie });
assert('canonical_product_list_persists', productList.response.ok && productList.json.items?.some((item) => item.id === saved.product_id));
const product = await request(`/products/${saved.product_id}`, { cookie });
assert('product_price_cost_stock_persist', product.response.ok
  && product.json.price_currency === 'INR'
  && String(product.json.price_amount) === '299.00'
  && String(product.json.cost_amount) === '120.00'
  && product.json.inventory_quantity === 7);
const inventory = await request(`/inventory?sku=${encodeURIComponent(saved.product_sku || '')}`, { cookie });
assert('canonical_inventory_balance_persists', inventory.response.ok
  && inventory.json.some((item) => item.id === saved.inventory_item_id && item.on_hand_quantity === 7));
const catalog = await request(`/catalog/products/${saved.product_id}`, { cookie });
assert('catalog_context_persists', catalog.response.ok
  && catalog.json.product?.id === saved.product_id
  && catalog.json.images?.some((item) => item.media_id === saved.media_id));
const media = await request(`/media/${saved.media_id}`, { cookie });
assert('media_metadata_persists', media.response.ok && media.json.status === 'ready');
const preview = await fetch(`${origin}/api/v1/media/${saved.media_id}/preview`, {
  headers: { Origin: origin, Cookie: cookie },
});
assert('media_bytes_persist', preview.status === 200 && (await preview.arrayBuffer()).byteLength > 0);
const market = await request('/marketplaces/connectivity/capabilities', { cookie });
assert('marketplace_external_writes_remain_disabled', market.response.ok && market.json.external_writes === false);
record.mode = 'verify';
record.checks.push(...[]);
record.after_restart = true;
record.verified_at = new Date().toISOString();
await fs.writeFile(evidencePath, `${JSON.stringify(record, null, 2)}\n`, { encoding: 'utf8', flag: 'w' });
console.log(JSON.stringify({ mode, checks: record.checks.map(({ name, pass }) => ({ name, pass })) }));
