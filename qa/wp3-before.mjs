import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { start, capture, finish } from './seller-browser-explore.mjs';
import { wp3Product, wp3Economics, wp3Owner } from './wp3-fixtures.mjs';

const session = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
if (!session.synthetic || session.schema !== 'ALEMBIC_HEAD' || session.status !== 'READY')
  throw Error('WP3_DISPOSABLE_SESSION_REQUIRED');
const witness = await fetch(session.origin + '/__qa/witness').then((r) => r.json());
if (!witness.disposable || witness.token !== session.token) throw Error('WP3_WITNESS_REQUIRED');
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
});
const runs = [];
const result = {
  token: session.token,
  stage: 'setup',
  observations: [],
  status: 'RUNNING',
  synthetic: true,
};
try {
  const desktop = await start(browser, session, { width: 1440, height: 900 }, 'wp3-before-desktop');
  runs.push(desktop);
  const page = desktop.page;
  page.setDefaultTimeout(15000);
  page.on('dialog', (dialog) => dialog.accept());
  await page.goto(session.origin + '/setup');
  await page.locator('#full-name').fill('[QA SYNTHETIC] WP3 Seller');
  await page.locator('#email').fill(wp3Owner.email);
  await page.locator('#password').fill(wp3Owner.password);
  await page.locator('#confirmation').fill(wp3Owner.password);
  await page.getByRole('button', { name: 'Create owner', exact: true }).click();
  await page.waitForURL('**/dashboard');
  const { api, op, assessment, goal, brand } = await wp3Product(page, session.origin);
  result.ids = { opportunity: op.id, assessment: assessment.id, goal: goal.id };
  result.stage = 'primary supplier navigation';
  await page.getByRole('link', { name: 'Suppliers', exact: true }).first().click();
  await page.waitForURL('**/intelligence/sourcing');
  await expect(
    page.getByRole('heading', { name: 'Make a sourcing decision', exact: true }),
  ).toBeVisible();
  result.observations.push({
    id: 'SE-BROWSER-013',
    route: new URL(page.url()).pathname,
    heading: await page.locator('h1').innerText(),
  });
  await capture(desktop, 'primary-suppliers');
  result.stage = 'selection and supplier discovery';
  await page.goto(
    session.origin + `/intelligence/product-opportunities/${op.id}?goal_id=${goal.id}`,
  );
  await page
    .getByRole('button', { name: 'Select this product for supplier research', exact: true })
    .click();
  await page.getByRole('link', { name: 'Find suppliers', exact: true }).click();
  await page.getByRole('button', { name: 'Find suppliers for this product', exact: true }).click();
  await page.getByRole('button', { name: 'View supplier', exact: true }).click();
  const projection = await api(
    'get',
    `intelligence/suppliers/research-results?opportunity_id=${op.id}`,
  );
  result.ids.supplier = projection.suppliers[0].id;
  await capture(desktop, 'supplier-detail');
  await page.getByRole('link', { name: 'Shortlist this supplier', exact: true }).click();
  await page.getByRole('button', { name: 'Evaluate current shortlist', exact: true }).click();
  await page.getByRole('button', { name: 'Shortlist for verification', exact: true }).click();
  await expect(
    page.getByRole('link', { name: "Assess this supplier's evidence", exact: true }),
  ).toBeVisible();
  result.observations.push({
    id: 'SE-BROWSER-007',
    beforeReload: await page.locator('.metrics').innerText(),
  });
  await capture(desktop, 'shortlist-before-reload');
  const metricsWait = page.waitForResponse((response) =>
    response.url().endsWith('/supplier-shortlisting/operations'),
  );
  await page.reload();
  const metricResponse = await metricsWait;
  result.observations.at(-1).canonicalOperations = await metricResponse.json();
  await expect(page.locator('app-loading-state')).toHaveCount(0);
  result.observations.at(-1).afterReload = await page.locator('.metrics').innerText();
  result.stage = 'economic scenario';
  const economics = await wp3Economics(api, op, assessment);
  result.economics = economics;
  await page.goto(
    session.origin +
      `/intelligence/sourcing-economics?opportunity_id=${op.id}&supplier_id=${result.ids.supplier}`,
  );
  await expect(
    page.getByRole('button', { name: 'Load decision brief', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Load decision brief', exact: true }).click();
  result.observations.push({
    id: 'WP3-SCOPED-BRIEF-PREREQUISITE',
    absentBrief: (await page.locator('.unit-economics-summary').count()) === 0,
    body: await page.locator('section[aria-labelledby=scope-title]').innerText(),
  });
  await capture(desktop, 'supplier-context-prerequisite');
  // The existing supplier-scoped context must not be replaced by another cost
  // basis. Separately inspect the explicitly product-level modeled assessment.
  await page.goto(session.origin + `/intelligence/sourcing-economics?opportunity_id=${op.id}`);
  await expect(page.locator('.unit-economics-summary')).toBeVisible();
  await page.locator('.unit-economics-summary').scrollIntoViewIfNeeded();
  const economicsBody = await page.locator('main').innerText();
  result.observations.push({
    id: 'SE-BROWSER-015',
    rawDictionaryWarning:
      economicsBody.includes("'source_refs':") || economicsBody.includes("'required':"),
    height: await page.evaluate(() => document.documentElement.scrollHeight),
  });
  result.observations.push({
    id: 'SE-BROWSER-016',
    body: await page.locator('.unit-economics-summary').innerText(),
  });
  await capture(desktop, 'raw-financial-presentation');
  result.stage = 'canonical catalog conversion';
  await page.goto(
    session.origin + `/intelligence/product-opportunities/${op.id}?goal_id=${goal.id}`,
  );
  const actions = page.locator('app-opportunity-next-actions');
  await actions.getByText('Prepare this selected product in Catalog', { exact: true }).click();
  await actions.locator('select[name=catalogBrand]').selectOption(brand.id);
  await actions.locator('input[name=confirmCatalog]').check();
  const conversion = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().endsWith(`/catalog/opportunities/${op.id}/convert`),
  );
  await actions.getByRole('button', { name: 'Create or open Catalog draft', exact: true }).click();
  const product = (await (await conversion).json()).product;
  result.ids.product = product.id;
  await actions.getByRole('link', { name: 'Open saved Catalog product', exact: true }).click();
  const catalogEconomics = await api('get', `catalog/products/${product.id}/economics`);
  await expect(
    page.getByRole('heading', { name: 'Economics readiness', exact: true }),
  ).toBeVisible();
  result.observations.push({
    id: 'SE-BROWSER-006',
    projectionCurrency: catalogEconomics.projection?.base_currency,
    body: await page.locator('section[aria-labelledby=economics-title]').innerText(),
  });
  await capture(desktop, 'catalog-currency');
  const mobile = await start(browser, session, { width: 390, height: 844 }, 'mobile');
  runs.push(mobile);
  await mobile.page.goto(session.origin + '/login');
  await mobile.page.locator('#email').fill(wp3Owner.email);
  await mobile.page.locator('#password').fill(wp3Owner.password);
  await mobile.page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await mobile.page.waitForURL('**/dashboard');
  await mobile.page.goto(
    session.origin + `/intelligence/sourcing-economics?opportunity_id=${op.id}`,
  );
  await expect(mobile.page.locator('.unit-economics-summary')).toBeVisible();
  result.observations.push({
    id: 'SE-BROWSER-015',
    viewport: 390,
    height: await mobile.page.evaluate(() => document.documentElement.scrollHeight),
  });
  await capture(mobile, 'mobile-economics-before', true);
  result.status = 'COMPLETE';
} catch (error) {
  result.status = 'BLOCKED';
  result.error = error.message.slice(0, 1200);
  for (const run of runs) await capture(run, 'before-blocker').catch(() => {});
} finally {
  for (const run of runs) await finish(run);
  await browser.close();
  await fs.writeFile(path.join(session.folder, 'wp3-before.json'), JSON.stringify(result, null, 2));
  await fs.writeFile(path.join(session.folder, 'stop.request'), 'WP3 before exploration complete');
  console.log(
    JSON.stringify({
      status: result.status,
      stage: result.stage,
      token: result.token,
      observations: result.observations.length,
    }),
  );
}
process.exitCode = result.status === 'COMPLETE' ? 0 : 1;
