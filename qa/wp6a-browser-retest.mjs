import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect as baseExpect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Api, wp3Owner } from './wp3-fixtures.mjs';
import { wp3UnexpectedSignals } from './wp3-reporting.mjs';
const expect = baseExpect.configure({ timeout: 20000 });
const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const witness = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (
  !s.synthetic ||
  s.status !== 'READY' ||
  s.schema !== 'ALEMBIC_HEAD' ||
  s.qa_phase !== 'WP6A' ||
  !witness.disposable ||
  witness.token !== s.token
)
  throw Error('APPROVED_QA_REQUIRED');
const chrome = await chromium.launch({ channel: 'chrome', headless: true });
const runs = [],
  report = { token: s.token, status: 'RUNNING', checks: [], scans: [], ids: {}, synthetic: true };
let edge;
const persist = () =>
  fs.writeFile(path.join(s.folder, 'wp6a-retest.json'), JSON.stringify(report, null, 2));
async function check(name, fn) {
  try {
    await fn();
    report.checks.push({ name, status: 'PASS' });
  } catch (e) {
    report.checks.push({ name, status: 'FAIL', error: e.message.slice(0, 1500) });
    throw e;
  } finally {
    await persist();
  }
}
async function scan(run, state) {
  const r = await axe(run, state);
  report.scans.push({ context: run.label, ...r });
  expect(r.violations).toEqual([]);
  await persist();
}
async function login(run) {
  await run.page.goto(s.origin + '/login');
  await run.page.locator('#email').fill(wp3Owner.email);
  await run.page.locator('#password').fill(wp3Owner.password);
  await run.page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await run.page.waitForURL('**/dashboard');
}
async function routeReview(run, route) {
  await run.page.goto(s.origin + route);
  await expect(run.page.locator('main h1').first()).toBeVisible();
  await expect(run.page.locator('main')).not.toContainText('data is unavailable');
  await capture(run, route.replaceAll('/', '-'), true);
  await scan(run, route);
  expect(
    await run.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
  ).toBe(true);
}
try {
  const d = await start(chrome, s, { width: 1440, height: 900 }, 'wp6a-desktop');
  runs.push(d);
  const p = d.page;
  p.setDefaultTimeout(20000);
  await p.goto(s.origin + '/setup');
  await p.locator('#full-name').fill('[QA SYNTHETIC] WP6A Owner');
  await p.locator('#email').fill(wp3Owner.email);
  await p.locator('#password').fill(wp3Owner.password);
  await p.locator('#confirmation').fill(wp3Owner.password);
  await p.getByRole('button', { name: 'Create owner', exact: true }).click();
  await p.waitForURL('**/dashboard');
  const api = wp3Api(p, s.origin);
  await check(
    'Empty Video, Social and Ads/optimization reads succeed after actual fresh migrations',
    async () => {
      for (const route of ['/ai/video', '/social', '/ads', '/ads/optimization'])
        await routeReview(d, route);
      expect(await api('get', 'ai/video/generations')).toEqual([]);
      expect(await api('get', 'ads/campaigns')).toEqual([]);
    },
  );
  const brand = await api('post', 'brands', { name: '[QA SYNTHETIC] WP6A Brand' });
  const product = await api('post', 'products', {
    brand_id: brand.id,
    name: '[QA SYNTHETIC] WP6A Product',
    description: 'Synthetic local QA description, not real provider evidence.',
    product_type: 'physical',
    price_amount: '150.25',
    price_currency: 'INR',
  });
  await api('post', `products/${product.id}/activate`, {});
  const board = await api('post', 'ai/video/storyboards', {
    brand_id: brand.id,
    product_id: product.id,
    scenes: [
      {
        stable_key: 'qa-scene',
        scene_order: 1,
        scene_text: '[QA SYNTHETIC] Original storyboard scene',
        duration_seconds: 3,
      },
    ],
  });
  report.ids = { brand: brand.id, product: product.id, storyboard: board.id };
  await check(
    'Canonical synthetic storyboard fixture can be edited with keyboard, saved and reopened without approval',
    async () => {
      await p.goto(s.origin + '/ai/video');
      await p.getByRole('button', { name: 'Open editor', exact: true }).click();
      const editor = p.locator('[aria-labelledby="storyboard-editor-title"]');
      await expect(editor).toBeVisible();
      await editor
        .getByLabel('On-screen text', { exact: true })
        .fill('[QA SYNTHETIC] WP6A desktop edited scene');
      const saved = p.waitForResponse(
        (r) =>
          r.request().method() === 'PUT' &&
          r.url().endsWith('/storyboards/' + board.id) &&
          r.status() === 200,
      );
      await editor.getByRole('button', { name: 'Save', exact: true }).focus();
      await p.keyboard.press('Enter');
      await saved;
      await p.reload();
      await p.getByRole('button', { name: 'Open editor', exact: true }).click();
      await expect(p.getByLabel('On-screen text', { exact: true })).toHaveValue(
        '[QA SYNTHETIC] WP6A desktop edited scene',
      );
      const rows = await api('get', 'ai/video/storyboards');
      expect(rows.find((r) => r.id === board.id).state).toBe('draft');
      await capture(d, 'saved-storyboard-not-approved', true);
      await scan(d, 'saved-storyboard');
      await expect(p.getByRole('button', { name: 'Queue Video', exact: true })).toBeDisabled();
    },
  );
  await check(
    'Local Ads account UI validates missing fields, persists disabled/unverified identity and survives reload',
    async () => {
      await p.goto(s.origin + '/ads/accounts');
      await p.getByRole('button', { name: 'Add account', exact: true }).click();
      const before = d.signals.network.filter(
        (n) => n.method === 'POST' && n.path === '/api/v1/ads/accounts',
      ).length;
      await p.getByRole('button', { name: 'Save account', exact: true }).click();
      expect(await p.locator('[name=display_name]').evaluate((e) => e.validity.valid)).toBe(false);
      expect(
        d.signals.network.filter((n) => n.method === 'POST' && n.path === '/api/v1/ads/accounts')
          .length,
      ).toBe(before);
      await p.locator('[name=display_name]').fill('[QA SYNTHETIC] WP6A local account');
      await p.locator('[name=external_account_id]').fill('qa-wp6a-browser');
      const created = p.waitForResponse(
        (r) =>
          r.request().method() === 'POST' &&
          r.url().endsWith('/ads/accounts') &&
          r.status() === 201,
      );
      await p.getByRole('button', { name: 'Save account', exact: true }).click();
      const account = await (await created).json();
      report.ids.account = account.id;
      expect(account.enabled).toBe(false);
      expect(account.validated).toBe(false);
      await p.reload();
      const row = p.getByRole('row').filter({ hasText: 'qa-wp6a-browser' });
      await expect(row).toContainText('disabled');
      p.once('dialog', (dialog) => dialog.dismiss());
      await row.getByRole('button', { name: 'Enable', exact: true }).click();
      expect((await api('get', 'ads/accounts/' + account.id)).enabled).toBe(false);
      await capture(d, 'local-account-disabled-provenance', true);
      await scan(d, 'local-account');
    },
  );
  await check(
    'Unvalidated local account cannot become eligible campaign context; explicit HUMAN confirm stays disabled',
    async () => {
      await p.goto(s.origin + '/ads/create');
      await expect(
        p.locator('[name=account_id] option[value="' + report.ids.account + '"]'),
      ).toHaveCount(0);
      await p.locator('[name=name]').fill('[QA SYNTHETIC] WP6A blocked campaign');
      for (let i = 0; i < 11; i++)
        await p.getByRole('button', { name: 'Next', exact: true }).click();
      await expect(
        p.getByRole('button', { name: 'Confirm and queue campaign', exact: true }),
      ).toBeDisabled();
      expect(await api('get', 'ads/campaigns')).toEqual([]);
      await capture(d, 'missing-prerequisites-human-confirm-disabled', true);
      await scan(d, 'human-confirm-disabled');
    },
  );
  await check(
    'Video and Ads read outage/retry clear prior unavailable states without fake successful output',
    async () => {
      for (const [route, endpoint] of [
        ['/ai/video', '/api/v1/ai/video/generations'],
        ['/ads', '/api/v1/ads/overview'],
      ]) {
        d.signals.expected_http_errors ??= [];
        d.signals.expected_http_errors.push({ path: endpoint, status: 503 });
        await p.route('**' + endpoint, (r) =>
          r.fulfill({
            status: 503,
            contentType: 'application/json',
            body: '{"detail":"Synthetic QA read outage"}',
          }),
        );
        await p.goto(s.origin + route);
        await expect(p.locator('main')).toContainText('unavailable');
        await capture(d, 'read-outage-' + route.replaceAll('/', '-'));
        await p.unroute('**' + endpoint);
        const refresh =
          route === '/ai/video'
            ? p.getByRole('button', { name: 'Retry', exact: true })
            : p.getByRole('button', { name: 'Refresh', exact: true }).first();
        await refresh.click();
        await expect(p.locator('main')).not.toContainText('data is unavailable');
        await scan(d, 'read-recovery-' + route);
      }
    },
  );
  const m = await start(chrome, s, { width: 390, height: 844 }, 'mobile');
  runs.push(m);
  await login(m);
  await check(
    'Chrome mobile reopens persisted storyboard and local account, with visible focus and bounded table scrolling',
    async () => {
      await m.page.goto(s.origin + '/ai/video');
      await m.page.getByRole('button', { name: 'Open editor', exact: true }).click();
      await expect(m.page.getByLabel('On-screen text', { exact: true })).toHaveValue(
        '[QA SYNTHETIC] WP6A desktop edited scene',
      );
      const table = m.page.getByRole('region', { name: 'Video generation history' });
      await table.focus();
      await m.page.keyboard.press('ArrowRight');
      await capture(m, 'mobile-persisted-storyboard', true);
      await scan(m, 'mobile-storyboard');
      await m.page.goto(s.origin + '/ads/accounts');
      await expect(m.page.getByRole('row').filter({ hasText: 'qa-wp6a-browser' })).toBeVisible();
      await m.page.reload();
      await capture(m, 'mobile-local-account', true);
      await scan(m, 'mobile-account');
    },
  );
  edge = await chromium.launch({ channel: 'msedge', headless: true });
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
  ]) {
    const e = await start(edge, s, viewport, 'wp6a-edge-' + viewport.width);
    runs.push(e);
    await login(e);
    await check(
      `Edge ${viewport.width} authenticated routes, persisted edit, reload and external-provider limitations`,
      async () => {
        for (const route of [
          '/ai/video',
          '/social',
          '/ads',
          '/ads/accounts',
          '/ads/campaigns',
          '/ads/optimization',
          '/ads/marketing',
          '/ads/settings',
        ])
          await routeReview(e, route);
        await e.page.goto(s.origin + '/ai/video');
        await e.page.getByRole('button', { name: 'Open editor', exact: true }).click();
        await expect(e.page.getByLabel('On-screen text', { exact: true })).toHaveValue(
          '[QA SYNTHETIC] WP6A desktop edited scene',
        );
        await e.page.reload();
        await expect(
          e.page.getByRole('heading', { name: 'AI video studio', exact: true }),
        ).toBeVisible();
        await e.page.goto(s.origin + '/ads/settings');
        await expect(e.page.locator('main')).toContainText('Local synthetic connectors only');
      },
    );
  }
  await check(
    'No unexpected console/page/server/guard errors or external execution in accepted browser contexts',
    async () => {
      for (const run of runs)
        expect(wp3UnexpectedSignals(run.signals)).toEqual({
          console_errors: [],
          page_errors: [],
          failed_requests: [],
          denied_requests: [],
          server_errors: [],
        });
      expect(await api('get', 'ads/campaigns')).toEqual([]);
      expect(await api('get', 'ai/video/generations')).toEqual([]);
    },
  );
  report.status = 'COMPLETE';
} catch (e) {
  report.status = 'FAILED';
  report.error = e.message.slice(0, 1500);
  for (const r of runs) await capture(r, 'failure').catch(() => {});
} finally {
  for (const r of runs) await finish(r);
  await chrome.close();
  if (edge) await edge.close();
  await persist();
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP6A complete');
  console.log(
    JSON.stringify({
      token: s.token,
      status: report.status,
      checks: report.checks,
      scans: report.scans.length,
      error: report.error,
    }),
  );
}
process.exitCode = report.status === 'COMPLETE' ? 0 : 1;
