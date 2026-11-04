import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { start, capture, finish } from './seller-browser-explore.mjs';
import { wp3Product, wp3Owner } from './wp3-fixtures.mjs';
const session = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
if (!session.synthetic || session.status !== 'READY') throw Error('DISPOSABLE_REQUIRED');
const witness = await fetch(session.origin + '/__qa/witness').then((r) => r.json());
if (!witness.disposable || witness.token !== session.token) throw Error('WITNESS_REQUIRED');
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
});
const run = await start(browser, session, { width: 1440, height: 900 }, 'wp3-sourcing-before');
const page = run.page;
page.on('dialog', (d) => d.accept());
const report = { token: session.token, status: 'RUNNING', observations: [] };
try {
  await page.goto(session.origin + '/setup');
  await page.locator('#full-name').fill('[QA SYNTHETIC] WP3');
  await page.locator('#email').fill(wp3Owner.email);
  await page.locator('#password').fill(wp3Owner.password);
  await page.locator('#confirmation').fill(wp3Owner.password);
  await page.getByRole('button', { name: 'Create owner', exact: true }).click();
  await page.waitForURL('**/dashboard');
  const { api, op, brand } = await wp3Product(page, session.origin);
  await page.goto(session.origin + `/intelligence/product-opportunities/${op.id}`);
  await page
    .getByRole('button', { name: 'Select this product for supplier research', exact: true })
    .click();
  await page.getByRole('link', { name: 'Find suppliers', exact: true }).click();
  await page.getByRole('button', { name: 'Find suppliers for this product', exact: true }).click();
  await page.getByRole('button', { name: 'View supplier', exact: true }).click();
  const projected = await api(
    'get',
    `intelligence/suppliers/research-results?opportunity_id=${op.id}`,
  );
  const supplier = projected.suppliers[0];
  await page.goto(session.origin + `/intelligence/product-opportunities/${op.id}`);
  const actions = page.locator('app-opportunity-next-actions');
  await actions.getByText('Prepare this selected product in Catalog', { exact: true }).click();
  await actions.locator('select[name=catalogBrand]').selectOption(brand.id);
  await actions.locator('input[name=confirmCatalog]').check();
  const converted = page.waitForResponse(
    (r) =>
      r.request().method() === 'POST' &&
      r.url().endsWith(`/catalog/opportunities/${op.id}/convert`),
  );
  await actions.getByRole('button', { name: 'Create or open Catalog draft', exact: true }).click();
  const product = (await (await converted).json()).product;
  await page.goto(
    session.origin +
      `/intelligence/sourcing?opportunity_id=${op.id}&name=WP3&category=Home%20%26%20Kitchen&market=IN&supplier_ids=${supplier.id}`,
  );
  const request = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().endsWith('/sourcing/requirements'),
  );
  await page.getByRole('button', { name: 'Confirm requirement', exact: true }).click();
  const response = await request;
  expect(response.status()).toBe(404);
  report.observations.push({
    id: 'WP3-QUOTE-CONTEXT',
    status: 404,
    requestOpportunity: response.request().postDataJSON().opportunity_id,
    canonicalOpportunity: op.id,
    product: product.id,
  });
  await capture(run, 'canonical-opportunity-rejected-as-legacy-id');
  const manual = await api('post', 'products', {
    brand_id: brand.id,
    name: '[QA SYNTHETIC] Manual item',
    slug: 'wp3-manual-item',
    product_type: 'physical',
    status: 'draft',
  });
  await page.goto(session.origin + `/catalog/${manual.id}`);
  await expect(
    page.getByRole('heading', { name: 'Economics readiness', exact: true }),
  ).toBeVisible();
  await capture(run, 'manual-product-no-opportunity-lineage');
  report.observations.push({
    id: 'WP3-MANUAL-ECONOMICS',
    product: manual.id,
    body: await page.locator('section[aria-labelledby=economics-title]').innerText(),
  });
  report.status = 'COMPLETE';
} catch (error) {
  report.status = 'INCOMPLETE';
  report.error = error.message.slice(0, 1500);
  await capture(run, 'before-blocker');
} finally {
  await finish(run);
  await browser.close();
  await fs.writeFile(
    path.join(session.folder, 'wp3-sourcing-before.json'),
    JSON.stringify(report, null, 2),
  );
  await fs.writeFile(path.join(session.folder, 'stop.request'), 'WP3 sourcing before finished');
  console.log(JSON.stringify(report));
}
process.exitCode = report.status === 'COMPLETE' ? 0 : 1;
