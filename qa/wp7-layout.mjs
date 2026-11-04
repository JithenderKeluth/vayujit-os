// Focused before/after proof for WP7-discovered responsive defects.
import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Owner, wp3Api } from './wp3-fixtures.mjs';
import { measure } from './wp6b-accessibility.mjs';
const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8')),
  before = process.argv.includes('--before');
const w = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (
  !s.synthetic ||
  s.schema !== 'ALEMBIC_HEAD' ||
  s.status !== 'READY' ||
  !w.disposable ||
  w.token !== s.token
)
  throw Error('OWNED_DISPOSABLE_REQUIRED');
const result = { token: s.token, before, checks: [], scans: [], manual: [], keyboard: [] },
  runs = [],
  browsers = [];
try {
  for (const channel of ['chrome', 'msedge']) {
    const b = await chromium.launch({ channel, headless: true });
    browsers.push(b);
    for (const width of [390, 768, 1440]) {
      const r = await start(
        b,
        s,
        { width, height: 900 },
        `wp7-${before ? (process.argv.includes('--extra') ? 'before-extra' : 'before') : 'after'}-${channel}-${width}`,
      );
      runs.push(r);
      const p = r.page;
      const status = await p.request
        .get(s.origin + '/api/v1/auth/setup-status')
        .then((r) => r.json());
      if (!status.ownerExists) {
        await p.goto(s.origin + '/setup');
        await p.locator('#full-name').fill('[QA SYNTHETIC] WP7 layout');
        await p.locator('#email').fill(wp3Owner.email);
        await p.locator('#password').fill(wp3Owner.password);
        await p.locator('#confirmation').fill(wp3Owner.password);
        await p.getByRole('button', { name: 'Create owner', exact: true }).click();
      } else {
        await p.goto(s.origin + '/login');
        await p.locator('#email').fill(wp3Owner.email);
        await p.locator('#password').fill(wp3Owner.password);
        await p.getByRole('button', { name: 'Sign in', exact: true }).click();
      }
      await p.waitForURL('**/dashboard');
      if (!before && !result.fixture) {
        const api = wp3Api(p, s.origin);
        const brand = await api('post', 'brands', {
          name: '[QA SYNTHETIC] WP7 responsive long brand label',
        });
        const product = await api('post', 'products', {
          brand_id: brand.id,
          name: '[QA SYNTHETIC] WP7 long product label for responsive selection',
          product_type: 'physical',
        });
        result.fixture = { brand: brand.id, product: product.id, synthetic: true };
      }
      for (const route of process.argv.includes('--extra')
        ? ['/ai/generate', '/ai/history', '/publishing/jobs']
        : before
          ? ['/ads/recommendations', '/ads/optimization-rules', '/campaigns/new']
          : [
              '/ads/recommendations',
              '/ads/optimization-rules',
              '/campaigns/new',
              '/ai/generate',
              '/ai/history',
              '/publishing/jobs',
            ]) {
        await p.goto(s.origin + route);
        await expect(p.locator('main h1').first()).toBeVisible();
        await p.waitForLoadState('networkidle');
        const dimensions = await p.evaluate(() => ({
          viewport: innerWidth,
          document: document.documentElement.scrollWidth,
          overflow: [...document.querySelectorAll('main *')]
            .filter((e) => {
              const r = e.getBoundingClientRect();
              return r.width && r.right > innerWidth + 1;
            })
            .slice(0, 20)
            .map((e) => ({
              tag: e.tagName,
              class: e.className,
              type: e.getAttribute('type'),
              width: e.getBoundingClientRect().width,
              right: e.getBoundingClientRect().right,
            })),
        }));
        const snap = await capture(r, route, true),
          scan = await axe(r, route);
        result.scans.push({ context: r.label, ...scan });
        let keyboard = 'NOT_TESTED';
        if (
          !before &&
          [
            '/ads/recommendations',
            '/ads/optimization-rules',
            '/ai/history',
            '/publishing/jobs',
          ].includes(route)
        ) {
          const name = {
            '/ads/recommendations': 'Optimization recommendations table',
            '/ads/optimization-rules': 'Optimization rules table',
            '/ai/history': 'AI generation history table',
            '/publishing/jobs': 'Publishing jobs table',
          }[route];
          const region = p.getByRole('region', { name, exact: true });
          await region.focus();
          await expect(region).toBeFocused();
          await p.keyboard.press('ArrowRight');
          keyboard = 'PASS';
          for (const position of [0, -1]) {
            const headers = region.locator('th');
            result.manual.push(
              await measure(
                r,
                position === 0 ? headers.first() : headers.last(),
                'table-header-' + route.replaceAll('/', '-') + position,
              ),
            );
          }
          result.keyboard.push({
            context: r.label,
            route,
            region_name: name,
            focused: true,
            horizontal_key: 'ArrowRight',
            accessible_tree: await region.ariaSnapshot(),
          });
        }
        result.checks.push({
          context: r.label,
          route,
          ...dimensions,
          screenshot: snap.screenshot,
          keyboard,
          status: dimensions.document <= width + 1 && !scan.violations.length ? 'PASS' : 'FAIL',
        });
      }
      if (!before && width < 1024) {
        const menu = p.locator('details.mobile-menu');
        if (await menu.isVisible()) {
          const summary = menu.locator(':scope > summary');
          await summary.focus();
          await p.keyboard.press('Enter');
          await expect(menu).toHaveAttribute('open', '');
          await p.keyboard.press('Escape');
          await expect(menu).not.toHaveAttribute('open', '');
          await expect(summary).toBeFocused();
          result.keyboard.push({
            context: r.label,
            scope: 'Application menu direct summary',
            enter_escape_focus: 'PASS',
          });
        }
      }
    }
  }
} finally {
  for (const r of runs) await finish(r);
  for (const b of browsers) await b.close();
  await fs.writeFile(
    path.join(
      s.folder,
      before
        ? process.argv.includes('--extra')
          ? 'wp7-layout-extra-before.json'
          : 'wp7-layout-before.json'
        : 'wp7-layout-after.json',
    ),
    JSON.stringify(result, null, 2),
  );
  if (!before)
    await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP7 layout retest complete');
  console.log(
    JSON.stringify({
      token: s.token,
      before,
      checks: result.checks.map((c) => ({
        context: c.context,
        route: c.route,
        status: c.status,
        document: c.document,
        viewport: c.viewport,
      })),
    }),
  );
}
process.exitCode =
  before || (result.checks.length === 36 && result.checks.every((c) => c.status === 'PASS'))
    ? 0
    : 1;
