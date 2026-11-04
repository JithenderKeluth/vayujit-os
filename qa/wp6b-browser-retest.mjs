import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect as baseExpect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Api, wp3Owner } from './wp3-fixtures.mjs';
import { wp5Operations } from './wp5-fixtures.mjs';
import { wp3UnexpectedSignals } from './wp3-reporting.mjs';
import { measure } from './wp6b-accessibility.mjs';
const expect = baseExpect.configure({ timeout: 20000 });
const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8')),
  before = process.argv.includes('--before'),
  social = process.argv.includes('--social');
const witness = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (
  s.qa_phase !== 'WP6B' ||
  s.status !== 'READY' ||
  s.schema !== 'ALEMBIC_HEAD' ||
  !s.synthetic ||
  !witness.disposable ||
  witness.token !== s.token
)
  throw Error('APPROVED_QA_REQUIRED');
const report = {
    token: s.token,
    before,
    status: 'RUNNING',
    checks: [],
    scans: [],
    manual: [],
    ads_requests: [],
  },
  runs = [];
let chrome, edge;
async function check(name, fn) {
  try {
    await fn();
    report.checks.push({ name, status: 'PASS' });
  } catch (e) {
    report.checks.push({ name, status: 'FAIL', error: e.message.slice(0, 1500) });
    throw e;
  }
}
async function scan(run, name) {
  const v = await axe(run, name);
  report.scans.push({ context: run.label, ...v });
  expect(v.violations).toEqual([]);
}
async function login(r) {
  await r.page.goto(s.origin + '/login');
  await r.page.locator('#email').fill(wp3Owner.email);
  await r.page.locator('#password').fill(wp3Owner.password);
  await r.page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await r.page.waitForURL('**/dashboard');
}
async function review(r, route) {
  await r.page.goto(s.origin + route);
  await expect(r.page.locator('main h1').first()).toBeVisible();
  await capture(r, route.replaceAll('/', '-'), true);
  await scan(r, route);
  expect(await r.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
    true,
  );
}
try {
  chrome = await chromium.launch({ channel: 'chrome', headless: true });
  const d = await start(chrome, s, { width: 1440, height: 900 }, 'wp6b-desktop');
  runs.push(d);
  const p = d.page;
  await p.goto(s.origin + '/setup');
  await p.locator('#full-name').fill('[QA SYNTHETIC] WP6B Owner');
  await p.locator('#email').fill(wp3Owner.email);
  await p.locator('#password').fill(wp3Owner.password);
  await p.locator('#confirmation').fill(wp3Owner.password);
  await p.getByRole('button', { name: 'Create owner', exact: true }).click();
  await p.waitForURL('**/dashboard');
  const api = wp3Api(p, s.origin);
  await check('Empty Video, Ads and Finance render honest unknown/empty states', async () => {
    for (const route of ['/ai/video', '/ads', '/ads/optimization', '/marketplaces/financials'])
      await review(d, route);
  });
  if (before) {
    await p.goto(s.origin + '/ai/video');
    await expect(p.getByRole('heading', { name: 'AI video studio', exact: true })).toBeVisible();
    await expect(p.locator('textarea[aria-label="Caption text"]').first()).toBeVisible();
    for (const [i, e] of (await p.locator('textarea[aria-label="Caption text"]').all()).entries())
      report.manual.push(await measure(d, e, 'caption-before-' + i));
  } else if (social) {
    edge = await chromium.launch({ channel: 'msedge', headless: true });
    for (const [browser, label, width] of [
      [chrome, 'mobile', 390],
      [edge, 'wp6b-edge-1440', 1440],
      [edge, 'wp6b-edge-390', 390],
    ]) {
      const r = await start(browser, s, { width, height: width === 390 ? 844 : 900 }, label);
      runs.push(r);
      await login(r);
      await check(
        label + ' original Social empty table semantics, contrast and horizontal keyboard access',
        async () => {
          await review(r, '/social');
          const table = r.page.getByRole('region', {
            name: 'Recent Video posts table',
            exact: true,
          });
          await expect(table.locator('th[scope="col"]')).toHaveCount(4);
          await expect(table.locator('tbody tr')).toHaveCount(0);
          await expect(
            r.page.getByText('No Video posts yet. Start with Compose.', { exact: true }),
          ).toBeVisible();
          report.social_semantics ??= [];
          report.social_semantics.push({
            context: r.label,
            headers: await table.locator('th').allTextContents(),
            accessible_snapshot: await table.ariaSnapshot(),
            classification: 'HONEST_EMPTY_TABLE_POPULATED_STATE_NOT_CERTIFIED',
          });
          for (const i of [2, 3])
            report.manual.push(await measure(r, table.locator('th').nth(i), 'social-header-' + i));
          await table.focus();
          await r.page.keyboard.press('ArrowRight');
          await capture(r, 'social-table-focus');
          await scan(r, 'social-table-exposed');
          await r.page.goto(s.origin + '/ai/video');
          const emptyVideo = r.page.locator(
            '[aria-label="Video generation history"] td[colspan="8"]',
          );
          await expect(emptyVideo).toBeVisible();
          report.manual.push(await measure(r, emptyVideo, 'video-original-empty-cell'));
          expect(wp3UnexpectedSignals(r.signals)).toEqual({
            console_errors: [],
            page_errors: [],
            failed_requests: [],
            denied_requests: [],
            server_errors: [],
          });
        },
      );
    }
  } else {
    const brand = await api('post', 'brands', { name: '[QA SYNTHETIC] WP6B Brand' }),
      ops = await wp5Operations(api, brand);
    const board = await api('post', 'ai/video/storyboards', {
      brand_id: brand.id,
      product_id: ops.product.id,
      scenes: [{ stable_key: 'wp6b', scene_order: 1, scene_text: '[QA SYNTHETIC] WP6B scene' }],
    });
    report.ids = { product: ops.product.id, board: board.id };
    await check(
      'Financial decimals, UNKNOWN inputs and same-scope reload remain canonical and synthetic',
      async () => {
        const unknown = await api('get', 'financial/summary');
        expect(unknown.estimated_profit).toBeNull();
        expect(unknown.provenance_status).toBe('SYNTHETIC');
        await p.goto(s.origin + '/marketplaces/financials');
        await expect(p.locator('main')).toContainText('UNKNOWN');
        await expect(p.locator('main')).toContainText('not an accounting ledger');
        await api('post', 'financial/costs', {
          cost_key: 'wp6b-known-cost',
          product_id: ops.product.id,
          marketplace: 'flipkart',
          cost_type: 'product_cost',
          amount: '10.05',
          currency: 'INR',
          evidence_status: 'reported',
          source_type: 'synthetic_fixture',
        });
        const value = await api('get', 'financial/summary');
        expect(value.estimated_profit).toBe('170.15');
        const a = await api('post', 'financial/calculations/recalculate', {}),
          b = await api('post', 'financial/calculations/recalculate', {});
        expect(a.id).toBe(b.id);
        await p.reload();
        await expect(p.locator('main')).toContainText('170.15');
        await scan(d, 'finance-known');
        await p.goto(s.origin + '/marketplaces/orders');
        await p.getByRole('button', { name: 'View details', exact: true }).first().click();
        await expect(p.locator('main')).toContainText('rounded');
        await capture(d, 'order-rounding-basis', true);
        await scan(d, 'orders-rounding');
      },
    );
    await check(
      'Real Ads comparison repeated navigation/read and reload has classified request evidence',
      async () => {
        for (let i = 0; i < 8; i++) {
          await p.goto(s.origin + '/ads/optimization');
          await expect(p.locator('main h1').first()).toBeVisible();
          for (const endpoint of [
            'ads/comparison',
            'ads/overview',
            'ads/optimization/overview',
            'ads/anomalies',
          ]) {
            const r = await p.request.get(s.origin + '/api/v1/' + endpoint);
            report.ads_requests.push({ path: endpoint, status: r.status(), attempt: i + 1 });
            expect(r.status()).toBe(200);
          }
        }
        await p.reload();
        await capture(d, 'ads-repeated-reads', true);
        await scan(d, 'ads-after-reload');
      },
    );
    await check('Exact Ads read failure is recoverable without approval or execution', async () => {
      let fail = true;
      await d.context.route('**/api/v1/ads/overview', (r) =>
        fail
          ? r.fulfill({
              status: 503,
              contentType: 'application/json',
              body: JSON.stringify({ detail: 'Synthetic read outage' }),
            })
          : r.continue(),
      );
      d.signals.expected_http_errors = [{ path: '/api/v1/ads/overview', status: 503 }];
      await p.goto(s.origin + '/ads');
      await expect(p.locator('main')).toContainText('unavailable');
      await capture(d, 'ads-read-outage');
      fail = false;
      await p.getByRole('button', { name: 'Refresh', exact: true }).click();
      await expect(p.locator('main')).not.toContainText('Ads data is unavailable');
      expect(await api('get', 'ads/campaigns')).toEqual([]);
      expect(await api('get', 'ai/video/generations')).toEqual([]);
    });
    edge = await chromium.launch({ channel: 'msedge', headless: true });
    for (const [browser, label, width] of [
      [chrome, 'mobile', 390],
      [edge, 'wp6b-edge-1440', 1440],
      [edge, 'wp6b-edge-390', 390],
    ]) {
      const r = await start(browser, s, { width, height: width === 390 ? 844 : 900 }, label);
      runs.push(r);
      await login(r);
      await check(
        label + ' affected routes, manual nodes, keyboard and persisted values',
        async () => {
          for (const route of [
            '/ai/video',
            '/social',
            '/ads',
            '/ads/optimization',
            '/marketplaces/orders',
            '/marketplaces/financials',
          ])
            await review(r, route);
          await r.page.goto(s.origin + '/ai/video');
          await expect(
            r.page.getByRole('group', { name: 'Quick actions', exact: true }),
          ).toBeVisible();
          await r.page.getByRole('button', { name: 'Open editor', exact: true }).click();
          for (const label of ['On-screen text', 'Narration']) {
            const l = r.page.getByLabel(label, { exact: true });
            await l.focus();
            report.manual.push(await measure(r, l, label));
          }
          const caption = r.page.getByLabel('Caption text', { exact: true });
          await caption.fill('[QA SYNTHETIC] local inert caption draft');
          await caption.focus();
          report.manual.push(await measure(r, caption, 'caption-after'));
          await r.page.keyboard.press('Tab');
          expect(await r.page.evaluate(() => document.activeElement !== document.body)).toBe(true);
          await r.page.keyboard.press('Shift+Tab');
          await expect(caption).toBeFocused();
          const table = r.page.getByRole('region', { name: 'Video generation history' });
          await table.focus();
          await r.page.keyboard.press('ArrowRight');
          await capture(r, 'history-table-keyboard');
          const quick = r.page.getByRole('group', { name: 'Quick actions', exact: true });
          report.manual.push(await measure(r, quick, 'quick-group'));
          report.manual.push(
            await measure(r, quick.getByRole('link').first(), 'quick-action-target'),
          );
          const historyHeaders = r.page.locator('[aria-label="Video generation history"] th');
          for (const i of [2, 3])
            report.manual.push(await measure(r, historyHeaders.nth(i), 'video-header-' + i));
          await historyHeaders
            .nth(2)
            .evaluate((e) => e.scrollIntoView({ block: 'center', inline: 'center' }));
          report.touch_targets ??= [];
          report.touch_targets.push({
            context: r.label,
            ...(await r.page.evaluate(() => {
              const nodes = [
                ...document.querySelectorAll(
                  'main button,main a,main input,main select,main summary',
                ),
              ].filter((e) => {
                const r = e.getBoundingClientRect();
                return r.width && r.height;
              });
              const small = nodes
                .map((e) => {
                  const r = e.getBoundingClientRect();
                  return {
                    tag: e.tagName,
                    name: (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 80),
                    width: r.width,
                    height: r.height,
                    disabled: e.disabled === true,
                  };
                })
                .filter((e) => e.width < 24 || e.height < 24);
              return {
                visible_controls: nodes.length,
                below_24px: small,
                status: small.length
                  ? 'SPACING_OR_EXCEPTION_MANUAL_REVIEW'
                  : 'MEASURED_DIMENSIONS_PASS',
              };
            })),
          });
          if (width === 390) {
            const menu = r.page.locator('details.mobile-menu');
            await menu.locator('summary').first().focus();
            await r.page.keyboard.press('Enter');
            await expect(menu).toHaveAttribute('open', '');
            await r.page.keyboard.press('Escape');
            await expect(menu).not.toHaveAttribute('open', '');
            await expect(menu.locator('summary').first()).toBeFocused();
          }
          await r.page.goto(s.origin + '/marketplaces/financials');
          await expect(r.page.locator('main')).toContainText('170.15');
          await r.page.reload();
          await expect(r.page.locator('main')).toContainText('170.15');
          const financialTables = r.page.locator('main table');
          if (await financialTables.count()) {
            for (const i of [2, 3]) {
              const header = financialTables.first().locator('th').nth(i);
              if (await header.count())
                report.manual.push(await measure(r, header, 'finance-header-' + i));
            }
            const cell = financialTables.first().locator('td').first();
            if (await cell.count()) report.manual.push(await measure(r, cell, 'finance-cell'));
          }
          await r.page.goto(s.origin + '/ai/video');
          await expect(
            r.page.getByRole('heading', { name: 'AI video studio', exact: true }),
          ).toBeVisible();
          await r.page.evaluate(() => (document.documentElement.style.fontSize = '200%'));
          expect(
            await r.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
          ).toBe(true);
          await capture(r, 'video-text-resize-200');
          await scan(r, 'video-text-resize');
        },
      );
    }
    await check(
      'No unexpected console/network/security errors or queued consequential actions',
      async () => {
        for (const r of runs)
          expect(wp3UnexpectedSignals(r.signals)).toEqual({
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
  }
  report.status = 'COMPLETE';
} catch (e) {
  report.status = 'FAILED';
  report.error = e.message.slice(0, 1500);
  for (const r of runs) await capture(r, 'failure').catch(() => {});
} finally {
  for (const r of runs) await finish(r);
  if (chrome) await chrome.close();
  if (edge) await edge.close();
  await fs.writeFile(
    path.join(
      s.folder,
      before ? 'wp6b-before.json' : social ? 'wp6b-social-review.json' : 'wp6b-retest.json',
    ),
    JSON.stringify(report, null, 2),
  );
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP6B done');
  console.log(
    JSON.stringify({
      token: s.token,
      status: report.status,
      checks: report.checks,
      manual: report.manual,
      scans: report.scans.length,
      error: report.error,
    }),
  );
}
process.exitCode = report.status === 'COMPLETE' ? 0 : 1;
