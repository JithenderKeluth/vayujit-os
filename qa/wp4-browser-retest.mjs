import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect as playwrightExpect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Product, wp3Owner } from './wp3-fixtures.mjs';
import { wp3UnexpectedSignals } from './wp3-reporting.mjs';
import { measure } from './wp6b-accessibility.mjs';

// Angular lazy routes and persisted reads are asynchronous. Keep assertions
// bounded without sampling an intermediate loading state on a busy Windows host.
const expect = playwrightExpect.configure({ timeout: 20000 });

const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
if (!s.synthetic || s.schema !== 'ALEMBIC_HEAD' || s.status !== 'READY')
  throw Error('APPROVED_QA_SESSION_REQUIRED');
const witness = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (!witness.disposable || witness.token !== s.token) throw Error('QA_WITNESS_REQUIRED');
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
});
const runs = [],
  report = {
    token: s.token,
    status: 'RUNNING',
    checks: [],
    ids: {},
    synthetic: true,
    axe_exposed: [],
  };
async function check(name, fn) {
  try {
    await fn();
    report.checks.push({ name, status: 'PASS' });
  } catch (e) {
    report.checks.push({ name, status: 'FAIL', error: e.message.slice(0, 1200) });
    throw e;
  }
}
async function scan(run, state) {
  const a = await axe(run, state);
  expect(a.violations).toEqual([]);
  for (const rule of a.incomplete.filter((r) => r.id === 'color-contrast'))
    for (const n of rule.nodes) {
      const sel = n.target.length === 1 ? n.target[0] : null;
      if (typeof sel !== 'string') {
        report.axe_exposed.push({ state, target: n.target, status: 'MANUAL' });
        continue;
      }
      const target = run.page.locator(sel);
      if ((await target.count()) !== 1) {
        report.axe_exposed.push({ state, target: n.target, status: 'AMBIGUOUS' });
        continue;
      }
      await target.evaluate((e) => e.scrollIntoView({ block: 'center', inline: 'center' }));
      const result = await target.evaluate(async (e) => {
        const r = await window.axe.run(e, {
          runOnly: { type: 'rule', values: ['color-contrast'] },
        });
        return { violations: r.violations, incomplete: r.incomplete, passes: r.passes.length };
      });
      report.axe_exposed.push({ state, target: n.target, ...result });
      expect(result.violations).toEqual([]);
    }
}
try {
  const d = await start(browser, s, { width: 1440, height: 900 }, 'wp4-after-desktop');
  runs.push(d);
  const p = d.page;
  p.setDefaultTimeout(20000);
  p.on('dialog', (dialog) => dialog.accept());
  await p.goto(s.origin + '/setup');
  await p.locator('#full-name').fill('[QA SYNTHETIC] WP4 Owner');
  await p.locator('#email').fill(wp3Owner.email);
  await p.locator('#password').fill(wp3Owner.password);
  await p.locator('#confirmation').fill(wp3Owner.password);
  await p.getByRole('button', { name: 'Create owner', exact: true }).click();
  await p.waitForURL('**/dashboard');
  const { api, op, brand, goal } = await wp3Product(p, s.origin);
  report.ids.opportunity = op.id;
  report.ids.goal = goal.id;
  let converted, manual, variant, image, firstCost, secondCost, draft;
  await check('HUMAN selected opportunity converts once with exact research lineage', async () => {
    await p.goto(s.origin + `/intelligence/product-opportunities/${op.id}?goal_id=${goal.id}`);
    const actions = p.locator('app-opportunity-next-actions');
    await actions
      .getByRole('button', { name: 'Select for further investigation', exact: true })
      .click();
    await expect(
      actions.getByText('Selected for further investigation.', { exact: true }),
    ).toBeVisible();
    await actions.getByText('Prepare this selected product in Catalog', { exact: true }).click();
    await actions.locator('[name=catalogBrand]').selectOption(brand.id);
    await actions.locator('[name=confirmCatalog]').check();
    const saved = p.waitForResponse(
      (r) =>
        r.request().method() === 'POST' &&
        r.url().endsWith(`/catalog/opportunities/${op.id}/convert`),
    );
    await actions
      .getByRole('button', { name: 'Create or open Catalog draft', exact: true })
      .click();
    converted = (await (await saved).json()).product;
    report.ids.converted = converted.id;
    await actions.getByRole('link', { name: 'Open saved Catalog product', exact: true }).click();
    await expect(p.locator('#identity-title')).toBeVisible();
    const detail = await api('get', `catalog/products/${converted.id}`);
    expect(detail.lineage.opportunity_id).toBe(op.id);
    const replay = await api('post', `catalog/opportunities/${op.id}/convert`, {
      brand_id: brand.id,
      goal_id: goal.id,
      idempotency_key: 'catalog-opportunity-' + op.id,
    });
    expect(replay.product.id).toBe(converted.id);
    await expect(
      p.getByRole('link', { name: 'Return to research and suppliers', exact: true }),
    ).toHaveAttribute('href', `/intelligence/product-opportunities/${op.id}`);
    await expect(
      p.getByRole('link', { name: "Prepare this product's economics", exact: true }),
    ).toHaveAttribute('href', `/intelligence/sourcing-economics?opportunity_id=${op.id}`);
    await capture(d, 'converted-catalog-lineage', true);
  });
  await check(
    'manual product create and edit clarify metadata stock and INR without synthetic research lineage',
    async () => {
      await p.goto(s.origin + '/products/new');
      await expect(
        p.getByLabel('Product master quantity (not stock ledger)', { exact: true }),
      ).toBeVisible();
      await expect(p.locator('[formcontrolname=price_currency]')).toHaveValue('INR');
      await p.locator('[formcontrolname=name]').fill('[QA SYNTHETIC] WP4 Manual Box');
      await p.locator('[formcontrolname=sku]').fill('QA-WP4-MANUAL');
      await p.locator('[formcontrolname=inventory_quantity]').fill('12');
      await p
        .locator('[formcontrolname=description]')
        .fill('Synthetic local product description, not market evidence.');
      await p.locator('[formcontrolname=category]').fill('Home');
      const saved = p.waitForResponse(
        (r) => r.request().method() === 'POST' && r.url().endsWith('/api/v1/products'),
      );
      await p.getByRole('button', { name: 'Save product', exact: true }).click();
      manual = await (await saved).json();
      report.ids.manual = manual.id;
      expect(await api('get', 'inventory')).toEqual([]);
      await p.getByRole('link', { name: 'Edit', exact: true }).click();
      await p.locator('[formcontrolname=price_amount]').fill('250.50');
      await p.getByRole('button', { name: 'Save product', exact: true }).click();
      await p.getByRole('link', { name: 'Open catalog workspace', exact: true }).click();
      await expect(p.locator('#manual-cost-title')).toBeVisible();
      expect((await api('get', `catalog/products/${manual.id}`)).lineage).toBeNull();
      expect((await api('get', `products/${manual.id}`)).price_amount).toBe('250.50');
      await capture(d, 'manual-catalog-unknown-costs');
    },
  );
  await check(
    'recoverable Catalog validation error retains h1, product and entered values',
    async () => {
      await p.locator('[name=new-variant-key]').fill('blue');
      await p.locator('[name=new-variant-options]').fill('{invalid');
      await p.getByRole('button', { name: 'Add variant', exact: true }).click();
      await expect(
        p.getByRole('heading', { name: 'Change not completed', exact: true }),
      ).toBeVisible();
      await expect(p.locator('#catalog-product-title')).toContainText('WP4 Manual Box');
      await expect(p.locator('[name=new-variant-options]')).toHaveValue('{invalid');
      await capture(d, 'inline-mutation-error-context-retained');
      await scan(d, 'inline-catalog-error');
      report.manual_contrast ??= [];
      const measured = await measure(
        d,
        p.locator('[name=new-variant-options]'),
        'historical-inline-error-variant-textarea',
      );
      report.manual_contrast.push(measured);
      expect(measured.status).toBe('MEASURED_PASS');
      await p.locator('[name=new-variant-options]').fill('{"color":"Blue"}');
    },
  );
  await check(
    'variant identity, SKU and price edit persist without duplicate actions',
    async () => {
      await p.locator('[name=new-variant-title]').fill('Blue box');
      await p.locator('[name=new-variant-sku]').fill('QA-WP4-BLUE');
      const saved = p.waitForResponse(
        (r) => r.request().method() === 'POST' && r.url().endsWith('/variants'),
      );
      await p.getByRole('button', { name: 'Add variant', exact: true }).evaluate((b) => {
        b.click();
        b.click();
      });
      variant = await (await saved).json();
      report.ids.variant = variant.id;
      await expect(p.getByLabel('Variant SKU', { exact: true })).toHaveValue('QA-WP4-BLUE');
      await p.getByLabel('Variant price (optional)', { exact: true }).fill('275.50');
      await p.getByLabel('Variant currency', { exact: true }).fill('INR');
      await p.getByRole('button', { name: 'Save variant', exact: true }).click();
      await p.reload();
      await expect(p.getByLabel('Variant price (optional)', { exact: true })).toHaveValue('275.50');
      expect((await api('get', `catalog/products/${manual.id}`)).variants).toHaveLength(1);
      await capture(d, 'variant-sku-and-price-persisted');
    },
  );
  await check(
    'empty media picker to secure local upload returns exact product; attachment requires explicit action',
    async () => {
      await p.getByRole('link', { name: 'Upload a product image', exact: true }).click();
      await p.waitForURL('**/media/upload?catalog_product_id=' + manual.id);
      expect(new URL(p.url()).searchParams.get('catalog_product_id')).toBe(manual.id);
      const data = await p.evaluate(() => {
        const c = document.createElement('canvas');
        c.width = 64;
        c.height = 64;
        const x = c.getContext('2d');
        x.fillStyle = '#ffffff';
        x.fillRect(0, 0, 64, 64);
        x.fillStyle = '#000000';
        x.fillText('QA', 8, 32);
        return c.toDataURL('image/png').split(',')[1];
      });
      await p.locator('input[type=file]').setInputFiles({
        name: 'qa-synthetic-product.png',
        mimeType: 'image/png',
        buffer: Buffer.from(data, 'base64'),
      });
      const uploaded = p.waitForResponse(
        (r) => r.request().method() === 'POST' && r.url().endsWith('/api/v1/media'),
      );
      await p.getByRole('button', { name: 'Upload securely', exact: true }).click();
      image = await (await uploaded).json();
      report.ids.media = image.id;
      await p.waitForURL('**/catalog/' + manual.id + '?media_id=' + image.id + '#images-title');
      await expect(p.locator('.asset-picker select')).toHaveValue(image.id);
      expect(await api('get', `catalog/products/${manual.id}/images`)).toHaveLength(0);
      await p
        .getByLabel('Alt text (recommended)', { exact: true })
        .fill('Synthetic QA box illustration');
      await p.getByRole('button', { name: 'Add image', exact: true }).click();
      await expect(p.getByAltText('Synthetic QA box illustration')).toBeVisible();
      const imageState = await p
        .getByAltText('Synthetic QA box illustration')
        .evaluate((e) => ({ complete: e.complete, width: e.naturalWidth }));
      expect(imageState.width).toBe(64);
      await capture(d, 'private-media-upload-return');
      const anonymous = await browser.newContext();
      const denied = await anonymous.request.get(s.origin + image.preview_url);
      expect(denied.status()).toBe(401);
      await anonymous.close();
    },
  );
  await check(
    'variant opening stock preserves product/SKU, requires review and HUMAN confirmation, no double posting',
    async () => {
      await p.getByRole('link', { name: 'Record stock for Blue box', exact: true }).click();
      await expect(p.locator('#opening-product')).toHaveValue(manual.id);
      await expect(p.locator('#opening-variant')).toHaveValue(variant.id);
      await expect(p.getByLabel('Internal SKU', { exact: true })).toHaveValue('QA-WP4-BLUE');
      await p.getByLabel('Opening quantity', { exact: true }).fill('12');
      await p.getByRole('button', { name: 'Review opening stock', exact: true }).click();
      await expect(
        p.getByRole('button', { name: 'Confirm opening stock', exact: true }),
      ).toBeDisabled();
      expect(await api('get', 'inventory')).toEqual([]);
      await capture(d, 'opening-stock-human-review');
      await p.getByRole('checkbox', { name: /I have counted/ }).check();
      await p.getByRole('button', { name: 'Confirm opening stock', exact: true }).evaluate((b) => {
        b.click();
        b.click();
      });
      await expect(
        p.getByRole('heading', { name: 'Opening stock recorded', exact: true }),
      ).toBeVisible();
      const items = await api('get', 'inventory');
      expect(items).toHaveLength(1);
      expect(items[0]).toMatchObject({
        product_id: manual.id,
        variant_id: variant.id,
        on_hand_quantity: 12,
        available_to_promise: 12,
      });
      const ledger = await api('get', `inventory/${items[0].id}/ledger`);
      expect(ledger).toHaveLength(1);
      expect(ledger[0].actor_type).toBe('HUMAN');
      report.ids.stock = items[0].id;
      await p.reload();
      await expect(
        p.getByRole('heading', { name: 'Opening stock recorded', exact: true }),
      ).toBeVisible();
      await capture(d, 'stock-reload-verified');
    },
  );
  await check(
    'Catalog inventory handoff includes variant ledger without confusing master quantity',
    async () => {
      await p.goto(s.origin + `/catalog/${manual.id}`);
      await p.getByRole('link', { name: 'Review stock ledger', exact: true }).click();
      await p.waitForURL('**/marketplaces/inventory?product_id=' + manual.id);
      expect(new URL(p.url()).searchParams.get('product_id')).toBe(manual.id);
      const row = p
        .getByRole('row')
        .filter({ has: p.getByRole('rowheader', { name: 'QA-WP4-BLUE', exact: true }) });
      await row.getByRole('button', { name: 'View ledger', exact: true }).click();
      await expect(
        p.getByRole('heading', { name: 'Movement ledger for QA-WP4-BLUE', exact: true }),
      ).toBeVisible();
      await capture(d, 'variant-stock-ledger');
    },
  );
  await check(
    'manual cost estimate uses canonical Decimal arithmetic and keeps excluded costs UNKNOWN',
    async () => {
      await p.goto(s.origin + `/catalog/${manual.id}`);
      const form = p.getByRole('form', { name: 'Seller cost assumptions' });
      await form.getByLabel('Planned quantity', { exact: true }).fill('12');
      await form.getByLabel('Assumed acquisition cost per unit', { exact: true }).fill('100.125');
      await form
        .getByLabel('Assumption basis and limitations', { exact: true })
        .fill('Synthetic QA only: hypothetical acquisition cost; not a supplier quote.');
      await form.getByRole('button', { name: 'Save known-cost estimate', exact: true }).click();
      await expect(p.locator('.estimate')).toContainText('1,201.50');
      firstCost = new URL(p.url()).searchParams.get('cost_context_id');
      report.ids.firstCost = firstCost;
      const context = await api('get', `intelligence/sourcing-economics/contexts/${firstCost}`);
      expect(context.context.product_id).toBe(manual.id);
      expect(context.context.product_opportunity_id).toBeNull();
      expect(context.quotes[0]).toMatchObject({ provenance: 'ASSUMED', freshness: 'UNKNOWN' });
      const calcs = await api('get', 'intelligence/sourcing-economics/calculations');
      const c = calcs.items.find((c) => c.context_id === firstCost);
      expect(String(c.per_unit_cost)).toBe('100.125');
      const exact = await api('get', 'intelligence/sourcing-economics/calculations/' + c.id);
      expect(exact.exact_amounts.per_unit_cost).toBe('100.12500000');
      expect(c.status).toBe('PARTIAL');
      expect(c.missing_inputs).toContain('FREIGHT');
      await p.reload();
      await expect(p.locator('.estimate')).toContainText('1,201.50');
      await capture(d, 'manual-cost-assumed-unknown');
    },
  );
  await check(
    'changed assumptions create a new estimate while identical retries and historical reload preserve identity',
    async () => {
      const form = p.getByRole('form', { name: 'Seller cost assumptions' });
      await form.getByLabel('Planned quantity', { exact: true }).fill('12');
      await form.getByLabel('Assumed acquisition cost per unit', { exact: true }).fill('200.5');
      await form
        .getByLabel('Assumption basis and limitations', { exact: true })
        .fill('Synthetic revised acquisition assumption.');
      await form.getByRole('button', { name: 'Save known-cost estimate', exact: true }).click();
      await expect(p.locator('.estimate')).toContainText('2,406.00');
      secondCost = new URL(p.url()).searchParams.get('cost_context_id');
      expect(secondCost).not.toBe(firstCost);
      await form.getByRole('button', { name: 'Save known-cost estimate', exact: true }).click();
      await expect(p.locator('.estimate')).toContainText('2,406.00');
      expect(new URL(p.url()).searchParams.get('cost_context_id')).toBe(secondCost);
      await p.getByLabel('Saved product cost scenario', { exact: true }).selectOption(firstCost);
      await expect(p.locator('.estimate')).toContainText('1,201.50');
      await p.reload();
      await expect(p.locator('.estimate')).toContainText('1,201.50');
      expect(
        (await api('get', 'intelligence/sourcing-economics/contexts')).items.filter(
          (c) => c.product_id === manual.id,
        ),
      ).toHaveLength(2);
    },
  );
  await check(
    'missing/stale economic context never substitutes another product estimate',
    async () => {
      await p.goto(
        s.origin + `/catalog/${manual.id}?cost_context_id=00000000-0000-0000-0000-000000000099`,
      );
      await expect(
        p.getByText(/This saved estimate is unavailable or does not match/),
      ).toBeVisible();
      expect(await p.locator('.estimate').count()).toBe(0);
      await p.goto(s.origin + `/catalog/${manual.id}?cost_context_id=${firstCost}`);
      await expect(p.locator('.estimate')).toContainText('1,201.50');
    },
  );
  await check(
    'incomplete listing blocks review, legitimate correction allows local review only, later edit invalidates it',
    async () => {
      await p.getByRole('button', { name: 'Start Amazon India draft', exact: true }).click();
      const card = p
        .locator('.channel-card')
        .filter({ has: p.getByRole('heading', { name: 'Amazon India', exact: true }) });
      await expect(card).toContainText('Missing:');
      expect(
        await card.getByRole('button', { name: 'Approve as HUMAN', exact: true }).count(),
      ).toBe(0);
      draft = (await api('get', `catalog/products/${manual.id}`)).listing_drafts.find(
        (d) => d.channel === 'amazon_in',
      );
      report.ids.draft = draft.id;
      const denied = await p.request.post(
        s.origin + `/api/v1/catalog/listing-drafts/${draft.id}/review`,
        { data: { version: draft.version, decision: 'approve' } },
      );
      expect(denied.status()).toBe(409);
      await card.getByRole('button', { name: 'Use primary product image', exact: true }).click();
      await card
        .getByLabel('Intended price (estimate, not profit)', { exact: true })
        .fill('250.50');
      await card.getByLabel('Currency (for example INR)', { exact: true }).fill('INR');
      await card
        .getByLabel('Compliance JSON', { exact: true })
        .fill('{"synthetic_local_review":true}');
      await card.getByRole('button', { name: 'Save draft', exact: true }).click();
      await expect(card).toContainText('All local required fields present');
      await card.getByRole('button', { name: 'Approve as HUMAN', exact: true }).click();
      await expect(card).toContainText(
        'HUMAN-reviewed local draft — not published or execution-authorized',
      );
      await card
        .getByLabel('Intended price (estimate, not profit)', { exact: true })
        .fill('275.50');
      await card.getByRole('button', { name: 'Save draft', exact: true }).click();
      await expect(
        card.getByRole('button', { name: 'Approve as HUMAN', exact: true }),
      ).toBeVisible();
      expect(await api('get', 'marketplaces/listings')).toEqual([]);
      await capture(d, 'local-draft-edit-invalidates-review');
    },
  );
  await check(
    'marketplace readiness shows exact product, unconnected accounts, intended price not sales and no publication',
    async () => {
      await p.getByRole('link', { name: 'Marketplace readiness', exact: true }).click();
      await expect(p.locator('h1')).toContainText('WP4 Manual Box');
      for (const channel of ['amazon', 'flipkart']) {
        const row = p
          .getByRole('row')
          .filter({ has: p.getByRole('rowheader', { name: channel, exact: true }) });
        await expect(
          row.getByText('Not connected — no seller account recorded', { exact: true }),
        ).toBeVisible();
      }
      await expect(p.getByRole('rowheader', { name: 'amazon_in', exact: true })).toHaveCount(0);
      await expect(
        p.getByText(/Product-specific sales, fees and profit are UNKNOWN/),
      ).toBeVisible();
      await expect(p.getByRole('cell', { name: '₹275.50', exact: true })).toBeVisible();
      await expect(
        p.getByRole('link', { name: 'Prepare local draft', exact: true }).first(),
      ).toHaveAttribute('href', `/catalog/${manual.id}#drafts-title`);
      await capture(d, 'marketplace-not-connected-no-false-sales', true);
      await scan(d, 'marketplace-preparation-desktop');
      await p.reload();
      await expect(p.locator('h1')).toContainText('WP4 Manual Box');
    },
  );
  await check(
    'converted product also supports its own variant, image selection and local Flipkart draft without manual-product substitution',
    async () => {
      await p.goto(s.origin + `/catalog/${converted.id}`);
      await expect(p.locator('#catalog-product-title')).toContainText('WP3 Bottle');
      await p.locator('[name=new-variant-key]').fill('single');
      await p.locator('[name=new-variant-title]').fill('Single bottle');
      await p.locator('[name=new-variant-sku]').fill('QA-WP4-BOTTLE');
      await p.getByRole('button', { name: 'Add variant', exact: true }).click();
      await expect(
        p.getByRole('link', { name: 'Record stock for Single bottle', exact: true }),
      ).toBeVisible();
      await p.locator('.asset-picker select').selectOption(image.id);
      await p
        .getByLabel('Alt text (recommended)', { exact: true })
        .fill('Synthetic placeholder only, not researched product evidence');
      await p.getByRole('button', { name: 'Add image', exact: true }).click();
      await expect(
        p.getByAltText('Synthetic placeholder only, not researched product evidence'),
      ).toBeVisible();
      await p.getByRole('button', { name: 'Start Flipkart draft', exact: true }).click();
      await expect(
        p
          .locator('.channel-card')
          .filter({ has: p.getByRole('heading', { name: 'Flipkart', exact: true }) }),
      ).toContainText('Missing:');
      expect((await api('get', `catalog/products/${converted.id}`)).lineage.opportunity_id).toBe(
        op.id,
      );
      await p.getByRole('link', { name: 'Record stock for Single bottle', exact: true }).click();
      await expect(p.locator('#opening-product')).toHaveValue(converted.id);
      await p.getByLabel('Opening quantity', { exact: true }).fill('0');
      await p.getByRole('button', { name: 'Review opening stock', exact: true }).click();
      await expect(
        p.getByRole('button', { name: 'Confirm opening stock', exact: true }),
      ).toBeDisabled();
      await p.getByRole('checkbox', { name: /I have counted/ }).check();
      await p.getByRole('button', { name: 'Confirm opening stock', exact: true }).click();
      await expect(
        p.getByRole('heading', { name: 'Opening stock recorded', exact: true }),
      ).toBeVisible();
      const zero = (await api('get', 'inventory')).find((item) => item.product_id === converted.id);
      expect(zero.on_hand_quantity).toBe(0);
      expect(zero.available_to_promise).toBe(0);
      await p.getByRole('link', { name: 'Return to inventory', exact: true }).click();
      await expect(p.getByRole('rowheader', { name: 'QA-WP4-BOTTLE', exact: true })).toBeVisible();
      await capture(d, 'converted-zero-stock-not-inferred');
    },
  );
  await check(
    'backend read failure recovery keeps exact product and does not certify unavailable state',
    async () => {
      const endpoint = `/api/v1/catalog/products/${manual.id}`;
      d.signals.expected_http_errors = [{ path: endpoint, status: 503 }];
      await p.route('**' + endpoint, (r) =>
        r.fulfill({
          status: 503,
          contentType: 'application/json',
          body: '{"detail":"Synthetic QA read outage"}',
        }),
      );
      await p.goto(s.origin + `/catalog/${manual.id}`);
      await expect(
        p.getByRole('heading', { name: 'Catalog context is unavailable', exact: true }),
      ).toBeVisible();
      await expect(p.locator('h1')).toContainText('Catalog product');
      await p.unroute('**' + endpoint);
      await p.getByRole('button', { name: 'Retry', exact: true }).click();
      await expect(p.locator('#catalog-product-title')).toContainText('WP4 Manual Box');
      await scan(d, 'catalog-recovered');
    },
  );
  const m = await start(browser, s, { width: 390, height: 844 }, 'mobile');
  runs.push(m);
  await m.context.addCookies(await d.context.cookies());
  m.page.setDefaultTimeout(20000);
  await check(
    'mobile Catalog deep link, estimates, variants and image preview retain exact product and fit viewport',
    async () => {
      await m.page.goto(s.origin + `/catalog/${manual.id}?cost_context_id=${firstCost}`);
      await expect(m.page.locator('.estimate')).toContainText('1,201.50');
      await expect(m.page.getByAltText('Synthetic QA box illustration')).toBeVisible();
      await expect(m.page.getByLabel('Variant SKU', { exact: true })).toHaveValue('QA-WP4-BLUE');
      expect(await m.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      await capture(m, 'mobile-catalog-costs-media-and-variant', true);
      await scan(m, 'mobile-catalog');
    },
  );
  await check(
    'mobile keyboard workflow reaches stock review with explicit HUMAN gate, cancel has no movement',
    async () => {
      await m.page.getByRole('link', { name: 'Record counted opening stock', exact: true }).focus();
      await m.page.keyboard.press('Enter');
      await expect(m.page.locator('#opening-product')).toHaveValue(manual.id);
      await m.page.getByLabel('Opening quantity', { exact: true }).fill('0');
      await m.page.getByRole('button', { name: 'Review opening stock', exact: true }).focus();
      await m.page.keyboard.press('Enter');
      await expect(
        m.page.getByRole('button', { name: 'Confirm opening stock', exact: true }),
      ).toBeDisabled();
      await scan(m, 'mobile-opening-review');
      await m.page.getByRole('button', { name: 'Edit review', exact: true }).click();
      await expect(m.page.locator('#opening-product')).toHaveValue(manual.id);
      expect((await api('get', 'inventory')).length).toBe(2);
      await capture(m, 'mobile-stock-review-cancelled');
    },
  );
  await check(
    'mobile marketplace preparation and browser history/reload preserve product and current persisted draft',
    async () => {
      await m.page.goto(s.origin + `/catalog/${manual.id}`);
      await m.page.getByRole('link', { name: 'Marketplace readiness', exact: true }).click();
      await expect(m.page.locator('h1')).toContainText('WP4 Manual Box');
      await scan(m, 'mobile-marketplace-preparation');
      expect(await m.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      await m.page.goBack();
      await expect(m.page.locator('#catalog-product-title')).toContainText('WP4 Manual Box');
      await m.page.goForward();
      await expect(m.page.locator('h1')).toContainText('WP4 Manual Box');
      await m.page.reload();
      await expect(
        m.page.getByRole('link', { name: 'Prepare local draft', exact: true }).first(),
      ).toHaveAttribute('href', `/catalog/${manual.id}#drafts-title`);
      await capture(m, 'mobile-marketplace-history', true);
    },
  );
  await check(
    'Historical Catalog inline validation-error textarea is exposed and measured on mobile without a write',
    async () => {
      const mobile = runs.find((r) => r.label === 'mobile');
      await mobile.page.goto(s.origin + `/catalog/${manual.id}`);
      await mobile.page.locator('[name=new-variant-key]').fill('uncommitted-error-check');
      await mobile.page.locator('[name=new-variant-options]').fill('{invalid');
      await mobile.page.getByRole('button', { name: 'Add variant', exact: true }).click();
      await expect(
        mobile.page.getByRole('heading', { name: 'Change not completed', exact: true }),
      ).toBeVisible();
      await expect(mobile.page.locator('#catalog-product-title')).toContainText('WP4 Manual Box');
      await scan(mobile, 'historical-inline-error-mobile');
      const measured = await measure(
        mobile,
        mobile.page.locator('[name=new-variant-options]'),
        'historical-inline-error-mobile-textarea',
      );
      report.manual_contrast.push(measured);
      expect(measured.status).toBe('MEASURED_PASS');
      expect((await api('get', `catalog/products/${manual.id}`)).variants).toHaveLength(1);
    },
  );
  await check(
    'unexpected Angular console, provider requests and server failures remain zero',
    async () => {
      report.signals = runs.map((r) => ({
        label: r.label,
        unexpected: wp3UnexpectedSignals(r.signals),
      }));
      for (const row of report.signals)
        for (const values of Object.values(row.unexpected)) expect(values).toHaveLength(0);
    },
  );
  report.status = 'COMPLETE';
} catch (e) {
  report.status = 'BLOCKED';
  report.error = e.message.slice(0, 1500);
  for (const r of runs) await capture(r, 'retest-blocker').catch(() => {});
} finally {
  for (const r of runs) await finish(r);
  await browser.close();
  await fs.writeFile(path.join(s.folder, 'wp4-retest.json'), JSON.stringify(report, null, 2));
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP4 retest complete');
  console.log(
    JSON.stringify({
      status: report.status,
      token: s.token,
      passed: report.checks.filter((c) => c.status === 'PASS').length,
      failed: report.checks.filter((c) => c.status === 'FAIL').length,
      error: report.error,
    }),
  );
}
process.exitCode = report.status === 'COMPLETE' ? 0 : 1;
