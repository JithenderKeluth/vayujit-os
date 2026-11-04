import { test as base, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { allowRequest, safeRoute, unexpectedServerErrors } from '../safety.mjs';

const test = base.extend({
  evidence: [
    async ({ page, context, baseURL }, use, info) => {
      expect(await (await page.request.get('/__qa/witness')).json()).toMatchObject({
        token: process.env.QA_TOKEN,
        disposable: true,
      });
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
        const req = route.request();
        if (!allowRequest(req.url(), req.method(), baseURL, '2')) {
          signals.denied_requests.push(safeRoute(req.url()));
          await route.abort();
          return;
        }
        await route.continue();
      });
      page.on('framenavigated', (frame) => {
        if (frame === page.mainFrame() && frame.url().startsWith(baseURL))
          signals.visited_routes.push(safeRoute(frame.url()));
      });
      page.on('console', (message) => {
        if (message.type() === 'error') signals.console_errors.push(message.text().slice(0, 200));
      });
      page.on('pageerror', (error) => signals.page_errors.push(error.message.slice(0, 200)));
      page.on('response', (r) => {
        if (r.status() >= 400)
          signals.http_errors.push({ path: safeRoute(r.url()), status: r.status() });
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

async function fixture(page, required) {
  const data = JSON.parse(
    await fs.readFile(path.join(process.env.QA_RUN_DIR, 'phase2-manifest.json'), 'utf8'),
  );
  test.skip(
    required.some((key) => !data[key]),
    'Blocked: canonical API setup did not produce required artifacts; inspect api-results.json.',
  );
  await page.goto('/login');
  await page.getByLabel('Email', { exact: true }).fill('qa-phase2-owner@example.com');
  await page.getByLabel('Password', { exact: true }).fill('SyntheticPhase2Only123!');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  return data;
}

async function axe(page, info, name) {
  await expect(page.getByRole('main')).toHaveCount(1);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.addScriptTag({ path: 'node_modules/axe-core/axe.min.js' });
  const result = await page.evaluate(async () => {
    const value = await globalThis.axe.run(document);
    return {
      route: location.pathname,
      violations: value.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        help: v.help,
        nodes: v.nodes.map((n) => ({ target: n.target, remediation: n.failureSummary })),
      })),
      incomplete: value.incomplete.map((v) => ({
        id: v.id,
        impact: v.impact,
        count: v.nodes.length,
        nodes: v.nodes.map((n) => ({ target: n.target, remediation: n.failureSummary })),
      })),
      passes: value.passes.length,
    };
  });
  await info.attach(`axe-${name}`, {
    contentType: 'application/json',
    body: JSON.stringify(result),
  });
  expect
    .soft(
      result.violations.filter((v) => ['critical', 'serious'].includes(v.impact)),
      'No serious/critical axe violation',
    )
    .toEqual([]);
}

test('QA-P2-01 selected product supplier context and incomplete due diligence', async ({
  page,
}, info) => {
  const data = await fixture(page, ['supplier_id', 'opportunity_id', 'due_context_id']);
  await page.goto(
    `/intelligence/cross-marketplace?opportunity_id=${data.opportunity_id}&supplier_id=${data.supplier_id}`,
  );
  await expect(page.locator('#supplier-detail')).toBeVisible();
  const canonical = await (
    await page.request.get(`/api/v1/intelligence/cross-marketplace/suppliers/${data.supplier_id}`)
  ).json();
  await expect(page.locator('#detail-title')).toHaveText(canonical.display_name);
  await axe(page, info, 'supplier-detail');
  await page.goto(
    `/intelligence/due-diligence?opportunity_id=${data.opportunity_id}&supplier_id=${data.supplier_id}`,
  );
  await expect(page.getByRole('heading', { name: 'What has been verified?' })).toBeVisible();
  const contexts = await (
    await page.request.get('/api/v1/intelligence/supplier-due-diligence/contexts')
  ).json();
  expect(contexts.find((c) => c.id === data.due_context_id).supplier_id).toBe(data.supplier_id);
  await expect(page.getByText('Open gaps:', { exact: false }).first()).toBeVisible();
  await page.reload();
  await expect(page.getByText('Open gaps:', { exact: false }).first()).toBeVisible();
  await axe(page, info, 'due-diligence');
});

test('QA-P2-02 modeled contribution API UI consistency and reload', async ({ page }, info) => {
  const data = await fixture(page, ['unit', 'opportunity_id']);
  await page.goto(`/intelligence/sourcing-economics?opportunity_id=${data.opportunity_id}`);
  const unit = page.locator('.unit-economics-summary');
  await expect(unit).toBeVisible();
  for (const [label, key] of [
    ['Landed cost / unit', 'per_unit_landed_cost'],
    ['Modeled contribution / unit', 'per_unit_contribution'],
    ['Contribution margin', 'contribution_margin'],
  ]) {
    const row = unit.locator('dl > div').filter({ has: page.locator('dt', { hasText: label }) });
    await expect(row.locator('dd')).toContainText(data.unit[key]);
  }
  await expect(unit).toContainText('not net profit');
  await expect(unit).toContainText('Tax/GST');
  const scrollRegion = page.getByRole('region', {
    name: 'Modeled selling cost components',
    exact: true,
  });
  await scrollRegion.focus();
  await expect(scrollRegion).toBeFocused();
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('Tab');
  await expect(scrollRegion).not.toBeFocused();
  const dimensions = await page.evaluate(() => ({
    height: document.documentElement.scrollHeight,
    viewport: innerHeight,
  }));
  if (dimensions.height > dimensions.viewport * 6) {
    await info.attach('ux-observations', {
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: `QA-P2-UX-ECONOMICS-${info.project.name.toUpperCase()}`,
          feature: 'Commercial decision brief information hierarchy',
          route: '/intelligence/sourcing-economics',
          type: 'USABILITY',
          severity: 'MODERATE',
          priority: 'P2',
          expected:
            'A first-time seller can review key economics, blockers and next action without traversing repeated technical detail.',
          actual: `The populated page is ${dimensions.height}px high at a ${dimensions.viewport}px viewport. The screenshot contains extensive evidence/reason lists before and around the commercial decision.`,
          reproduction_steps: [
            'npm.cmd run qa:phase2',
            'Open the populated economics scenario and review its full-page screenshot.',
          ],
          confidence: 'RECOMMENDATION',
          suggested_fix:
            'Consider a concise seller summary, grouped/de-duplicated reasons, jump links and progressively disclosed evidence. Keep canonical provenance available.',
          retest_status: 'NOT_RETESTED',
        },
      ]),
    });
  }
  await page.reload();
  await expect(unit).toContainText(data.unit.per_unit_contribution);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
    'No horizontal page overflow',
  ).toBe(true);
  await axe(page, info, 'economics');
  await info.attach('economics-overview', {
    contentType: 'image/png',
    body: await page.screenshot({ fullPage: true }),
  });
  if (data.stale_opportunity_id) {
    await page.goto(`/intelligence/sourcing-economics?opportunity_id=${data.stale_opportunity_id}`);
    const stale = page.locator('.unit-economics-summary');
    await expect(stale).toContainText('Stale acquisition inputs');
    await expect(stale).toContainText('recalculate landed cost');
    await expect(stale.locator('dl.input-list')).toHaveCount(0);
    await page.reload();
    await expect(stale).toContainText('Stale acquisition inputs');
    await axe(page, info, 'stale-economics');
  }
});

test('QA-P2-03 explicit HUMAN review, duplicate replay and reopening decision', async ({
  page,
  evidence,
}, info) => {
  const data = await fixture(page, ['opportunity_id', 'goal_id', 'recommendation']);
  await page.goto(
    `/intelligence/sourcing-economics?opportunity_id=${data.opportunity_id}&journey_id=${data.goal_id}`,
  );
  const controls = page.locator('[aria-label="Explicit human decision options"]');
  await expect(controls).toBeVisible();
  await expect(controls.getByRole('button', { name: 'Proceed', exact: true })).toBeDisabled();
  const sent = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/commerce-journeys/${data.goal_id}/decision`) &&
      r.request().method() === 'POST',
  );
  await controls.getByRole('button', { name: 'Keep under review', exact: true }).click();
  const response = await sent;
  const outcome = await response.json();
  await info.attach('human-decision-outcome', {
    contentType: 'application/json',
    body: JSON.stringify({ status: response.status(), outcome }),
  });
  expect(response.status(), JSON.stringify(outcome)).toBe(200);
  const route = `/api/v1/intelligence/product-opportunities/${data.opportunity_id}/human-decision/history`;
  const history = await (await page.request.get(route)).json();
  expect(history).toHaveLength(1);
  expect(history[0].provenance).toBe('HUMAN');
  const replay = await page.request.post(`/api/v1/commerce-journeys/${data.goal_id}/decision`, {
    data: response.request().postDataJSON(),
  });
  const replayOutcome = await replay.json();
  await info.attach('human-decision-replay', {
    contentType: 'application/json',
    body: JSON.stringify({ status: replay.status(), outcome: replayOutcome }),
  });
  expect.soft(replay.status(), JSON.stringify(replayOutcome)).toBe(200);
  const replayRoute = `/api/v1/commerce-journeys/${data.goal_id}/decision`;
  const identical = response.request().postDataJSON();
  const parallel = await Promise.all(
    Array.from({ length: 4 }, () => page.request.post(replayRoute, { data: identical })),
  );
  const replayed = await Promise.all(parallel.map((r) => r.json()));
  expect(parallel.map((r) => r.status())).toEqual([200, 200, 200, 200]);
  expect(new Set(replayed.map((body) => body.decision.id))).toEqual(new Set([outcome.decision.id]));
  evidence.expected_http_errors.push({ path: replayRoute, status: 409 });
  const conflict = await page.request.post(replayRoute, {
    data: { ...identical, action: 'DO_NOT_PROCEED' },
  });
  expect(conflict.status()).toBe(409);
  await info.attach('supplier-scoped-concurrent-replay', {
    contentType: 'application/json',
    body: JSON.stringify({
      statuses: parallel.map((r) => r.status()),
      unique_decisions: new Set(replayed.map((body) => body.decision.id)).size,
      conflict_status: conflict.status(),
    }),
  });
  expect(await (await page.request.get(route)).json()).toHaveLength(1);
  await page.reload();
  await expect(
    page.locator('.decision-control-panel p.callout').filter({ hasText: 'Your decision:' }),
  ).toContainText('KEEP_UNDER_REVIEW');
  await axe(page, info, 'human-decision');
});

test('QA-P2-04 product cost edit cancel, persistence and immutable economic snapshot', async ({
  page,
}, info) => {
  const data = await fixture(page, ['product_id', 'unit']);
  await page.goto(`/products/${data.product_id}/edit`);
  const cost = page.getByLabel('Cost', { exact: true });
  const original = await cost.inputValue();
  await cost.fill('999.99');
  await cost.focus();
  await page.keyboard.press('Tab');
  await expect(cost).not.toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(cost).toBeFocused();
  await page.getByRole('link', { name: 'Cancel', exact: true }).focus();
  await page.keyboard.press('Enter');
  await page.goto(`/products/${data.product_id}/edit`);
  await expect(cost).toHaveValue(original);
  await cost.fill('199.25');
  await page.getByLabel('Price', { exact: true }).fill('499.95');
  await page.getByLabel('Currency', { exact: true }).fill('INR');
  await page.getByRole('button', { name: 'Save product', exact: true }).focus();
  await page.keyboard.press('Space');
  await expect(page).toHaveURL(new RegExp(`/products/${data.product_id}$`));
  const product = await (await page.request.get(`/api/v1/products/${data.product_id}`)).json();
  expect(product).toMatchObject({
    cost_amount: '199.25',
    price_amount: '499.95',
    price_currency: 'INR',
  });
  await page.reload();
  const unit = await (
    await page.request.get(
      `/api/v1/intelligence/product-opportunities/${data.opportunity_id}/assessments/${data.assessment_id}/commercial/unit-economics`,
    )
  ).json();
  expect(unit.per_unit_landed_cost).toBe(data.unit.per_unit_landed_cost);
  await axe(page, info, 'product-cost');
});
