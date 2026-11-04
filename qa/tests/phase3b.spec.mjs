import { test as base, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { allowRequest, safeRoute, unexpectedServerErrors } from '../safety.mjs';

const test = base.extend({
  evidence: [
    async ({ page, context, baseURL }, use, info) => {
      const signals = {
        visited_routes: [],
        http_errors: [],
        expected_http_errors: [],
        denied_requests: [],
        console_errors: [],
        failed_requests: [],
        page_errors: [],
      };
      await context.route('**/*', async (route) => {
        if (!allowRequest(route.request().url(), route.request().method(), baseURL, '3')) {
          signals.denied_requests.push(safeRoute(route.request().url()));
          await route.abort();
        } else await route.continue();
      });
      page.on('framenavigated', (f) => {
        if (f === page.mainFrame() && f.url().startsWith(baseURL))
          signals.visited_routes.push(safeRoute(f.url()));
      });
      page.on('pageerror', (e) => signals.page_errors.push(e.message));
      page.on('response', (r) => {
        if (r.status() >= 400)
          signals.http_errors.push({ path: safeRoute(r.url()), status: r.status() });
      });
      page.on('console', (m) => {
        if (m.type() === 'error') signals.console_errors.push(m.text().slice(0, 200));
      });
      page.on('requestfailed', (r) =>
        signals.failed_requests.push({ path: safeRoute(r.url()), code: r.failure()?.errorText }),
      );
      await use(signals);
      await info.attach('network-and-console', {
        contentType: 'application/json',
        body: JSON.stringify(signals),
      });
      await info.attach('final-screen', {
        contentType: 'image/png',
        body: await page.screenshot({ fullPage: true }),
      });
      expect(signals.page_errors).toEqual([]);
      expect(signals.denied_requests).toEqual([]);
      expect(unexpectedServerErrors(signals)).toEqual([]);
    },
    { auto: true },
  ],
});
async function login(page) {
  const data = JSON.parse(
    await fs.readFile(path.join(process.env.QA_RUN_DIR, 'phase3-manifest.json'), 'utf8'),
  );
  await page.goto('/login');
  await page.getByLabel('Email', { exact: true }).fill('qa-phase3-owner@example.com');
  await page.getByLabel('Password', { exact: true }).fill('SyntheticPhase3Only123!');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  return data;
}
const attach = async (info, name, data) =>
  info.attach(name, { contentType: 'application/json', body: JSON.stringify(data) });
async function axe(page, info, name) {
  await page.addScriptTag({ path: 'node_modules/axe-core/axe.min.js' });
  const result = await page.evaluate(async () => {
    const r = await globalThis.axe.run(document);
    const map = (v) => ({
      id: v.id,
      impact: v.impact,
      nodes: v.nodes.map((n) => ({ target: n.target, remediation: n.failureSummary })),
    });
    return {
      route: location.pathname,
      violations: r.violations.map(map),
      incomplete: r.incomplete.map(map),
      passes: r.passes.length,
    };
  });
  await attach(info, 'axe-' + name, result);
  expect
    .soft(result.violations.filter((v) => ['critical', 'serious'].includes(v.impact)))
    .toEqual([]);
  return result;
}
test('QA-P3B-01 provenance labels and single current research navigation', async ({
  page,
}, info) => {
  await login(page);
  await page.goto('/marketplaces/financials');
  await expect(page.getByRole('note', { name: 'Financial evidence provenance' })).toContainText(
    'Synthetic fixture',
  );
  await expect(page.getByRole('note', { name: 'Financial evidence provenance' })).toContainText(
    'not independently verified',
  );
  await page.reload();
  await expect(page.getByRole('note', { name: 'Financial evidence provenance' })).toContainText(
    'Synthetic fixture',
  );
  await axe(page, info, 'provenance');
  await page.goto('/intelligence/business-agent');
  const nav = page.locator('nav[aria-label="Primary navigation"]');
  await expect(nav.locator('a[href="/intelligence/business-agent"]')).toHaveAttribute(
    'aria-current',
    'page',
  );
  await expect(nav.locator('a[href="/intelligence"]')).not.toHaveAttribute('aria-current', 'page');
  await attach(info, 'navigation-current', {
    current: await nav.locator('a[aria-current="page"]').allTextContents(),
  });
});
test('QA-P3B-02 server filtered pages, resolved reload and empty state', async ({ page }, info) => {
  test.setTimeout(180000);
  const data = await login(page);
  expect(data.inventory.product_id).toBeTruthy();
  for (let index = 0; index < 27; index++) {
    const response = await page.request.post('/api/v1/inventory/items', {
      headers: { Origin: process.env.QA_ORIGIN },
      data: {
        product_id: data.inventory.product_id,
        internal_sku: `QA3B-BROWSER-${index}`,
        opening_quantity: 0,
        low_stock_threshold: 5,
        idempotency_key: `qa3b-browser-${index}`,
      },
    });
    expect(response.status()).toBe(201);
  }
  expect(
    (
      await page.request.post('/api/v1/operations/action-center/scan', {
        headers: { Origin: process.env.QA_ORIGIN },
        data: {},
      })
    ).status(),
  ).toBe(200);
  await page.goto('/operations/action-center');
  await page.getByRole('searchbox', { name: 'Search' }).fill('QA3B-BROWSER');
  await expect(
    page.getByRole('heading', { name: '27 matching issue(s)', exact: true }),
  ).toBeVisible();
  await expect(page.locator('.signal-card')).toHaveCount(25);
  await page.getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(page.locator('.signal-card')).toHaveCount(2);
  await page
    .locator('.signal-card')
    .first()
    .getByRole('button', { name: 'Resolve', exact: true })
    .click();
  await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption('RESOLVED');
  await expect(page.locator('.signal-card')).toHaveCount(1);
  await page.locator('.signal-card').getByRole('button', { name: 'Inspect evidence' }).click();
  await expect(page.getByRole('region', { name: 'Selected signal evidence' })).toContainText(
    'HUMAN',
  );
  await page.reload();
  // Filters are view state, not persisted business state. Reapply the explicit filter.
  await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption('RESOLVED');
  await page.getByRole('searchbox', { name: 'Search' }).fill('QA3B-BROWSER');
  await expect(page.locator('.signal-card')).toHaveCount(1);
  await axe(page, info, 'resolved-filter');
  await page.getByRole('searchbox', { name: 'Search' }).fill('absent-qa3b-browser');
  await expect(page.getByRole('heading', { name: 'No matching issues' })).toBeVisible();
});
test('QA-P3B-03 expose every outstanding caption and financial contrast target', async ({
  page,
}, info) => {
  test.setTimeout(300000);
  const data = await login(page);
  expect(data.phase2).toBeTruthy();
  const p = data.phase2;
  const states = [
    [
      'due-diligence',
      `/intelligence/due-diligence?opportunity_id=${p.opportunity_id}&supplier_id=${p.supplier_id}`,
      'Open gaps:',
    ],
    [
      'economics',
      `/intelligence/sourcing-economics?opportunity_id=${p.opportunity_id}`,
      'Modeled contribution / unit',
    ],
    [
      'stale-economics',
      `/intelligence/sourcing-economics?opportunity_id=${p.stale_opportunity_id}`,
      'Stale acquisition inputs',
    ],
    [
      'human-decision',
      `/intelligence/sourcing-economics?opportunity_id=${p.opportunity_id}&journey_id=${p.goal_id}`,
      'Your decision:',
    ],
    ['financial', '/marketplaces/financials', 'Sales summary'],
  ];
  for (const [name, route, ready] of states) {
    await page.goto(route);
    if (name === 'financial')
      await expect(page.getByRole('region', { name: ready, exact: true })).toBeVisible();
    else await expect(page.getByText(ready, { exact: false }).first()).toBeVisible();
    const full = await axe(page, info, 'completion-' + name);
    const targets =
      name === 'financial'
        ? full.incomplete
            .filter((r) => r.id === 'color-contrast')
            .flatMap((r) =>
              r.nodes.map((n) => ({ locator: page.locator(n.target[0]), selector: n.target[0] })),
            )
        : await Promise.all(
            (await page.locator('caption').all()).map(async (locator, index) => ({
              locator,
              selector: `caption index ${index}: ${await locator.innerText()}`,
            })),
          );
    const diagnostics = [];
    for (const [index, { locator, selector }] of targets.entries()) {
      await locator.scrollIntoViewIfNeeded();
      const scroll = locator.locator('xpath=ancestor::*[@tabindex="0"][1]');
      if (await scroll.count()) {
        await scroll.focus();
        await page.keyboard.press('Home');
        await page.keyboard.press('ArrowRight');
        await locator.scrollIntoViewIfNeeded();
      }
      const result = await locator.evaluate(async (element) => {
        const rect = element.getBoundingClientRect();
        const r = await globalThis.axe.run(element, {
          runOnly: { type: 'rule', values: ['color-contrast'] },
        });
        const range = document.createRange();
        range.selectNodeContents(element);
        const boxes = [...range.getClientRects()].map((b) => ({
          left: b.left,
          top: b.top,
          right: b.right,
          bottom: b.bottom,
        }));
        return {
          html: element.outerHTML.slice(0, 1200),
          text: element.textContent.trim(),
          bounds: { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom },
          viewport: { width: innerWidth, height: innerHeight },
          text_boxes: boxes,
          violations: r.violations.map((v) => ({
            id: v.id,
            nodes: v.nodes.map((n) => ({ target: n.target, remediation: n.failureSummary })),
          })),
          incomplete: r.incomplete.map((v) => ({
            id: v.id,
            nodes: v.nodes.map((n) => ({ target: n.target, remediation: n.failureSummary })),
          })),
          passes: r.passes.map((v) => v.id),
        };
      });
      diagnostics.push({ selector, ...result });
      expect.soft(result.violations).toEqual([]);
      await info.attach(`review-${name}-${index}`, {
        contentType: 'image/png',
        body: await page.screenshot(),
      });
    }
    await attach(info, 'accessibility-completion-' + name, {
      route,
      diagnostics,
      scope:
        'Real scrolling/focus only; no nodes, rules, styles or thresholds removed. Incomplete results remain manual review.',
    });
  }
});
