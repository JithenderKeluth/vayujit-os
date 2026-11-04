import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect as baseExpect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Owner, wp3Product } from './wp3-fixtures.mjs';
import { wp5Operations } from './wp5-fixtures.mjs';
const expect = baseExpect.configure({ timeout: 20000 });
const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const witness = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (
  !s.synthetic ||
  s.status !== 'READY' ||
  s.schema !== 'ALEMBIC_HEAD' ||
  witness.token !== s.token ||
  !witness.disposable
)
  throw Error('APPROVED_QA_REQUIRED');
const chrome = await chromium.launch({ channel: 'chrome', headless: true });
const runs = [],
  report = {
    token: s.token,
    status: 'RUNNING',
    checks: [],
    review: [],
    manual_contrast: [],
    ids: {},
    synthetic: true,
  };
let edge;
const persist = () =>
  fs.writeFile(path.join(s.folder, 'wp6-retest.json'), JSON.stringify(report, null, 2));
async function check(name, fn) {
  try {
    await fn();
    report.checks.push({ name, status: 'PASS' });
  } catch (e) {
    report.checks.push({ name, status: 'FAIL', error: e.message.slice(0, 1400) });
    throw e;
  } finally {
    await persist();
  }
}
async function login(run, route) {
  await run.page.goto(s.origin + route);
  await run.page.waitForURL('**/login**');
  await run.page.locator('#email').fill(wp3Owner.email);
  await run.page.locator('#password').fill(wp3Owner.password);
  await run.page.getByRole('button', { name: 'Sign in', exact: true }).click();
}
async function contrast(run, loc, name) {
  if ((await loc.count()) !== 1) {
    report.manual_contrast.push({ context: run.label, name, status: 'NOT_UNIQUELY_AVAILABLE' });
    return;
  }
  await loc.evaluate((el) => el.scrollIntoView({ block: 'center', inline: 'center' }));
  await loc.focus();
  const value = await loc.evaluate((el) => {
    const style = getComputedStyle(el),
      rgb = (s) => s.match(/[\d.]+/g)?.map(Number);
    let current = el,
      bg;
    while (current) {
      const c = rgb(getComputedStyle(current).backgroundColor);
      if (c?.[3] === undefined || c[3] === 1) {
        bg = c;
        break;
      }
      current = current.parentElement;
    }
    const fg = rgb(style.color);
    const l = (c) =>
      c
        .slice(0, 3)
        .map((v) => {
          v /= 255;
          return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
        })
        .reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0);
    const ratio =
      fg && bg ? (Math.max(l(fg), l(bg)) + 0.05) / (Math.min(l(fg), l(bg)) + 0.05) : null;
    const rect = el.getBoundingClientRect(),
      hit = document.elementFromPoint(
        rect.left + rect.width / 2,
        rect.top + Math.min(rect.height / 2, 20),
      );
    return {
      foreground: style.color,
      background: bg,
      ratio,
      center_unobscured: hit === el || el.contains(hit),
      fontSize: style.fontSize,
      outline: style.outlineStyle,
    };
  });
  report.manual_contrast.push({
    context: run.label,
    name,
    ...value,
    status: value.ratio >= 4.5 && value.center_unobscured ? 'MEASURED_PASS' : 'REVIEW_REQUIRED',
  });
  await capture(run, 'manual-' + name);
}
async function review(run, route) {
  await run.page.goto(s.origin + route, { waitUntil: 'domcontentloaded' });
  await run.page
    .locator('main h1')
    .first()
    .waitFor({ state: 'visible', timeout: 15000 })
    .catch(() => {});
  const surface = await capture(run, route.split('?')[0].replaceAll('/', '-'));
  const scan = await axe(run, route);
  report.review.push({
    context: run.label,
    route,
    actual: new URL(run.page.url()).pathname,
    headings: surface.headings,
    layout: await run.page.evaluate(() => ({
      viewport: innerWidth,
      document: document.documentElement.scrollWidth,
    })),
    screenshot: surface.screenshot,
    violations: scan.violations,
    incomplete: scan.incomplete,
    visible_errors: await run.page.locator('main [role="alert"]').allTextContents(),
  });
  await persist();
}
const primary = [
  '/dashboard',
  '/intelligence/business-agent',
  '/operations/action-center',
  '/operations/launch-readiness',
  '/intelligence/product-opportunities',
  '/intelligence/research',
  '/intelligence/cross-marketplace',
  '/intelligence/sourcing',
  '/intelligence/supplier-engagement',
  '/intelligence/sourcing-scenarios',
  '/catalog',
  '/products',
  '/marketplaces/listings',
  '/marketplaces/inventory',
  '/marketplaces/orders',
  '/marketplaces/financials',
  '/ai/studio',
  '/ai/studio/seo',
  '/ai/images',
  '/ai/video',
  '/campaigns',
  '/social',
  '/ads',
  '/calendar',
];
const advanced = [
  '/intelligence/sourcing-economics',
  '/intelligence/due-diligence',
  '/intelligence/supplier-shortlisting',
  '/marketplaces',
  '/marketplaces/accounts',
  '/marketplaces/amazon',
  '/marketplaces/flipkart',
  '/intelligence/autonomous',
  '/operations',
  '/workflows',
  '/approvals',
  '/execution-history',
  '/settings',
];
try {
  const d = await start(chrome, s, { width: 1440, height: 900 }, 'wp6-desktop');
  runs.push(d);
  d.page.setDefaultTimeout(20000);
  const p = d.page;
  await p.goto(s.origin + '/setup');
  await p.locator('#full-name').fill('[QA SYNTHETIC] WP6 Owner');
  await p.locator('#email').fill(wp3Owner.email);
  await p.locator('#password').fill(wp3Owner.password);
  await p.locator('#confirmation').fill(wp3Owner.password);
  await p.getByRole('button', { name: 'Create owner', exact: true }).click();
  await p.waitForURL('**/dashboard');
  const { api, brand, op, goal } = await wp3Product(p, s.origin);
  const f = await wp5Operations(api, brand);
  report.ids = { product: f.product.id, order: f.order.id, opportunity: op.id, goal: goal.id };
  const m = await start(chrome, s, { width: 390, height: 844 }, 'mobile');
  runs.push(m);
  m.page.setDefaultTimeout(20000);
  await m.context.addCookies(await d.context.cookies());
  await check(
    '017: all three creative tools explain persisted draft-only eligibility and Catalog next step',
    async () => {
      for (const run of [d, m])
        for (const route of ['/ai/studio/seo', '/ai/images', '/ai/video']) {
          await run.page.goto(s.origin + route);
          const selector = run.page.locator('app-business-entity-selectors').first();
          await expect(selector).toContainText('No active products available');
          await expect(selector).toContainText('Draft and archived products are not eligible');
          await expect(selector).not.toContainText('No products yet');
          await expect(
            selector.getByRole('link', { name: 'Review Catalog products' }),
          ).toHaveAttribute('href', '/catalog');
          await capture(run, 'creative-eligibility-' + route.split('/').at(-1), true);
        }
    },
  );
  await check(
    '009: Video fits 360/390/768/1440; history remains keyboard-scrollable and diagnostics wrap',
    async () => {
      for (const width of [360, 390, 768, 1440]) {
        await m.page.setViewportSize({ width, height: 844 });
        await m.page.goto(s.origin + '/ai/video');
        await expect(m.page.locator('#diagnostics')).toBeVisible();
        await m.page.locator('#diagnostics').scrollIntoViewIfNeeded();
        await expect
          .poll(() => m.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
          .toBe(true);
        const region = m.page.getByRole('region', { name: 'Video generation history' });
        await region.focus();
        await m.page.keyboard.press('ArrowRight');
        expect(await region.evaluate((el) => el.scrollWidth >= el.clientWidth)).toBe(true);
        await capture(m, 'video-responsive-' + width, true);
      }
      await m.page.setViewportSize({ width: 390, height: 844 });
    },
  );
  await check(
    '020: real Login restores exact protected Catalog deep link including query and fragment',
    async () => {
      const a = await start(chrome, s, { width: 1440, height: 900 }, 'wp6-auth');
      runs.push(a);
      const route = `/catalog/${f.product.id}?wp6=return#product-details`;
      await login(a, route);
      await a.page.waitForURL(s.origin + route);
      await expect(a.page.locator('#catalog-product-title')).toHaveText(f.product.name);
      await a.page.reload();
      await expect(a.page.locator('#catalog-product-title')).toHaveText(f.product.name);
      await capture(a, 'auth-restored-exact-catalog', true);
      await axe(a, 'restored-auth-catalog');
      // A malicious return URL must not trigger an external navigation, even after real sign-in.
      const hostile = await start(chrome, s, { width: 390, height: 844 }, 'wp6-hostile-return');
      runs.push(hostile);
      await login(hostile, '/login?returnUrl=%2F%2Fevil.invalid');
      await hostile.page.waitForURL(s.origin + '/dashboard');
      expect(hostile.signals.denied_requests).toEqual([]);
      await capture(hostile, 'unsafe-return-denied');
    },
  );
  await check(
    'Shared context read outage is not an empty-product success; Retry restores same eligibility',
    async () => {
      await p.route('**/api/v1/products?*', (r) =>
        r.fulfill({
          status: 503,
          contentType: 'application/json',
          body: '{"detail":"Synthetic QA outage"}',
        }),
      );
      d.signals.expected_http_errors = [{ path: '/api/v1/products', status: 503 }];
      await p.goto(s.origin + '/ai/studio/seo');
      const selector = p.locator('app-business-entity-selectors');
      await expect(selector).toContainText('Business context is unavailable');
      await expect(selector).not.toContainText('No active products available');
      await capture(d, 'context-outage-recovery');
      await p.unroute('**/api/v1/products?*');
      await selector.getByRole('button', { name: 'Retry business context' }).click();
      await expect(selector).toContainText('No active products available');
    },
  );
  await check(
    'Existing canonical activation makes same Product eligible; no duplicate product or generated output',
    async () => {
      const prior = (await api('get', 'products?all_brands=true')).total;
      await api('patch', `products/${f.product.id}`, {
        description:
          'Synthetic QA organizer description; not real supplier or marketplace evidence.',
      });
      await p.goto(s.origin + `/products/${f.product.id}`);
      const activated = p.waitForResponse(
        (r) => r.url().endsWith(`/products/${f.product.id}/activate`) && r.status() === 200,
      );
      await p.getByRole('button', { name: 'Activate', exact: true }).click();
      await activated;
      await p.goto(s.origin + '/ai/studio/seo');
      await expect(p.getByRole('option', { name: new RegExp('WP5 Organizer') })).toHaveCount(1);
      await p.getByLabel('Product', { exact: true }).selectOption(f.product.id);
      expect((await api('get', 'products?all_brands=true')).total).toBe(prior);
      await capture(d, 'existing-active-product-eligible');
    },
  );
  await check(
    'Mobile navigation and Advanced use readable shared palette, Escape restores focus, Enter closes menu',
    async () => {
      await m.page.goto(s.origin + '/dashboard');
      const menu = m.page.locator('details.mobile-menu');
      await menu.locator('summary').first().focus();
      await m.page.keyboard.press('Enter');
      const adv = menu.locator('details.advanced-nav');
      await adv.locator('summary').click();
      await contrast(
        m,
        adv.getByRole('link', { name: 'Sourcing Economics', exact: true }),
        'advanced-mobile-link',
      );
      expect(report.manual_contrast.at(-1).status).toBe('MEASURED_PASS');
      await axe(m, 'expanded-mobile-navigation');
      await menu.locator('summary').first().focus();
      await m.page.keyboard.press('Escape');
      expect(await menu.evaluate((el) => el.open)).toBe(false);
      await m.page.keyboard.press('Enter');
      await menu.getByRole('link', { name: 'Orders', exact: true }).focus();
      await m.page.keyboard.press('Enter');
      await m.page.waitForURL('**/marketplaces/orders');
      await expect(menu).not.toHaveAttribute('open');
      await expect(m.page.locator('#main-content')).toBeFocused();
    },
  );
  // Real broad screen review: route visits are not claimed as full feature journeys.
  for (const run of [d, m])
    for (const route of process.argv.includes('--focused')
      ? ['/ai/video', '/intelligence/autonomous', '/ai/studio/seo', '/marketplaces/financials']
      : [...primary, ...advanced])
      await review(run, route);
  await check(
    'Recorded order totals stay authoritative and finance explicitly remains a mutable projection',
    async () => {
      await p.goto(s.origin + `/marketplaces/orders?order_id=${f.order.id}`);
      await expect(p.locator('[aria-label="Order details"]')).toContainText('100.13');
      await expect(p.locator('[aria-label="Order details"]')).toContainText('200.25');
      await expect(p.locator('[aria-label="Order details"]')).toContainText('rounded');
      await capture(d, 'rounded-projection-not-source-total', true);
      await p.goto(s.origin + '/marketplaces/financials');
      await expect(p.locator('[aria-label="Financial reporting scope"]')).toContainText(
        'not an accounting ledger',
      );
      await expect(p.locator('main')).toContainText('mutable');
      await expect(p.locator('main')).toContainText('UNKNOWN');
      await p.reload();
      await capture(d, 'mutable-financial-projection', true);
    },
  );
  await p.goto(s.origin + `/catalog/${f.product.id}`);
  const draftCreated = p.waitForResponse(
    (r) =>
      r.request().method() === 'POST' && r.url().endsWith('/listing-drafts') && r.status() === 201,
  );
  await p.getByRole('button', { name: 'Start Amazon India draft', exact: true }).click();
  report.ids.draft = (await (await draftCreated).json()).id;
  for (const run of [d, m]) {
    await run.page.goto(s.origin + `/catalog/${f.product.id}`);
    await expect(run.page.locator('#catalog-product-title')).toBeVisible();
    for (const target of [
      'textarea[name="estimate-reason"]',
      'textarea[maxlength="20000"]',
      'textarea[spellcheck="false"]',
    ])
      await contrast(run, run.page.locator(target), target.replace(/[^a-z]/gi, '-'));
    await axe(run, 'catalog-manual-textareas');
    await capture(run, 'catalog-shared-actions', true);
  }
  await check(
    'Autonomous layout preserves visible policy/controls at narrow widths without starting a mission',
    async () => {
      for (const width of [360, 390, 1440]) {
        await m.page.setViewportSize({ width, height: 844 });
        await m.page.goto(s.origin + '/intelligence/autonomous');
        await expect(
          m.page.getByRole('heading', { name: 'Autonomous research', exact: true }),
        ).toBeVisible();
        expect(
          await m.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
        ).toBe(true);
        await capture(m, 'autonomous-responsive-' + width, true);
      }
      await m.page.setViewportSize({ width: 390, height: 844 });
    },
  );
  edge = await chromium.launch({ channel: 'msedge', headless: true });
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
  ]) {
    const e = await start(edge, s, viewport, 'wp6-edge-' + viewport.width);
    runs.push(e);
    e.page.setDefaultTimeout(20000);
    const route = `/catalog/${f.product.id}?wp6=edge#product-details`;
    await login(e, route);
    await e.page.waitForURL(s.origin + route);
    await expect(e.page.locator('#catalog-product-title')).toHaveText(f.product.name);
    await capture(e, 'edge-auth-deep-link', true);
    for (const r of [
      '/dashboard',
      '/ai/studio/seo',
      '/ai/images',
      '/ai/video',
      '/ads',
      '/ads/optimization',
      '/ads/marketing',
      '/marketplaces/orders',
      '/marketplaces/financials',
    ])
      await review(e, r);
    await e.page.goto(s.origin + '/ai/video');
    expect(
      await e.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
    ).toBe(true);
    await e.page.reload();
    await expect(
      e.page.getByRole('heading', { name: 'AI video studio', exact: true }),
    ).toBeVisible();
  }
  report.status = 'COMPLETE';
} catch (e) {
  report.status = 'FAILED';
  report.error = e.message.slice(0, 1800);
  for (const r of runs) await capture(r, 'failure').catch(() => {});
} finally {
  for (const r of runs) await finish(r);
  await chrome.close();
  if (edge) await edge.close();
  await persist();
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP6 replay complete');
  console.log(
    JSON.stringify({
      token: s.token,
      status: report.status,
      checks: report.checks,
      reviewed: report.review.length,
      manual_contrast: report.manual_contrast,
      error: report.error,
    }),
  );
}
process.exitCode = report.status === 'COMPLETE' ? 0 : 1;
