import fs from 'node:fs/promises';
import path from 'node:path';
import {
  test,
  expect,
  login,
  scanAxe,
  visitSurface,
  attach,
  inspectContrastNode,
} from '../explore.mjs';

async function artifacts() {
  return JSON.parse(
    await fs.readFile(path.join(process.env.QA_RUN_DIR, 'phase4c-manifest.json'), 'utf8'),
  );
}
test('QA-P4C-01 canonical draft campaign context routes', async ({ page }, info) => {
  await login(page);
  const m = await artifacts();
  for (const [suffix, heading] of [
    ['', '[QA SYNTHETIC] Phase 4C local draft'],
    ['/activities/new', 'Add Campaign activity'],
    ['/dependencies', 'Activity dependencies'],
    ['/video', '[QA SYNTHETIC] Phase 4C local draft'],
  ]) {
    const route = '/campaigns/:id' + suffix;
    const data = await visitSurface(page, info, {
      route,
      target: '/campaigns/' + m.campaign_id + suffix,
    });
    expect(data.route_match).toBe(true);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    expect(
      (
        await scanAxe(page, info, 'campaign-' + (suffix.replaceAll('/', '-') || 'detail'))
      ).violations.filter((v) => ['critical', 'serious'].includes(v.impact)),
    ).toEqual([]);
  }
  await page.reload();
  await expect(
    page.getByRole('heading', { name: '[QA SYNTHETIC] Phase 4C local draft', exact: true }),
  ).toBeVisible();
});
test('QA-P4C-02 private media persists and remains authenticated', async ({ page }, info) => {
  await login(page);
  const m = await artifacts();
  const data = await visitSurface(page, info, {
    route: '/media/:id',
    target: '/media/' + m.media_id,
  });
  expect(data.route_match).toBe(true);
  await expect(page.getByRole('heading', { name: m.media_filename, exact: true })).toBeVisible();
  await expect(page.getByRole('img', { name: m.media_filename, exact: true })).toBeVisible();
  expect((await page.request.get('/api/v1/media/' + m.media_id + '/preview')).status()).toBe(200);
  expect((await scanAxe(page, info, 'media-detail')).violations).toEqual([]);
  await page.reload();
  await expect(page.getByRole('heading', { name: m.media_filename, exact: true })).toBeVisible();
  expect((await page.request.post('/api/v1/auth/logout')).status()).toBe(204);
  expect((await page.request.get('/api/v1/media/' + m.media_id + '/preview')).status()).toBe(401);
});
test('QA-P4C-03 settings context keyboard and current warning screens', async ({ page }, info) => {
  test.setTimeout(240000);
  await login(page);
  for (const section of [
    'general',
    'profile',
    'appearance',
    'security',
    'ai',
    'publishing',
    'system',
  ]) {
    const data = await visitSurface(page, info, {
      route: '/settings/:section',
      target: '/settings/' + section,
    });
    expect(data.route_match).toBe(true);
    await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
    const link = page
      .getByRole('navigation', { name: 'Settings sections' })
      .getByRole('link')
      .first();
    await link.focus();
    await expect(link).toBeFocused();
    await page.keyboard.press('Tab');
    await page.keyboard.press('Shift+Tab');
    await expect(link).toBeFocused();
    expect(
      (await scanAxe(page, info, 'settings-' + section)).violations.filter((v) =>
        ['critical', 'serious'].includes(v.impact),
      ),
    ).toEqual([]);
  }
  for (const route of ['/marketplaces/accounts', '/ai/video', '/intelligence/autonomous']) {
    const data = await visitSurface(page, info, { route, target: route });
    expect(data.route_match).toBe(true);
    await attach(info, 'current-warning-dimensions', {
      route,
      viewport: data.viewport,
      document: data.document,
    });
    await scanAxe(page, info, 'warning-' + route.replaceAll('/', '-'));
  }
  await page.goto('/marketplaces/inventory');
  await page.waitForLoadState('networkidle');
  await scanAxe(page, info, 'inventory-full');
  const caption = page.locator('table caption').first();
  expect(await caption.count()).toBe(1);
  const review = await inspectContrastNode(page, info, caption, 'inventory-caption');
  expect(review.text_horizontally_in_view).toBe(true);
  expect(review.violations).toEqual([]);
});
test('QA-P4C-04 catalog currency and persisted context audit', async ({ page }, info) => {
  test.setTimeout(180000);
  await login(page);
  const m = JSON.parse(
    await fs.readFile(path.join(process.env.QA_RUN_DIR, 'phase3-manifest.json'), 'utf8'),
  );
  const product = await (await page.request.get('/api/v1/products/' + m.phase2.product_id)).json();
  const target = '/products/' + product.id;
  const data = await visitSurface(page, info, { route: '/products/:id', target });
  expect(data.route_match).toBe(true);
  await expect(page.getByRole('heading', { name: product.name, exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: product.name, exact: true })).toBeVisible();
  await page.goto('/products/new');
  const currency = page.getByLabel('Currency', { exact: true });
  await expect(currency).toBeVisible();
  await attach(info, 'currency-observation', {
    currency: await currency.inputValue(),
    classification: 'observation, not acceptance or closure of currency finding',
  });
  await currency.focus();
  await expect(currency).toBeFocused();
  await page.keyboard.press('Tab');
  await page.keyboard.press('Shift+Tab');
  await expect(currency).toBeFocused();
  expect((await scanAxe(page, info, 'catalog-create')).violations).toEqual([]);
});
