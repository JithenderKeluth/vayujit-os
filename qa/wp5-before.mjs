import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Product, wp3Owner } from './wp3-fixtures.mjs';
import { wp5Operations } from './wp5-fixtures.mjs';

const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const w = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (
  !s.synthetic ||
  s.schema !== 'ALEMBIC_HEAD' ||
  s.status !== 'READY' ||
  !w.disposable ||
  w.token !== s.token
)
  throw Error('APPROVED_QA_REQUIRED');
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
});
const runs = [],
  report = { token: s.token, status: 'RUNNING', observations: [], ids: {} };
try {
  const d = await start(browser, s, { width: 1440, height: 900 }, 'wp5-before-desktop');
  runs.push(d);
  const p = d.page;
  p.setDefaultTimeout(20000);
  await p.goto(s.origin + '/setup');
  await p.locator('#full-name').fill('[QA SYNTHETIC] WP5 Owner');
  await p.locator('#email').fill(wp3Owner.email);
  await p.locator('#password').fill(wp3Owner.password);
  await p.locator('#confirmation').fill(wp3Owner.password);
  await p.getByRole('button', { name: 'Create owner', exact: true }).click();
  await p.waitForURL('**/dashboard');
  await expect(
    p.getByRole('heading', { name: 'What should you do today?', exact: true }),
  ).toBeVisible();
  await capture(d, 'new-seller-dashboard', true);
  for (const route of ['/marketplaces/orders', '/marketplaces/financials']) {
    await p.goto(s.origin + route);
    await capture(d, route.split('/').at(-1) + '-empty', true);
  }
  const { api, brand, goal, op } = await wp3Product(p, s.origin);
  report.ids = { goal: goal.id, opportunity: op.id };
  await api('post', 'publishing/destinations', {
    name: '[QA SYNTHETIC] WP5 local destination',
    connector_key: 'mock_publisher_v1',
    configuration: { channel_name: 'QA-WP5-LOCAL' },
  });
  await p.goto(s.origin + '/dashboard');
  await capture(d, 'research-without-inventory', true);
  const fixture = await wp5Operations(api, brand);
  report.ids.product = fixture.product.id;
  report.ids.order = fixture.order.id;
  await p.goto(s.origin + '/marketplaces/orders');
  const row = p.getByRole('row').filter({ hasText: 'QA-WP5-ORDER' });
  await row.getByRole('button', { name: 'View details', exact: true }).click();
  await expect(p.getByRole('heading', { name: 'Order QA-WP5-ORDER', exact: true })).toBeVisible();
  report.observations.push({
    id: 'WP5-ORDER-CONTEXT',
    detail: await p.locator('[aria-label="Order details"]').innerText(),
  });
  await capture(d, 'order-detail-no-line-links', true);
  await axe(d, 'orders');
  await p.goto(s.origin + '/marketplaces/financials');
  await expect(p.locator('[aria-label="Financial evidence provenance"]')).toContainText(
    'Synthetic',
  );
  await capture(d, 'finance-missing-costs', true);
  await axe(d, 'finance');
  // A failed new filter must not masquerade as current successful evidence.
  await p.route('**/api/v1/financial/summary?*', (r) =>
    r.fulfill({
      status: 503,
      contentType: 'application/json',
      body: '{"detail":"Synthetic outage"}',
    }),
  );
  await p.locator('[aria-label="Financial filters"] select').selectOption('amazon');
  await expect(
    p.getByRole('heading', { name: 'Financial evidence is unavailable', exact: true }),
  ).toBeVisible();
  report.observations.push({
    id: 'WP5-FINANCE-STALE-FILTER',
    oldSummaryStillVisible: await p.locator('[aria-label="Sales summary"]').count(),
  });
  await capture(d, 'failed-finance-filter-old-figures', true);
  await p.unroute('**/api/v1/financial/summary?*');
  await p.goto(s.origin + '/operations/action-center');
  await expect(p.locator('.signal-card').first()).toBeVisible();
  await capture(d, 'multiple-operational-signals', true);
  await p.route('**/api/v1/operations/action-center/scan', (r) =>
    r.fulfill({
      status: 503,
      contentType: 'application/json',
      body: '{"detail":"Synthetic outage"}',
    }),
  );
  const scanFailure = p.waitForResponse(
    (r) => r.url().endsWith('/action-center/scan') && r.status() === 503,
  );
  await p.getByRole('button', { name: 'Refresh scan', exact: true }).click();
  await scanFailure;
  await capture(d, 'scan-failure-feedback');
  await p.unroute('**/api/v1/operations/action-center/scan');
  const m = await start(browser, s, { width: 390, height: 844 }, 'wp5-before-mobile');
  runs.push(m);
  await m.context.addCookies(await d.context.cookies());
  await m.page.goto(s.origin + '/dashboard');
  await m.page.getByText('Application menu', { exact: true }).click();
  await m.page.getByRole('link', { name: 'Action Center', exact: true }).click();
  report.observations.push({
    id: 'SE-BROWSER-012',
    menuOpen: await m.page.locator('details.mobile-menu').getAttribute('open'),
  });
  await capture(m, 'menu-after-navigation', true);
  await m.page.goto(s.origin + '/marketplaces/financials');
  await capture(m, 'finance-mobile', true);
  await axe(m, 'finance-mobile');
  // Second installed browser, same witnessed disposable installation, actual auth cookie.
  const edge = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const e = await start(edge, s, { width: 1440, height: 900 }, 'wp5-before-edge');
    runs.push(e);
    await e.context.addCookies(await d.context.cookies());
    await e.page.goto(s.origin + '/operations/action-center');
    await capture(e, 'edge-action-center', true);
    await finish(e);
    runs.pop();
  } finally {
    await edge.close();
  }
  report.status = 'COMPLETE';
} catch (e) {
  report.status = 'BLOCKED';
  report.error = e.message.slice(0, 1200);
  for (const r of runs) await capture(r, 'before-blocker').catch(() => {});
} finally {
  for (const r of runs) await finish(r);
  await browser.close();
  await fs.writeFile(path.join(s.folder, 'wp5-before.json'), JSON.stringify(report, null, 2));
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP5 before complete');
  console.log(JSON.stringify(report));
}
process.exitCode = report.status === 'COMPLETE' ? 0 : 1;
