import { test as base, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { allowRequest, safeRoute, unexpectedServerErrors } from './safety.mjs';
import { snapshotSurface, surfaceId } from './phase4-surface.mjs';

export const attach = (info, name, value) =>
  info.attach(name, { contentType: 'application/json', body: JSON.stringify(value) });
export const test = base.extend({
  exploration: [
    async ({ page, context, baseURL }, use, info) => {
      const signals = {
        visited_routes: [],
        http_errors: [],
        expected_http_errors: [],
        denied_requests: [],
        console_errors: [],
        page_errors: [],
        failed_requests: [],
        api_operations: [],
      };
      await context.route('**/*', async (route) => {
        const r = route.request();
        if (!allowRequest(r.url(), r.method(), baseURL, '4')) {
          signals.denied_requests.push({ path: safeRoute(r.url()), method: r.method() });
          await route.abort();
        } else await route.continue();
      });
      page.on('framenavigated', (f) => {
        if (f === page.mainFrame() && f.url().startsWith(baseURL))
          signals.visited_routes.push(safeRoute(f.url()));
      });
      page.on('response', (r) => {
        const route = safeRoute(r.url());
        if (route.startsWith('/api/'))
          signals.api_operations.push({
            path: route,
            method: r.request().method(),
            status: r.status(),
            screen: safeRoute(page.url()),
          });
        if (r.status() >= 400) signals.http_errors.push({ path: route, status: r.status() });
      });
      page.on('console', (m) => {
        if (m.type() === 'error') signals.console_errors.push(m.text().slice(0, 250));
      });
      page.on('pageerror', (e) => signals.page_errors.push(e.message.slice(0, 250)));
      page.on('requestfailed', (r) =>
        signals.failed_requests.push({ path: safeRoute(r.url()), code: r.failure()?.errorText }),
      );
      await use(signals);
      await attach(info, 'network-and-console', signals);
      await info.attach('final-screen', {
        contentType: 'image/png',
        body: await page.screenshot(),
      });
      expect
        .soft(signals.denied_requests, 'No unexplained blocked external/mutation request')
        .toEqual([]);
      expect.soft(signals.page_errors, 'No uncaught page exception').toEqual([]);
      expect.soft(unexpectedServerErrors(signals), 'No unexplained API 5xx').toEqual([]);
    },
    { auto: true },
  ],
});
export { expect };
export async function manifest() {
  return JSON.parse(
    await fs.readFile(path.join(process.env.QA_RUN_DIR, 'phase3-manifest.json'), 'utf8'),
  );
}
export async function login(page, ui = false) {
  if (ui) {
    await page.goto('/login');
    await page.getByLabel('Email', { exact: true }).fill('qa-phase3-owner@example.com');
    await page.getByLabel('Password', { exact: true }).fill('SyntheticPhase3Only123!');
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  } else {
    const r = await page.request.post('/api/v1/auth/login', {
      data: { email: 'qa-phase3-owner@example.com', password: 'SyntheticPhase3Only123!' },
    });
    expect(r.status()).toBe(200);
  }
}
export async function scanAxe(page, info, name) {
  if (!(await page.evaluate(() => !!globalThis.axe)))
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
  return result;
}
export async function visitSurface(page, info, row, state = 'default') {
  const key = surfaceId(row.route + '|' + state);
  await page.goto(row.target, { waitUntil: 'domcontentloaded', timeout: 20000 });
  const settled = await page
    .waitForLoadState('networkidle', { timeout: 3000 })
    .then(() => true)
    .catch(() => false);
  const data = await snapshotSurface(page, row.route, state);
  data.route_match = data.route === new URL(row.target, 'http://local').pathname;
  data.settled = settled;
  await info.attach('surface-screen-' + key, {
    contentType: 'image/png',
    body: await page.screenshot(),
  });
  await attach(info, 'surface-' + key, data);
  return data;
}

export async function inspectContrastNode(page, info, locator, name) {
  await locator.scrollIntoViewIfNeeded();
  const container = locator.locator('xpath=ancestor::*[@tabindex="0"][1]');
  if (await container.count()) {
    await container.focus();
    await page.keyboard.press('Home');
    await page.keyboard.press('ArrowLeft');
    await container.evaluate((e) => e.scrollTo({ left: 0, behavior: 'instant' }));
    await locator.scrollIntoViewIfNeeded();
  }
  const result = await locator.evaluate(async (element) => {
    const rect = element.getBoundingClientRect();
    const range = document.createRange();
    range.selectNodeContents(element);
    const boxes = [...range.getClientRects()].map((r) => ({
      left: r.left,
      right: r.right,
      top: r.top,
      bottom: r.bottom,
    }));
    const r = await globalThis.axe.run(element, {
      runOnly: { type: 'rule', values: ['color-contrast'] },
    });
    const map = (v) => ({
      id: v.id,
      impact: v.impact,
      nodes: v.nodes.map((n) => ({ target: n.target, remediation: n.failureSummary })),
    });
    return {
      route: location.pathname,
      html: element.outerHTML.slice(0, 1600),
      text: element.textContent.trim(),
      bounds: { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom },
      viewport: { width: innerWidth, height: innerHeight },
      text_boxes: boxes,
      violations: r.violations.map(map),
      incomplete: r.incomplete.map(map),
      passes: r.passes.map((v) => v.id),
      text_horizontally_in_view: boxes.every((b) => b.left >= 0 && b.right <= innerWidth),
    };
  });
  await info.attach('node-screen-' + name, {
    contentType: 'image/png',
    body: await page.screenshot(),
  });
  await attach(info, 'node-review-' + name, result);
  return result;
}
