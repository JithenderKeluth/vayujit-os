import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Product, wp3Owner } from './wp3-fixtures.mjs';

const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
if (!s.synthetic || s.status !== 'READY' || s.schema !== 'ALEMBIC_HEAD') throw Error('QA_REQUIRED');
const w = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (!w.disposable || w.token !== s.token) throw Error('WITNESS_REQUIRED');
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
});
const runs = [],
  result = { token: s.token, status: 'RUNNING', observations: [], ids: {}, stage: 'setup' };
try {
  const run = await start(browser, s, { width: 1440, height: 900 }, 'wp4-before-desktop');
  runs.push(run);
  const p = run.page;
  p.setDefaultTimeout(15000);
  p.on('dialog', (d) => d.accept());
  await p.goto(s.origin + '/setup');
  await p.locator('#full-name').fill('[QA SYNTHETIC] WP4 Seller');
  await p.locator('#email').fill(wp3Owner.email);
  await p.locator('#password').fill(wp3Owner.password);
  await p.locator('#confirmation').fill(wp3Owner.password);
  await p.getByRole('button', { name: 'Create owner', exact: true }).click();
  await p.waitForURL('**/dashboard');
  const { api, op, assessment, brand, goal } = await wp3Product(p, s.origin);
  result.stage = 'conversion';
  await p.goto(s.origin + `/intelligence/product-opportunities/${op.id}?goal_id=${goal.id}`);
  const a = p.locator('app-opportunity-next-actions');
  await a.getByRole('button', { name: 'Select for further investigation', exact: true }).click();
  await a.getByText('Prepare this selected product in Catalog', { exact: true }).click();
  await a.locator('select[name=catalogBrand]').selectOption(brand.id);
  await a.locator('input[name=confirmCatalog]').check();
  const converted = p.waitForResponse(
    (r) =>
      r.request().method() === 'POST' &&
      r.url().endsWith(`/catalog/opportunities/${op.id}/convert`),
  );
  await a.getByRole('button', { name: 'Create or open Catalog draft', exact: true }).click();
  const product = (await (await converted).json()).product;
  result.ids.converted = product.id;
  await a.getByRole('link', { name: 'Open saved Catalog product', exact: true }).click();
  await expect(p.locator('#catalog-product-title')).toBeVisible();
  result.observations.push({
    id: 'SE-BROWSER-018',
    imageActions: await p.locator('[aria-labelledby=images-title]').innerText(),
  });
  await capture(run, 'converted-catalog-before', true);
  result.stage = 'variant error';
  await p.locator('[name=new-variant-key]').fill('blue');
  await p.locator('[name=new-variant-options]').fill('{invalid');
  await p.getByRole('button', { name: 'Add variant', exact: true }).click();
  await expect(p.getByText('Variant options must be valid JSON.', { exact: true })).toBeVisible();
  result.observations.push({
    id: 'SE-BROWSER-010',
    h1Count: await p.locator('h1').count(),
    workspaceRetained: await p.locator('#identity-title').count(),
  });
  await capture(run, 'mutation-error-lost-workspace');
  await axe(run, 'mutation-error');
  result.stage = 'manual product';
  await p.goto(s.origin + '/products/new');
  await p.locator('[formcontrolname=name]').fill('[QA SYNTHETIC] WP4 Manual Box');
  await p.locator('[formcontrolname=sku]').fill('QA-WP4-MANUAL');
  await p.locator('[formcontrolname=inventory_quantity]').fill('12');
  await p.locator('[formcontrolname=inventory_tracking_enabled]').check();
  result.observations.push({
    id: 'SE-BROWSER-019',
    quantityLabel: await p
      .locator('[formcontrolname=inventory_quantity]')
      .evaluate((e) => e.closest('label').innerText),
  });
  await capture(run, 'manual-quantity-entry');
  const created = p.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().endsWith('/api/v1/products'),
  );
  await p.getByRole('button', { name: 'Save product', exact: true }).click();
  const manual = await (await created).json();
  result.ids.manual = manual.id;
  await p.getByRole('link', { name: 'Open catalog workspace', exact: true }).click();
  await expect(p.locator('#identity-title')).toBeVisible();
  result.observations.push({
    id: 'WP4-MANUAL-ECONOMICS',
    text: await p.locator('[aria-labelledby=economics-title]').innerText(),
  });
  await capture(run, 'manual-economics-before');
  await p.goto(s.origin + `/products/${manual.id}/channels`);
  await capture(run, 'manual-product-channels-before');
  await p.goto(s.origin + '/marketplaces/amazon');
  await capture(run, 'amazon-without-account');
  await p.goto(s.origin + '/marketplaces/flipkart');
  await capture(run, 'flipkart-without-account');
  const mobile = await start(browser, s, { width: 390, height: 844 }, 'mobile');
  runs.push(mobile);
  await mobile.context.addCookies(await run.context.cookies());
  await mobile.page.goto(s.origin + `/catalog/${manual.id}`);
  await expect(mobile.page.locator('#identity-title')).toBeVisible();
  await capture(mobile, 'manual-catalog-before', true);
  await axe(mobile, 'manual-catalog-before');
  result.status = 'COMPLETE';
} catch (e) {
  result.status = 'BLOCKED';
  result.error = e.message.slice(0, 900);
  for (const r of runs) await capture(r, 'before-blocker').catch(() => {});
} finally {
  for (const r of runs) await finish(r);
  await browser.close();
  await fs.writeFile(path.join(s.folder, 'wp4-before.json'), JSON.stringify(result, null, 2));
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP4 before complete');
  console.log(JSON.stringify(result));
}
process.exitCode = result.status === 'COMPLETE' ? 0 : 1;
