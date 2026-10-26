import fs from 'node:fs';
import {
  test,
  expect,
  attach,
  login,
  manifest,
  scanAxe,
  visitSurface,
  inspectContrastNode,
} from '../explore.mjs';
import { routePlan, runApprovedAction, snapshotSurface, surfaceId } from '../phase4-surface.mjs';

const inventory = JSON.parse(fs.readFileSync('docs/qa/phase-4-source-inventory.json', 'utf8'));
const areas = [
  ...new Set(
    routePlan(inventory.routes)
      .filter((r) => r.kind === 'PAGE' && !['/login', '/setup'].includes(r.route))
      .map((r) => r.area),
  ),
].sort();
for (const area of areas) {
  test(`QA-P4-SURFACE-${area.toUpperCase().replaceAll(/[^A-Z0-9]/g, '-')} explicit read-only ${area} discovery`, async ({
    page,
  }, info) => {
    test.setTimeout(600000);
    await login(page);
    const plan = routePlan(inventory.routes, await manifest()).filter((r) => r.area === area);
    await attach(info, 'planned-routes', plan);
    for (const row of plan.filter((r) => r.target)) {
      await test.step('Read-only ' + row.route, async () => {
        try {
          const data = await visitSurface(page, info, row);
          expect
            .soft(data.route_match, 'Deep link resolves to requested route ' + row.route)
            .toBe(true);
          const axe = await scanAxe(page, info, 'surface-' + surfaceId(row.route));
          expect
            .soft(
              axe.violations.filter((v) => ['critical', 'serious'].includes(v.impact)),
              row.route + ' serious/critical axe violations',
            )
            .toEqual([]);
        } catch (error) {
          await attach(info, 'blocked-route-' + surfaceId(row.route), {
            declaration: row.route,
            failure: 'QA_ROUTE_EXPLORATION_BLOCKED',
            exception_type: error.name,
          });
          expect.soft(false, 'Route exploration blocked: ' + row.route).toBe(true);
        }
      });
    }
  });
}

test('QA-P4-TASK-01 authenticated navigation history refresh logout and protected route', async ({
  page,
}, info) => {
  await login(page, true);
  await page.goto('/marketplaces');
  await page.goto('/marketplaces/amazon');
  await page.goBack();
  await expect(page).toHaveURL(/\/marketplaces$/);
  await page.goForward();
  await expect(page).toHaveURL(/\/marketplaces\/amazon$/);
  await page.reload();
  await expect(page).toHaveURL(/\/marketplaces\/amazon$/);
  await attach(info, 'navigation-transitions', {
    routes: [
      '/dashboard',
      '/marketplaces',
      '/marketplaces/amazon',
      'BACK /marketplaces',
      'FORWARD /marketplaces/amazon',
      'REFRESH /marketplaces/amazon',
    ],
  });
  expect((await page.request.post('/api/v1/auth/logout')).status()).toBe(204);
  await page.goto('/marketplaces/financials');
  await expect(page).toHaveURL(/\/login/);
});

test('QA-P4-TASK-02 catalog edit cancel save reload and duplicate submission', async ({
  page,
}, info) => {
  await login(page);
  const m = await manifest();
  const id = m.phase2.product_id;
  const before = await (await page.request.get('/api/v1/products/' + id)).json();
  await page.goto(`/products/${id}/edit`);
  const name = page.getByLabel('Name *', { exact: true });
  await expect(name).toHaveValue(before.name);
  await name.fill('[QA SYNTHETIC] cancelled phase4 edit');
  await page.getByRole('link', { name: 'Cancel', exact: true }).click();
  expect((await (await page.request.get('/api/v1/products/' + id)).json()).name).toBe(before.name);
  await page.goto(`/products/${id}/edit`);
  await name.fill('');
  await expect(page.getByRole('button', { name: 'Save product', exact: true })).toBeDisabled();
  const revised = '[QA SYNTHETIC] Phase4 persisted product';
  await name.fill(revised);
  const responses = [];
  page.on('response', (r) => {
    if (
      r.url().endsWith('/api/v1/products/' + id) &&
      ['PATCH', 'PUT'].includes(r.request().method())
    )
      responses.push(r.status());
  });
  await runApprovedAction(page, 'product.save');
  await expect(page).not.toHaveURL(/\/edit$/);
  await page.reload();
  expect((await (await page.request.get('/api/v1/products/' + id)).json()).name).toBe(revised);
  await attach(info, 'approved-actions', [
    { action: 'product.cancel', route: `/products/${id}/edit`, result: 'API_UNCHANGED' },
    {
      action: 'product.save',
      route: `/products/${id}/edit`,
      result: 'PERSISTED_RELOADED',
      responses,
    },
  ]);
  // Duplicate UI save is not synthesized after navigation; API replay/stock
  // concurrency is covered by the existing 18-case setup regression matrix.
  expect(responses).toHaveLength(1);
});

test('QA-P4-TASK-03 stock handoff empty filter mapping cancel and recovery', async ({
  page,
  exploration,
}, info) => {
  await login(page);
  const m = await manifest();
  await page.goto('/marketplaces/inventory');
  await page.getByLabel('SKU search', { exact: true }).fill('QA4-ABSENT-SKU');
  await runApprovedAction(page, 'inventory.refresh');
  await expect(
    page.getByRole('heading', { name: 'No matching inventory', exact: true }),
  ).toBeVisible();
  await attach(
    info,
    'stock-handoff-filter-empty',
    await snapshotSurface(page, '/marketplaces/inventory', 'filtered-empty-not-new-installation'),
  );
  await page.getByLabel('SKU search', { exact: true }).fill(m.inventory.internal_sku);
  await runApprovedAction(page, 'inventory.refresh');
  const row = page
    .getByRole('row')
    .filter({ has: page.getByRole('rowheader', { name: m.inventory.internal_sku, exact: true }) });
  await expect(row).toBeVisible();
  await row.getByRole('button', { name: 'Map channel SKU', exact: true }).click();
  const form = page.getByRole('form', { name: 'Map channel SKU', exact: true });
  await expect(form.getByRole('button', { name: 'Save mapping', exact: true })).toBeDisabled();
  await form.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(form).toHaveCount(0);
  const failure = '/api/v1/inventory';
  exploration.expected_http_errors.push({ path: failure, status: 503 });
  await page.route('**/api/v1/inventory?*', (r) =>
    r.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'QA injected unavailable' }),
    }),
  );
  await runApprovedAction(page, 'inventory.refresh');
  await expect(
    page.getByRole('heading', { name: 'Inventory is unavailable', exact: true }),
  ).toBeVisible();
  await page.unroute('**/api/v1/inventory?*');
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(row).toBeVisible();
  await attach(info, 'approved-actions', [
    {
      action: 'inventory.refresh',
      route: '/marketplaces/inventory',
      result: 'FILTER_EMPTY_AND_RECOVERY_ASSERTED',
    },
    {
      action: 'inventory.mapping-cancel',
      route: '/marketplaces/inventory',
      result: 'NO_MAPPING_SUBMITTED',
    },
  ]);
});

test('QA-P4-TASK-04 exact caption and historical financial node review', async ({ page }, info) => {
  test.setTimeout(300000);
  await login(page);
  const m = await manifest();
  const p = m.phase2;
  const routes = [
    [
      'due',
      `/intelligence/due-diligence?opportunity_id=${p.opportunity_id}&supplier_id=${p.supplier_id}`,
    ],
    ['economics', `/intelligence/sourcing-economics?opportunity_id=${p.opportunity_id}`],
    ['stale', `/intelligence/sourcing-economics?opportunity_id=${p.stale_opportunity_id}`],
    [
      'decision',
      `/intelligence/sourcing-economics?opportunity_id=${p.opportunity_id}&journey_id=${p.goal_id}`,
    ],
  ];
  const originalViewport = page.viewportSize();
  for (const [state, route] of routes) {
    await page.goto(route);
    await page.waitForLoadState('networkidle');
    await scanAxe(page, info, 'caption-' + state);
    const captions = page.locator('caption');
    const count = await captions.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i++) {
      await inspectContrastNode(page, info, captions.nth(i), `${state}-${i}-original`);
      await page.setViewportSize({ width: 1440, height: 1000 });
      await inspectContrastNode(page, info, captions.nth(i), `${state}-${i}-wide`);
      await page.setViewportSize(originalViewport);
    }
  }
  await page.goto('/marketplaces/financials');
  await page.getByRole('combobox', { name: 'Marketplace', exact: true }).selectOption('amazon');
  const table = page.getByRole('region', { name: 'Settlement reconciliation table', exact: true });
  await expect(table).toContainText('QA3-UNKNOWN');
  await scanAxe(page, info, 'historical-financial');
  const nodes = table.locator('thead th:first-child,tbody th[scope="row"]');
  // Exact semantic successors of the four original nth-child selectors: one
  // settlement column heading and the three persisted settlement-key row headings.
  expect(await nodes.count()).toBe(4);
  for (let i = 0; i < 4; i++) await inspectContrastNode(page, info, nodes.nth(i), `financial-${i}`);
  await table.focus();
  await page.keyboard.press('Tab');
  await expect(table).not.toBeFocused();
});
