import { test as base, expect, scanAxe, attach, inspectContrastNode } from '../explore.mjs';
import { allowRequest } from '../safety.mjs';
import { snapshotSurface } from '../phase4-surface.mjs';

const email = 'qa-phase3-owner@example.com';
const password = 'SyntheticPhase3Only123!';
const test = base.extend({
  stockSafety: [
    async ({ context, baseURL }, use) => {
      await context.route('**/*', (r) =>
        allowRequest(r.request().url(), r.request().method(), baseURL, '4B')
          ? r.fallback()
          : r.abort(),
      );
      await use();
    },
    { auto: true },
  ],
});
async function authenticate(page) {
  const status = await (await page.request.get('/api/v1/auth/setup-status')).json();
  if (!status.ownerExists) {
    const r = await page.request.post('/api/v1/auth/setup-owner', {
      data: {
        full_name: '[QA SYNTHETIC] Stock owner',
        email,
        password,
        password_confirmation: password,
      },
    });
    expect(r.status()).toBe(201);
  } else
    expect(
      (await page.request.post('/api/v1/auth/login', { data: { email, password } })).status(),
    ).toBe(200);
}
async function product(page, key, variant = false) {
  const b = await page.request.post('/api/v1/brands', {
    data: { name: `[QA SYNTHETIC] Stock ${key}`, slug: `qa4b-${key}` },
  });
  expect(b.status()).toBe(201);
  const p = await page.request.post('/api/v1/products', {
    data: {
      brand_id: (await b.json()).id,
      name: `[QA SYNTHETIC] Stock ${key}`,
      product_type: 'physical',
      sku: `QA4B-${key}`,
    },
  });
  expect(p.status()).toBe(201);
  const row = await p.json();
  if (variant) {
    const v = await page.request.post(`/api/v1/catalog/products/${row.id}/variants`, {
      data: { variant_key: 'blue', title: 'Blue counted units', sku: `QA4B-${key}-BLUE` },
    });
    expect(v.status()).toBe(201);
    row.variant = await v.json();
  }
  return row;
}
async function start(page, p) {
  await page.goto('/marketplaces/inventory/opening');
  await page.getByLabel('Catalog product', { exact: true }).selectOption(p.id);
  await expect(page.getByLabel('Internal SKU', { exact: true })).toHaveValue(p.sku);
}
async function review(page, quantity = '12') {
  await page.getByLabel('Opening quantity', { exact: true }).fill(quantity);
  await page.getByRole('button', { name: 'Review opening stock', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Review opening stock', exact: true }),
  ).toBeVisible();
}
async function confirm(page) {
  await page.getByRole('checkbox', { name: /I have counted/ }).check();
  await page.getByRole('button', { name: 'Confirm opening stock', exact: true }).click();
}
async function axe(page, info, state) {
  await attach(
    info,
    'stock-surface-' + state,
    await snapshotSurface(page, new URL(page.url()).pathname, state),
  );
  await info.attach('stock-screen-' + state, {
    contentType: 'image/png',
    body: await page.screenshot({ fullPage: true }),
  });
  expect((await scanAxe(page, info, state)).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
}
async function exposedContrast(page, info, selector, name) {
  const result = await inspectContrastNode(page, info, page.locator(selector), name);
  expect(result.violations).toEqual([]);
  expect(result.incomplete).toEqual([]);
  expect(result.passes).toContain('color-contrast');
  expect(result.text_horizontally_in_view).toBe(true);
}

test('QA-P4B-01 empty inventory to persisted opening, ledger and refresh', async ({
  page,
}, info) => {
  await authenticate(page);
  await page.goto('/marketplaces/inventory');
  await expect(
    page.getByRole('heading', { name: 'No canonical inventory yet', exact: true }),
  ).toBeVisible();
  await axe(page, info, 'genuine-empty');
  await page.getByRole('link', { name: 'Add opening stock', exact: true }).click();
  await expect(
    page.getByText('No eligible products match this search.', { exact: false }),
  ).toBeVisible();
  await axe(page, info, 'no-products');
  const p = await product(page, 'one');
  await start(page, p);
  for (const id of [
    'product-error',
    'sku-error',
    'location-error',
    'unit-error',
    'quantity-error',
    'threshold-error',
  ])
    await expect(page.locator('#' + id)).not.toBeVisible();
  await axe(page, info, 'entry');
  await review(page);
  await expect(
    page.getByRole('button', { name: 'Confirm opening stock', exact: true }),
  ).toBeDisabled();
  expect(await (await page.request.get('/api/v1/inventory')).json()).toEqual([]);
  await axe(page, info, 'review');
  await confirm(page);
  await expect(
    page.getByRole('heading', { name: 'Opening stock recorded', exact: true }),
  ).toBeVisible();
  await axe(page, info, 'saved');
  const rows = await (await page.request.get('/api/v1/inventory')).json();
  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({
    product_id: p.id,
    on_hand_quantity: 12,
    reserved_quantity: 0,
    damaged_quantity: 0,
    available_to_promise: 12,
    version: 1,
  });
  const movements = await (await page.request.get(`/api/v1/inventory/${rows[0].id}/ledger`)).json();
  expect(movements).toHaveLength(1);
  expect(movements[0]).toMatchObject({
    movement_type: 'opening_balance',
    actor_type: 'HUMAN',
    reason: 'Opening balance',
    quantity: 12,
  });
  await attach(info, 'persisted-stock-proof', { item: rows[0], movements });
  await page.reload();
  await expect(
    page.getByRole('heading', { name: 'Opening stock recorded', exact: true }),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Return to inventory', exact: true }).click();
  const row = page
    .getByRole('row')
    .filter({ has: page.getByRole('rowheader', { name: p.sku, exact: true }) });
  await row.getByRole('button', { name: 'View ledger', exact: true }).click();
  await expect(page.getByRole('heading', { name: `Movement ledger for ${p.sku}` })).toBeVisible();
  await axe(page, info, 'ledger');
  await exposedContrast(
    page,
    info,
    '.marketplace-page > .marketplace-table > table > caption',
    'stock-ledger-caption',
  );
  await exposedContrast(
    page,
    info,
    '.marketplace-page > .marketplace-table > table > thead > tr > th:nth-child(5)',
    'stock-damaged-header',
  );
});

test('QA-P4B-02 invalid inputs, zero balance, cancel and keyboard review', async ({
  page,
}, info) => {
  await authenticate(page);
  const p = await product(page, 'two');
  await start(page, p);
  for (const value of ['', '-1', '1.5', '2000000001']) {
    await page.getByLabel('Opening quantity', { exact: true }).fill(value);
    await page.getByRole('button', { name: 'Review opening stock', exact: true }).click();
    await expect(page.getByLabel('Opening quantity', { exact: true })).toHaveAttribute(
      'aria-invalid',
      'true',
    );
    await expect(page.getByLabel('Opening quantity', { exact: true })).toBeFocused();
  }
  await axe(page, info, 'invalid');
  await exposedContrast(page, info, '#quantity-help', 'stock-quantity-help');
  await review(page, '0');
  await expect(
    page.getByRole('heading', { name: 'Review opening stock', exact: true }),
  ).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('checkbox', { name: /I have counted/ })).toBeFocused();
  expect(
    await page
      .getByRole('checkbox', { name: /I have counted/ })
      .evaluate((e) => getComputedStyle(e).outlineStyle),
  ).not.toBe('none');
  await page.keyboard.press('Space');
  await expect(
    page.getByRole('button', { name: 'Confirm opening stock', exact: true }),
  ).toBeEnabled();
  await page.keyboard.press('Tab');
  await expect(
    page.getByRole('button', { name: 'Confirm opening stock', exact: true }),
  ).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByRole('checkbox', { name: /I have counted/ })).toBeFocused();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Edit review', exact: true }).click();
  await expect(page.getByLabel('Opening quantity', { exact: true })).toHaveValue('0');
  await page.getByRole('link', { name: 'Cancel', exact: true }).click();
  expect(
    (await (await page.request.get('/api/v1/inventory')).json()).filter(
      (i) => i.product_id === p.id,
    ),
  ).toEqual([]);
  await start(page, p);
  await review(page, '0');
  await page.getByRole('checkbox', { name: /I have counted/ }).focus();
  await page.keyboard.press('Space');
  await expect(
    page.getByRole('button', { name: 'Confirm opening stock', exact: true }),
  ).toBeEnabled();
  await page.getByRole('button', { name: 'Confirm opening stock', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(
    page.getByRole('heading', { name: 'Opening stock recorded', exact: true }),
  ).toBeVisible();
});

test('QA-P4B-03 variant custom SKU review reload and explicit reapproval', async ({
  page,
}, info) => {
  await authenticate(page);
  const p = await product(page, 'three', true);
  await start(page, p);
  await page.getByLabel('Product variant', { exact: true }).selectOption(p.variant.id);
  await page.getByLabel('Internal SKU', { exact: true }).fill('QA4B-CUSTOM');
  await page.getByLabel('Location code', { exact: true }).fill('counted-shelf');
  await review(page, '7');
  await page.reload();
  await expect(
    page.getByRole('heading', { name: 'Review opening stock', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('QA4B-CUSTOM', { exact: true })).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Confirm opening stock', exact: true }),
  ).toBeDisabled();
  await axe(page, info, 'restored-review');
  await confirm(page);
  await expect(
    page.getByRole('heading', { name: 'Opening stock recorded', exact: true }),
  ).toBeVisible();
  const row = (await (await page.request.get('/api/v1/inventory')).json()).find(
    (i) => i.product_id === p.id,
  );
  expect(row).toMatchObject({
    variant_id: p.variant.id,
    internal_sku: 'QA4B-CUSTOM',
    location_code: 'counted-shelf',
    on_hand_quantity: 7,
  });
});

test('QA-P4B-04 response lost after commit replays without duplicate stock', async ({
  page,
  exploration,
}, info) => {
  await authenticate(page);
  const p = await product(page, 'four');
  await start(page, p);
  await review(page);
  let first = true;
  const keys = [];
  await page.route('**/api/v1/inventory/items', async (route) => {
    keys.push(route.request().postDataJSON().idempotency_key);
    if (first) {
      first = false;
      const response = await route.fetch();
      expect(response.status()).toBe(201);
      await route.abort('failed');
    } else await route.continue();
  });
  await confirm(page);
  await expect(
    page.getByText('Save or verification was interrupted.', { exact: false }),
  ).toBeVisible();
  await axe(page, info, 'uncertain-save');
  await page.reload();
  await expect(
    page.getByRole('button', { name: 'Retry identical opening request', exact: true }),
  ).toBeDisabled();
  await page.getByRole('checkbox', { name: /I have counted/ }).check();
  await page.getByRole('button', { name: 'Retry identical opening request', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Opening stock recorded', exact: true }),
  ).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  const row = (await (await page.request.get('/api/v1/inventory')).json()).find(
    (i) => i.product_id === p.id,
  );
  expect(await (await page.request.get(`/api/v1/inventory/${row.id}/ledger`)).json()).toHaveLength(
    1,
  );
  await attach(info, 'lost-response-replay', {
    equal_request_keys: keys[0] === keys[1],
    failed_requests: exploration.failed_requests,
  });
});

test('QA-P4B-05 stock appears after review conflict preserves balance', async ({ page }, info) => {
  await authenticate(page);
  const p = await product(page, 'five');
  await start(page, p);
  await review(page);
  const r = await page.request.post('/api/v1/inventory/items', {
    data: {
      product_id: p.id,
      internal_sku: p.sku,
      opening_quantity: 4,
      idempotency_key: 'qa4b-competing',
    },
  });
  expect(r.status()).toBe(201);
  await confirm(page);
  await expect(page.getByRole('alert')).toContainText('already exists');
  await expect(
    page.getByRole('heading', { name: 'Opening stock recorded', exact: true }),
  ).toHaveCount(0);
  await axe(page, info, 'conflict');
  const rows = (await (await page.request.get('/api/v1/inventory')).json()).filter(
    (i) => i.product_id === p.id,
  );
  expect(rows).toHaveLength(1);
  expect(rows[0].on_hand_quantity).toBe(4);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Edit review', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Edit review', exact: true }).click();
  await page.getByRole('button', { name: 'Review opening stock', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('already exist');
});

test('QA-P4B-06 unavailable product and API recovery remain fail closed', async ({
  page,
  exploration,
}, info) => {
  await authenticate(page);
  const p = await product(page, 'six');
  await start(page, p);
  await review(page);
  expect((await page.request.post(`/api/v1/products/${p.id}/archive`)).status()).toBe(200);
  await confirm(page);
  await expect(page.getByRole('alert')).toContainText('non-archived');
  expect(
    (await (await page.request.get('/api/v1/inventory')).json()).filter(
      (i) => i.product_id === p.id,
    ),
  ).toEqual([]);
  await page.getByRole('button', { name: 'Edit review', exact: true }).click();
  await page.goto('/marketplaces/inventory/opening');
  exploration.expected_http_errors.push({ path: '/api/v1/products', status: 503 });
  await page.route('**/api/v1/products?*', (r) =>
    r.fulfill({ status: 503, contentType: 'application/json', body: '{}' }),
  );
  await page.getByRole('button', { name: 'Find products', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Product search could not be loaded');
  await axe(page, info, 'search-error');
  await page.unroute('**/api/v1/products?*');
  await page.getByRole('button', { name: 'Find products', exact: true }).click();
  await expect(
    page.getByLabel('Catalog product', { exact: true }).locator('option'),
  ).not.toHaveCount(1);
});

test('QA-P4B-07 filtered navigation and saved deep link history', async ({ page }, info) => {
  await authenticate(page);
  const p = await product(page, 'seven');
  await page.goto('/marketplaces/inventory?sku=NO-SUCH-STOCK&low_stock=true');
  await expect(
    page.getByRole('heading', { name: 'No matching inventory', exact: true }),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Add opening stock', exact: true }).click();
  await page.getByLabel('Catalog product', { exact: true }).selectOption(p.id);
  await expect(page.getByLabel('Internal SKU', { exact: true })).toHaveValue(p.sku);
  await review(page, '3');
  await confirm(page);
  await expect(
    page.getByRole('heading', { name: 'Opening stock recorded', exact: true }),
  ).toBeVisible();
  const saved = page.url();
  await page.getByRole('link', { name: 'Return to inventory', exact: true }).click();
  await expect(page.getByLabel('SKU search', { exact: true })).toHaveValue('NO-SUCH-STOCK');
  await expect(page.getByLabel('Low stock only', { exact: true })).toBeChecked();
  await page.goBack();
  await expect(page).toHaveURL(saved);
  await expect(
    page.getByRole('heading', { name: 'Opening stock recorded', exact: true }),
  ).toBeVisible();
  await page.goForward();
  await expect(page).toHaveURL(/\/marketplaces\/inventory\?/);
  await page.goto(saved);
  await page.reload();
  await axe(page, info, 'saved-deep-link');
});

test('QA-P4B-08 auth and unknown installation identifiers do not leak stock', async ({
  page,
}, info) => {
  await authenticate(page);
  await page.goto('/marketplaces/inventory/opening?item_id=00000000-0000-0000-0000-000000000001');
  await expect(page.getByRole('alert')).toContainText('could not be loaded');
  await expect(
    page.getByRole('heading', { name: 'Opening stock recorded', exact: true }),
  ).toHaveCount(0);
  await axe(page, info, 'unknown-item');
  expect((await page.request.post('/api/v1/auth/logout')).status()).toBe(204);
  await page.goto('/marketplaces/inventory/opening');
  await expect(page).toHaveURL(/\/login/);
  expect(
    (
      await page.request.post('/api/v1/inventory/items', {
        data: {
          product_id: '00000000-0000-0000-0000-000000000001',
          internal_sku: 'UNAUTHORIZED',
          opening_quantity: 2,
          idempotency_key: 'qa4b-no-auth',
        },
      })
    ).status(),
  ).toBe(401);
});
