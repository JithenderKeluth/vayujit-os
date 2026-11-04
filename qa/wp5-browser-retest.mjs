import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect as baseExpect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Product, wp3Owner } from './wp3-fixtures.mjs';
import { wp5Operations } from './wp5-fixtures.mjs';
import { wp3UnexpectedSignals } from './wp3-reporting.mjs';
const expect = baseExpect.configure({ timeout: 20000 });
const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const witness = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (
  !s.synthetic ||
  s.status !== 'READY' ||
  s.schema !== 'ALEMBIC_HEAD' ||
  !witness.disposable ||
  witness.token !== s.token
)
  throw Error('APPROVED_QA_REQUIRED');
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
    axe_exposed: [],
    synthetic: true,
  };
let edge;
async function check(name, fn) {
  try {
    await fn();
    report.checks.push({ name, status: 'PASS' });
  } catch (e) {
    report.checks.push({ name, status: 'FAIL', error: e.message.slice(0, 1400) });
    throw e;
  }
}
async function scan(run, state) {
  const result = await axe(run, state);
  expect(result.violations).toEqual([]);
  for (const rule of result.incomplete.filter((r) => r.id === 'color-contrast'))
    for (const node of rule.nodes) {
      if (node.target.length !== 1 || typeof node.target[0] !== 'string') {
        report.axe_exposed.push({ state, target: node.target, status: 'MANUAL' });
        continue;
      }
      const loc = run.page.locator(node.target[0]);
      if ((await loc.count()) !== 1) {
        report.axe_exposed.push({ state, target: node.target, status: 'AMBIGUOUS' });
        continue;
      }
      await loc.evaluate((e) => e.scrollIntoView({ block: 'center', inline: 'center' }));
      const exposed = await loc.evaluate(async (e) => {
        const r = await window.axe.run(e, {
          runOnly: { type: 'rule', values: ['color-contrast'] },
        });
        return { violations: r.violations, incomplete: r.incomplete, passes: r.passes.length };
      });
      report.axe_exposed.push({ state, target: node.target, ...exposed });
      expect(exposed.violations).toEqual([]);
    }
}
try {
  const d = await start(browser, s, { width: 1440, height: 900 }, 'wp5-desktop');
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
  await check(
    'New seller dashboard distinguishes empty local records, UNKNOWN profitability and no connection proof',
    async () => {
      await expect(p.locator('#daily-status-title')).toBeVisible();
      await expect(p.locator('.dashboard-page')).toContainText('0 recorded account(s)');
      await expect(p.locator('.dashboard-page')).toContainText('0 inventory record(s)');
      await p.goto(s.origin + '/marketplaces/financials');
      await expect(p.locator('[aria-label="Sales summary"]')).toContainText('UNKNOWN');
      await expect(p.locator('[aria-label="Financial reporting scope"]')).toContainText(
        'not an accounting ledger',
      );
      await capture(d, 'new-seller-unknown-finance', true);
      await scan(d, 'empty-finance');
    },
  );
  const { api, brand, goal, op } = await wp3Product(p, s.origin);
  report.ids.goal = goal.id;
  report.ids.opportunity = op.id;
  await check(
    'Research without inventory and mock destination does not mean a connected sales channel',
    async () => {
      await api('post', 'publishing/destinations', {
        name: '[QA SYNTHETIC] WP5 local',
        connector_key: 'mock_publisher_v1',
        configuration: { channel_name: 'QA-WP5-LOCAL' },
      });
      await p.goto(s.origin + '/dashboard');
      await expect(p.locator('.opportunity-item')).toContainText(
        '1 configured publishing destination',
      );
      await expect(p.locator('.dashboard-page')).not.toContainText('sales channel connected');
      await expect(p.locator('.dashboard-page')).toContainText('0 inventory record(s)');
      await capture(d, 'research-configuration-not-connection', true);
    },
  );
  const f = await wp5Operations(api, brand);
  Object.assign(report.ids, {
    product: f.product.id,
    order: f.order.id,
    inventory: f.item.id,
    zero: f.zero.id,
  });
  await check(
    'Persisted synthetic order replay reserves once; cancellation is visible and does not imply refund',
    async () => {
      expect((await api('post', 'orders/fake/events', f.event('QA-WP5-ORDER'))).id).toBe(
        f.order.id,
      );
      const inventory = await api('get', 'inventory');
      expect(inventory.find((x) => x.id === f.item.id).reserved_quantity).toBe(2);
      expect((await api('get', 'orders')).length).toBe(2);
      await p.goto(s.origin + '/marketplaces/orders');
      await expect(p.getByRole('row').filter({ hasText: 'QA-WP5-CANCEL' })).toContainText(
        'cancelled',
      );
      await expect(p.locator('table')).toContainText('Synthetic fixture');
      await p
        .getByRole('row')
        .filter({ hasText: 'QA-WP5-ORDER' })
        .getByRole('button', { name: 'View details', exact: true })
        .click();
      await expect(p.locator('[aria-label="Order details"]')).toContainText('QA-WP5-BOX');
      await expect(p.locator('[aria-label="Order details"]')).toContainText(
        'Stored unit price (rounded)',
      );
      await expect(p.locator('[aria-label="Order details"]')).toContainText(
        'must not be reconstructed',
      );
      await expect(p).toHaveURL(new RegExp('order_id=' + f.order.id));
      await capture(d, 'synthetic-order-context', true);
      await scan(d, 'populated-orders');
    },
  );
  await check(
    'Order detail product and inventory handoffs preserve exact owned product across history and reload',
    async () => {
      await p.getByRole('link', { name: 'Review this product', exact: true }).click();
      await expect(p).toHaveURL(s.origin + '/catalog/' + f.product.id);
      await p.goBack();
      await expect(
        p.getByRole('heading', { name: 'Order QA-WP5-ORDER', exact: true }),
      ).toBeVisible();
      await p.getByRole('link', { name: 'Review this product inventory', exact: true }).click();
      await expect(p).toHaveURL(new RegExp('product_id=' + f.product.id));
      await expect(p.getByRole('rowheader', { name: 'QA-WP5-BOX', exact: true })).toBeVisible();
      await p.goto(s.origin + '/marketplaces/orders?order_id=' + f.order.id);
      await p.reload();
      await expect(
        p.getByRole('heading', { name: 'Order QA-WP5-ORDER', exact: true }),
      ).toBeVisible();
    },
  );
  await check('Invalid order identifiers fail closed without selecting another order', async () => {
    await p.goto(s.origin + '/marketplaces/orders?order_id=invalid');
    await expect(p.getByRole('alert')).toContainText('Invalid order identifier');
    expect(await p.locator('[aria-label="Order details"]').count()).toBe(0);
  });
  await check(
    'Order list outage is not an empty history and Retry restores persisted records',
    async () => {
      const endpoint = '/api/v1/orders';
      d.signals.expected_http_errors = [{ path: endpoint, status: 503 }];
      await p.route('**' + endpoint, (r) =>
        r.fulfill({
          status: 503,
          contentType: 'application/json',
          body: '{"detail":"Synthetic order read outage"}',
        }),
      );
      await p.goto(s.origin + '/marketplaces/orders');
      await expect(
        p.getByRole('heading', { name: 'Orders are unavailable', exact: true }),
      ).toBeVisible();
      await expect(
        p.getByRole('heading', { name: 'No matching local orders', exact: true }),
      ).toHaveCount(0);
      await capture(d, 'order-read-outage-not-empty');
      await p.unroute('**' + endpoint);
      await p.getByRole('button', { name: 'Retry', exact: true }).click();
      await expect(p.getByRole('row').filter({ hasText: 'QA-WP5-ORDER' })).toBeVisible();
    },
  );
  await check(
    'Dashboard reflects synthetic orders and missing financial inputs, not real sales or healthy status',
    async () => {
      await p.goto(s.origin + '/dashboard');
      await expect(p.locator('.dashboard-page')).toContainText('Synthetic records: 2');
      await expect(p.locator('.dashboard-page')).toContainText('not real seller revenue');
      await expect(p.locator('.dashboard-page')).toContainText('Review operational evidence');
      await capture(d, 'daily-synthetic-operational-status', true);
      await scan(d, 'dashboard');
    },
  );
  await check(
    'Finance uses exact INR evidence, unknown costs, scoped periods and truthful snapshot-history limitation',
    async () => {
      await p.goto(s.origin + '/marketplaces/financials');
      await expect(p.locator('[aria-label="Sales summary"]')).toContainText('₹200.25');
      await expect(p.locator('[aria-label="Sales summary"]')).toContainText('₹20.05');
      await expect(p.locator('[aria-label="Sales summary"]')).toContainText('UNKNOWN');
      await expect(p.locator('[aria-label="Financial reporting scope"]')).toContainText(
        'not immutable accounting history',
      );
      await capture(d, 'partial-finance-provenance-and-period', true);
      await scan(d, 'partial-finance');
      const result = await api('get', 'financial/summary');
      expect(result.gross_sales).toBe('200.25');
      expect(result.fees).toBe('20.05');
      expect(result.contribution).toBe('UNKNOWN');
      expect(result.synthetic_provider).toBe(true);
    },
  );
  await check(
    'Failed financial filter clears old figures; exact outage recovers without false empty success',
    async () => {
      const endpoint = '/api/v1/financial/summary';
      d.signals.expected_http_errors.push({ path: endpoint, status: 503 });
      await p.route('**' + endpoint + '?*', (r) =>
        r.fulfill({
          status: 503,
          contentType: 'application/json',
          body: '{"detail":"Synthetic outage"}',
        }),
      );
      await p.getByLabel('Marketplace', { exact: true }).selectOption('amazon');
      await expect(
        p.getByRole('heading', { name: 'Financial evidence is unavailable', exact: true }),
      ).toBeVisible();
      expect(await p.locator('[aria-label="Sales summary"]').count()).toBe(0);
      await capture(d, 'finance-failure-no-old-figures');
      await p.unroute('**' + endpoint + '?*');
      await p.getByRole('button', { name: 'Retry', exact: true }).click();
      await expect(p.locator('[aria-label="Sales summary"]')).toContainText('UNKNOWN');
      await p.getByLabel('Marketplace', { exact: true }).selectOption('flipkart');
      await expect(p.locator('[aria-label="Sales summary"]')).toContainText('₹200.25');
    },
  );
  await check('Date boundaries and invalid ranges do not reuse outside-period data', async () => {
    await p.getByLabel('Date from', { exact: true }).fill('2027-01-01');
    await expect(p.locator('[aria-label="Sales summary"]')).toContainText('UNKNOWN');
    await p.getByLabel('Date to', { exact: true }).fill('2026-10-01');
    await expect(p.getByRole('alert')).toContainText('Date from must not');
    expect(await p.locator('[aria-label="Sales summary"]').count()).toBe(0);
    await p.getByLabel('Date from', { exact: true }).fill('2026-10-01');
    await expect(p.locator('[aria-label="Sales summary"]')).toContainText('₹200.25');
    await p.reload();
    await expect(p.locator('[aria-label="Sales summary"]')).toContainText('₹200.25');
  });
  await check(
    'Action Center explains evidence, HUMAN local notice lifecycle, duplicate protection and safe source navigation',
    async () => {
      await p.goto(s.origin + '/operations/action-center');
      const card = p.locator('.signal-card').filter({ hasText: 'QA-WP5-ZERO' });
      await expect(card).toBeVisible();
      await expect(card).toContainText('Advisory only');
      await card.getByRole('button', { name: 'Inspect evidence', exact: true }).click();
      await expect(card.locator('.evidence-panel')).toContainText(f.zero.id);
      await capture(d, 'signal-evidence-and-local-actions', true);
      await card.getByRole('button', { name: 'Acknowledge', exact: true }).dblclick();
      await expect(p.getByRole('status').filter({ hasText: 'Signal acknowledged.' })).toBeVisible();
      const signal = (await api('get', 'operations/action-center')).signals.find(
        (x) => x.source_resource_id === f.zero.id,
      );
      const detail = await api('get', 'operations/action-center/signals/' + signal.id);
      expect(detail.history.filter((x) => x.to_status === 'ACKNOWLEDGED').length).toBe(1);
      await p.reload();
      await expect(card).toContainText('ACKNOWLEDGED');
      await card.getByRole('link', { name: 'Open source', exact: true }).click();
      await expect(p).toHaveURL(new RegExp('product_id='));
      await expect(p.getByRole('rowheader', { name: 'QA-WP5-ZERO', exact: true })).toBeVisible();
    },
  );
  await check(
    'Resolved notice remains distinguishable and ongoing canonical shortage reopens on rescan',
    async () => {
      await p.goto(s.origin + '/operations/action-center');
      const card = p.locator('.signal-card').filter({ hasText: 'QA-WP5-ZERO' });
      await card.getByRole('button', { name: 'Resolve notice locally', exact: true }).click();
      await p.getByLabel('Status', { exact: true }).selectOption('RESOLVED');
      await expect(card).toContainText('RESOLVED');
      await p.getByRole('button', { name: 'Refresh scan', exact: true }).click();
      await p.getByLabel('Status', { exact: true }).selectOption('');
      await expect(card).toContainText('REOPENED');
    },
  );
  await check(
    'Legitimate stock change stales obsolete recommendation and stale action is rejected',
    async () => {
      const old = (await api('get', 'operations/action-center')).signals.find(
        (x) => x.source_resource_id === f.zero.id,
      );
      await api('post', 'inventory/' + f.zero.id + '/adjust', {
        delta: 10,
        expected_version: f.zero.version,
        reason: '[QA SYNTHETIC] Counted receipt',
        idempotency_key: 'wp5-receipt',
      });
      await p.reload();
      await expect(p.locator('.signal-card').filter({ hasText: 'QA-WP5-ZERO' })).toHaveCount(0);
      await p.getByLabel('Status', { exact: true }).selectOption('STALE');
      await expect(p.locator('.signal-card').filter({ hasText: 'QA-WP5-ZERO' })).toContainText(
        'Historical evidence only',
      );
      const denied = await p.request.post(
        s.origin + '/api/v1/operations/action-center/signals/' + old.id + '/acknowledge',
        { data: { idempotency_key: 'wp5-stale-browser' } },
      );
      expect(denied.status()).toBe(409);
      await capture(d, 'stale-signal-after-real-condition-change', true);
    },
  );
  await check(
    'Scan failure gives useful feedback, no false success; retry remains usable',
    async () => {
      const endpoint = '/api/v1/operations/action-center/scan';
      d.signals.expected_http_errors.push({ path: endpoint, status: 503 });
      await p.route('**' + endpoint, (r) =>
        r.fulfill({
          status: 503,
          contentType: 'application/json',
          body: '{"detail":"Synthetic outage"}',
        }),
      );
      await p.getByRole('button', { name: 'Refresh scan', exact: true }).click();
      await expect(p.getByRole('alert')).toContainText('not confirmed');
      await p.unroute('**' + endpoint);
      await p.getByRole('button', { name: 'Refresh scan', exact: true }).click();
      await expect(p.getByRole('status').filter({ hasText: 'rescanned' })).toBeVisible();
      await scan(d, 'action-center-recovered');
    },
  );
  await check(
    'Explicit synthetic cost produces negative contribution, current snapshot is mutable not fabricated accounting history',
    async () => {
      await api('post', 'financial/costs', {
        product_id: f.product.id,
        cost_key: 'wp5-known-cost',
        cost_type: 'acquisition',
        amount: '300.00',
        currency: 'INR',
        evidence_status: 'reported',
        source_type: 'synthetic_fixture',
        effective_from: '2026-09-01T00:00:00Z',
      });
      const current = await api('post', 'financial/calculations/recalculate', {});
      expect(current.metrics.contribution).toBe('-119.80');
      await p.goto(s.origin + '/marketplaces/financials');
      await expect(p.locator('[aria-label="Sales summary"]')).toContainText('₹-119.80');
      await expect(p.locator('[aria-label="Sales summary"]')).toContainText('not net profit');
      await capture(d, 'negative-synthetic-contribution', true);
      await scan(d, 'qualified-synthetic-contribution');
      await api('post', 'financial/events', f.financial('wp5-extra-fee', 'fee', '1.00'));
      const next = await api('post', 'financial/calculations/recalculate', {});
      expect(next.id).toBe(current.id);
      expect(next.metrics.contribution).toBe('-120.80');
      expect((await api('get', 'financial/calculations')).length).toBe(1);
    },
  );
  await check(
    'Business Agent daily guidance links existing supported workflows and never claims execution',
    async () => {
      await p.goto(s.origin + '/intelligence/business-agent?goal_id=' + goal.id);
      await expect(p.locator('[aria-label="Daily operational guidance"]')).toContainText(
        'do not synchronize orders or execute',
      );
      await p
        .locator('[aria-label="Daily operational guidance"]')
        .getByRole('link', {
          name: 'Review evidence-backed operational recommendations',
          exact: true,
        })
        .click();
      await expect(p).toHaveURL(s.origin + '/operations/action-center');
      await api('post', 'operations/action-center/scan', {});
      await p.reload();
      await expect(
        p.locator('.signal-card').filter({ hasText: 'Negative contribution' }),
      ).toBeVisible();
      await capture(d, 'agent-handoff-multiple-recommendations', true);
    },
  );
  const m = await start(browser, s, { width: 390, height: 844 }, 'mobile');
  runs.push(m);
  await m.context.addCookies(await d.context.cookies());
  const mp = m.page;
  mp.setDefaultTimeout(20000);
  await check(
    'Mobile menu closes after navigation with main focus; keyboard remains usable',
    async () => {
      await mp.goto(s.origin + '/dashboard');
      await expect(mp.locator('#daily-status-title')).toBeVisible();
      await mp.getByText('Application menu', { exact: true }).focus();
      await mp.keyboard.press('Enter');
      await mp.getByRole('link', { name: 'Action Center', exact: true }).focus();
      await mp.keyboard.press('Enter');
      await expect(mp.locator('details.mobile-menu')).not.toHaveAttribute('open');
      await expect(mp.locator('#main-content')).toBeFocused();
      await capture(m, 'mobile-navigation-focus');
      await scan(m, 'mobile-action-center');
    },
  );
  await check(
    'Mobile orders, product handoff and finance remain persisted, provenance-labelled and viewport-contained',
    async () => {
      await mp.goto(s.origin + '/marketplaces/orders?order_id=' + f.order.id);
      await expect(
        mp.getByRole('link', { name: 'Review this product', exact: true }),
      ).toHaveAttribute('href', '/catalog/' + f.product.id);
      await mp.reload();
      await expect(mp.locator('[aria-label="Order details"]')).toContainText('Synthetic');
      expect(await mp.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      await capture(m, 'mobile-order-product-context', true);
      await scan(m, 'mobile-orders');
      await mp.goto(s.origin + '/marketplaces/financials');
      await expect(mp.locator('[aria-label="Sales summary"]')).toContainText('₹-120.80');
      expect(await mp.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      await capture(m, 'mobile-finance-current-projection', true);
      await scan(m, 'mobile-finance');
    },
  );
  edge = await chromium.launch({ channel: 'msedge', headless: true });
  await check(
    'Installed Edge desktop and mobile render authenticated daily status, order and finance source context',
    async () => {
      for (const [label, viewport] of [
        ['wp5-edge-desktop', { width: 1440, height: 900 }],
        ['wp5-edge-mobile', { width: 390, height: 844 }],
      ]) {
        const e = await start(edge, s, viewport, label);
        runs.push(e);
        await e.context.addCookies(await d.context.cookies());
        await e.page.goto(s.origin + '/dashboard');
        await expect(e.page.locator('#daily-status-title')).toBeVisible();
        await e.page.goto(s.origin + '/marketplaces/orders?order_id=' + f.order.id);
        await expect(e.page.locator('[aria-label="Order details"]')).toContainText('QA-WP5-BOX');
        await e.page.goto(s.origin + '/marketplaces/financials');
        await expect(e.page.locator('[aria-label="Sales summary"]')).toContainText('₹-120.80');
        await capture(e, 'edge-persisted-finance', true);
        await scan(e, label);
      }
    },
  );
  await check(
    'Financial recommendation becomes historical when legitimate revised evidence clears its condition',
    async () => {
      await api('post', 'financial/events', f.financial('wp5-additional-sale', 'sale', '500.00'));
      const revised = await api('post', 'financial/calculations/recalculate', {});
      expect(revised.metrics.contribution).toBe('379.20');
      await p.goto(s.origin + '/operations/action-center');
      await p.getByRole('button', { name: 'Refresh scan', exact: true }).click();
      await expect(p.getByRole('status').filter({ hasText: 'rescanned' })).toBeVisible();
      await expect(
        p.locator('.signal-card').filter({ hasText: 'Negative contribution' }),
      ).toHaveCount(0);
      await p.getByLabel('Status', { exact: true }).selectOption('STALE');
      await expect(
        p.locator('.signal-card').filter({ hasText: 'Negative contribution' }),
      ).toContainText('Historical evidence only');
      await capture(d, 'financial-warning-legitimate-resolution', true);
    },
  );
  await check(
    'Unexpected console, page, failed request and server errors remain zero in every final browser context',
    async () => {
      report.signals = runs.map((r) => ({
        label: r.label,
        unexpected: wp3UnexpectedSignals(r.signals),
      }));
      for (const row of report.signals)
        for (const values of Object.values(row.unexpected)) expect(values).toEqual([]);
    },
  );
  report.status = 'COMPLETE';
} catch (e) {
  report.status = 'BLOCKED';
  report.error = e.message.slice(0, 1600);
  for (const r of runs) await capture(r, 'retest-blocker').catch(() => {});
} finally {
  for (const r of runs) await finish(r);
  if (edge) await edge.close();
  await browser.close();
  await fs.writeFile(path.join(s.folder, 'wp5-retest.json'), JSON.stringify(report, null, 2));
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP5 retest complete');
  console.log(
    JSON.stringify({
      token: s.token,
      status: report.status,
      passed: report.checks.filter((c) => c.status === 'PASS').length,
      failed: report.checks.filter((c) => c.status === 'FAIL').length,
      error: report.error,
    }),
  );
}
process.exitCode = report.status === 'COMPLETE' ? 0 : 1;
