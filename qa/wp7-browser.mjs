// Whole-surface review supplements (does not replace) persisted seller assertions.
import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect as baseExpect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Owner, wp3Product } from './wp3-fixtures.mjs';
import { wp5Operations } from './wp5-fixtures.mjs';
import { measure } from './wp6b-accessibility.mjs';
const expect = baseExpect.configure({ timeout: 20000 });
const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const witness = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (
  !s.synthetic ||
  s.schema !== 'ALEMBIC_HEAD' ||
  s.status !== 'READY' ||
  !witness.disposable ||
  witness.token !== s.token
)
  throw Error('APPROVED_QA_REQUIRED');
const inv = JSON.parse(await fs.readFile('tmp/qa-wp7/inventory.json', 'utf8'));
const report = {
  token: s.token,
  package: 'WP7',
  synthetic: true,
  status: 'RUNNING',
  checks: [],
  routes: [],
  scans: [],
  manual: [],
  versions: {},
  not_tested: [],
};
const runs = [],
  browsers = [];
const persist = () =>
  fs.writeFile(path.join(s.folder, 'wp7-surface.json'), JSON.stringify(report, null, 2));
async function check(name, fn) {
  try {
    await fn();
    report.checks.push({ name, status: 'PASS' });
  } catch (e) {
    report.checks.push({ name, status: 'FAIL', error: e.message.slice(0, 1000) });
  }
  await persist();
}
async function scan(r, state) {
  const a = await axe(r, state);
  report.scans.push({ context: r.label, ...a });
  return a;
}
async function login(r) {
  await r.page.goto(s.origin + '/login');
  await r.page.locator('#email').fill(wp3Owner.email);
  await r.page.locator('#password').fill(wp3Owner.password);
  await r.page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await r.page.waitForURL('**/dashboard');
}
async function review(r, row) {
  const n = r.signals.network.length,
    ce = r.signals.console_errors.length,
    pe = r.signals.page_errors.length;
  const out = {
    context: r.label,
    declared_route: row.route,
    url: row.url || row.route,
    status: 'NOT_TESTED',
    feature_execution: 'NOT_TESTED',
    positive: 'READ_ONLY_ROUTE_REVIEW',
    negative: 'NOT_TESTED',
    persistence: 'NOT_TESTED',
    authorization: 'AUTHENTICATED',
    safety: 'NETWORK_GUARDED',
  };
  try {
    await r.page.goto(s.origin + out.url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await r.page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
    await expect(r.page.locator('main').first()).toBeVisible();
    const snap = await capture(r, 'route-' + row.route, true),
      a = await scan(r, row.route);
    out.actual_path = new URL(r.page.url()).pathname;
    out.screenshot = snap.screenshot;
    out.headings = snap.headings;
    out.layout = snap.layout;
    out.document_fits = await r.page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    );
    out.network = r.signals.network.slice(n);
    out.console_errors = r.signals.console_errors.slice(ce);
    out.page_errors = r.signals.page_errors.slice(pe);
    out.axe_violations = a.violations.length;
    out.axe_incomplete = a.incomplete.length;
    const expectedPath = out.url.split('?')[0].split('#')[0];
    out.status =
      out.actual_path === expectedPath &&
      out.document_fits &&
      !out.page_errors.length &&
      !out.network.some((n) => n.status >= 500) &&
      !a.violations.length
        ? 'PASS'
        : 'FAIL';
    out.scope = 'RENDER_READ_RESPONSIVE_AXE_ONLY_NOT_COMPLETE_FEATURE';
  } catch (e) {
    out.status = 'FAIL';
    out.error = e.message.slice(0, 800);
    await capture(r, 'failed-' + row.route).catch(() => {});
  }
  report.routes.push(out);
  await persist();
}
try {
  const chrome = await chromium.launch({ channel: 'chrome', headless: true }),
    edge = await chromium.launch({ channel: 'msedge', headless: true });
  browsers.push(chrome, edge);
  report.versions = { chrome: chrome.version(), edge: edge.version() };
  const d = await start(chrome, s, { width: 1440, height: 900 }, 'wp7-chrome-1440');
  runs.push(d);
  const p = d.page;
  await check('A/M first-owner validation, canonical setup and second-owner refusal', async () => {
    await p.goto(s.origin + '/setup');
    await p.locator('#full-name').fill('[QA SYNTHETIC] WP7 Seller');
    await p.locator('#email').fill(wp3Owner.email);
    await p.locator('#password').fill(wp3Owner.password);
    await p.locator('#confirmation').fill('MismatchOnly123!');
    await p.getByRole('button', { name: 'Create owner', exact: true }).click();
    await expect(p).toHaveURL(/\/setup/);
    await capture(d, 'owner-mismatch', true);
    await scan(d, 'owner-mismatch');
    await p.locator('#confirmation').fill(wp3Owner.password);
    await p.getByRole('button', { name: 'Create owner', exact: true }).click();
    await p.waitForURL('**/dashboard');
    const second = await p.request.post(s.origin + '/api/v1/auth/setup-owner', {
      data: {
        email: 'second-qa@example.com',
        full_name: '[QA SYNTHETIC] second',
        password: wp3Owner.password,
        password_confirmation: wp3Owner.password,
      },
    });
    expect(second.status()).toBe(409);
  });
  const { api, brand, op, goal } = await wp3Product(p, s.origin),
    ops = await wp5Operations(api, brand);
  report.ids = { brand: brand.id, opportunity: op.id, goal: goal.id, product: ops.product.id };
  const dynamic = [
    ['/brands/:id', `/brands/${brand.id}`],
    ['/brands/:id/edit', `/brands/${brand.id}/edit`],
    ['/catalog/:id', `/catalog/${ops.product.id}`],
    ['/products/:id', `/products/${ops.product.id}`],
    ['/products/:id/edit', `/products/${ops.product.id}/edit`],
    ['/products/:id/channels', `/products/${ops.product.id}/channels`],
    ['/products/:id/media', `/products/${ops.product.id}/media`],
    [
      '/intelligence/product-opportunities/:opportunityId',
      `/intelligence/product-opportunities/${op.id}?goal_id=${goal.id}`,
    ],
    ['/settings/:section', '/settings/security'],
  ].map(([route, url]) => ({ route, url }));
  const statics = inv.routes.filter(
    (r) =>
      r.kind === 'PAGE' && !r.route.includes(':') && !['/setup', '/login', '/**'].includes(r.route),
  );
  const all = [...statics, ...dynamic];
  for (const row of all) await review(d, row);
  const mobile = await start(edge, s, { width: 390, height: 844 }, 'wp7-edge-390');
  runs.push(mobile);
  await login(mobile);
  for (const row of all) await review(mobile, row);
  const critical = [
    '/dashboard',
    '/intelligence/business-agent',
    '/intelligence/research',
    '/intelligence/product-opportunities',
    '/catalog',
    '/intelligence/cross-marketplace',
    '/intelligence/sourcing',
    '/intelligence/sourcing-economics',
    '/intelligence/due-diligence',
    '/intelligence/supplier-shortlisting',
    '/marketplaces',
    '/marketplaces/inventory',
    '/marketplaces/orders',
    '/marketplaces/financials',
    '/operations/action-center',
    '/operations/launch-readiness',
    '/ai/video',
    '/ads',
    '/ads/optimization',
  ];
  for (const [browser, label, width] of [
    [chrome, 'wp7-chrome-390', 390],
    [edge, 'wp7-edge-1440', 1440],
    [chrome, 'wp7-chrome-768', 768],
  ]) {
    const r = await start(browser, s, { width, height: width === 390 ? 844 : 900 }, label);
    runs.push(r);
    await login(r);
    for (const row of all.filter((x) => critical.includes(x.route))) await review(r, row);
    await check(
      label + ' M keyboard menu, refresh and browser history preserve exact owned product',
      async () => {
        await r.page.goto(s.origin + `/catalog/${ops.product.id}`);
        await expect(r.page.locator('main')).toContainText(ops.product.name);
        await r.page.goto(s.origin + '/marketplaces/inventory');
        await r.page.goBack();
        await expect(r.page).toHaveURL(new RegExp('/catalog/' + ops.product.id));
        await expect(r.page.locator('main')).toContainText(ops.product.name);
        await r.page.goForward();
        await expect(r.page).toHaveURL(/\/marketplaces\/inventory/);
        await r.page.reload();
        await expect(r.page.locator('main h1').first()).toBeVisible();
        if (width < 1024) {
          const menu = r.page.locator('details.mobile-menu');
          if (await menu.isVisible()) {
            await menu.locator(':scope > summary').focus();
            await r.page.keyboard.press('Enter');
            await expect(menu).toHaveAttribute('open', '');
            await r.page.keyboard.press('Escape');
            await expect(menu).not.toHaveAttribute('open', '');
            await expect(menu.locator(':scope > summary')).toBeFocused();
          }
        }
        await capture(r, 'keyboard-history-reload', true);
      },
    );
    await r.page.goto(s.origin + '/ai/video');
    await expect(r.page.getByRole('group', { name: 'Quick actions', exact: true })).toBeVisible();
    report.manual.push(
      await measure(
        r,
        r.page.getByRole('group', { name: 'Quick actions', exact: true }),
        'quick-actions',
      ),
    );
    await r.page.evaluate(() => (document.documentElement.style.fontSize = '200%'));
    await capture(r, 'video-200-percent-text', true);
    await scan(r, 'video-200-percent-text');
  }
  await check(
    'M expired/cleared session denies protected API; sign-in retains authorized deep link',
    async () => {
      await d.context.clearCookies();
      const protectedRead = await p.request.get(s.origin + '/api/v1/financial/summary');
      expect(protectedRead.status()).toBe(401);
      await p.goto(s.origin + `/catalog/${ops.product.id}`);
      await p.waitForURL('**/login**');
      await p.locator('#email').fill(wp3Owner.email);
      await p.locator('#password').fill(wp3Owner.password);
      await p.getByRole('button', { name: 'Sign in', exact: true }).click();
      await p.waitForURL('**/catalog/' + ops.product.id);
      await p.reload();
      await expect(p.locator('main')).toContainText(ops.product.name);
      await capture(d, 'session-recovery-deeplink', true);
    },
  );
  await check(
    'Invalid same-owner context is not silently replaced by another product',
    async () => {
      await p.goto(s.origin + '/catalog/00000000-0000-0000-0000-000000000099');
      await expect(p.locator('main')).not.toContainText(ops.product.name);
      await capture(d, 'invalid-product', true);
      await scan(d, 'invalid-product');
    },
  );
  report.not_tested = inv.routes
    .filter(
      (r) =>
        r.kind === 'PAGE' && r.route.includes(':') && !dynamic.some((d) => d.route === r.route),
    )
    .map((r) => ({
      route: r.route,
      status: 'BLOCKED',
      reason:
        'NO_LEGITIMATE_PERSISTED_ARTIFACT_PREPARED; NOT_COUNTED_AS_SUCCESSFUL_DETAIL_COVERAGE',
    }));
  report.status =
    report.routes.some((r) => r.status === 'FAIL') || report.checks.some((c) => c.status === 'FAIL')
      ? 'FAILED'
      : 'COMPLETE';
} catch (e) {
  report.status = 'BLOCKED';
  report.safe_error = e.message.slice(0, 1000);
  for (const r of runs) await capture(r, 'surface-blocker').catch(() => {});
} finally {
  for (const r of runs) await finish(r);
  for (const b of browsers) await b.close();
  await persist();
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP7 surface complete');
  console.log(
    JSON.stringify({
      token: s.token,
      status: report.status,
      routes: report.routes.length,
      checks: report.checks,
      scans: report.scans.length,
    }),
  );
}
process.exitCode = report.status === 'COMPLETE' ? 0 : 1;
