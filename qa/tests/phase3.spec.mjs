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
        if (!allowRequest(req.url(), req.method(), baseURL, '3')) {
          signals.denied_requests.push(safeRoute(req.url()));
          await route.abort();
          return;
        }
        await route.continue();
      });
      page.on('framenavigated', (f) => {
        if (f === page.mainFrame() && f.url().startsWith(baseURL))
          signals.visited_routes.push(safeRoute(f.url()));
      });
      page.on('console', (m) => {
        if (m.type() === 'error') signals.console_errors.push(m.text().slice(0, 200));
      });
      page.on('pageerror', (e) => signals.page_errors.push(e.message.slice(0, 200)));
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

async function fixture(page, required = []) {
  const data = JSON.parse(
    await fs.readFile(path.join(process.env.QA_RUN_DIR, 'phase3-manifest.json'), 'utf8'),
  );
  test.skip(
    required.some((k) => !data[k]),
    'Canonical API fixture missing; inspect actual Phase 3 API failures.',
  );
  await page.goto('/login');
  await page.getByLabel('Email', { exact: true }).fill('qa-phase3-owner@example.com');
  await page.getByLabel('Password', { exact: true }).fill('SyntheticPhase3Only123!');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  return data;
}

async function attach(info, name, data) {
  await info.attach(name, { contentType: 'application/json', body: JSON.stringify(data) });
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
  await attach(info, `axe-${name}`, result);
  expect
    .soft(
      result.violations.filter((v) => ['critical', 'serious'].includes(v.impact)),
      'No serious/critical axe violation',
    )
    .toEqual([]);
  return result;
}

test('QA-P3-01 seller adjusts stock, reopens ledger and rejects stale balance', async ({
  page,
}, info) => {
  const data = await fixture(page, ['inventory']);
  await page.goto('/marketplaces/inventory');
  const row = page.getByRole('row').filter({
    has: page.getByRole('rowheader', { name: data.inventory.internal_sku, exact: true }),
  });
  await expect(row).toBeVisible();
  const before = (await (await page.request.get('/api/v1/inventory')).json()).find(
    (x) => x.id === data.inventory.id,
  );
  await row.getByRole('button', { name: 'Adjust stock', exact: true }).click();
  const form = page.getByRole('form', { name: 'Human stock adjustment' });
  await form.getByLabel('Delta', { exact: true }).fill('2');
  await form.getByLabel('Reason', { exact: true }).fill('[QA SYNTHETIC] seller receipt');
  await form.getByRole('button', { name: 'Record adjustment' }).focus();
  await page.keyboard.press('Enter');
  await expect(form).toHaveCount(0);
  await page.reload();
  await expect(row).toContainText(`${before.on_hand_quantity + 2} each`);
  await row.getByRole('button', { name: 'View ledger' }).click();
  await expect(page.getByRole('region', { name: 'Inventory movement ledger' })).toContainText(
    '[QA SYNTHETIC] seller receipt',
  );
  await row.getByRole('button', { name: 'Adjust stock', exact: true }).click();
  const current = (await (await page.request.get('/api/v1/inventory')).json()).find(
    (x) => x.id === data.inventory.id,
  );
  expect(
    (
      await page.request.post(`/api/v1/inventory/${current.id}/adjust`, {
        data: {
          delta: 1,
          reason: 'Competing synthetic receipt',
          expected_version: current.version,
          idempotency_key: 'qa3-browser-other',
        },
        headers: { Origin: process.env.QA_ORIGIN },
      })
    ).status(),
  ).toBe(200);
  await form.getByLabel('Delta', { exact: true }).fill('1');
  await form.getByLabel('Reason', { exact: true }).fill('Stale synthetic form');
  await form.getByRole('button', { name: 'Record adjustment' }).click();
  await expect(form.getByRole('alert')).toContainText('stock changed');
  await axe(page, info, 'inventory-stale-adjustment');
});

test('QA-P3-02 order timeline, source, empty filter and reload agree with API', async ({
  page,
}, info) => {
  const data = await fixture(page, ['order']);
  await page.goto('/marketplaces/orders');
  const row = page.getByRole('row').filter({
    has: page.getByRole('rowheader', { name: data.order.remote_order_id, exact: true }),
  });
  await expect(row).toContainText('returned');
  await expect(row).toContainText('Local fake provider');
  await row.getByRole('button', { name: 'View details' }).click();
  await expect(page.getByRole('region', { name: 'Order details' })).toContainText('returned');
  await page.reload();
  await expect(row).toContainText('returned');
  await page.getByLabel('Status', { exact: true }).fill('nonexistent-status');
  await page.getByLabel('Status', { exact: true }).press('Enter');
  await expect(page.getByRole('heading', { name: 'No unified orders yet' })).toBeVisible();
  await page.getByLabel('Status', { exact: true }).fill('');
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await expect(row).toBeVisible();
  await axe(page, info, 'orders-persisted');
});

test('QA-P3-03 financial decimals, loss, missing settlements and seller explanations', async ({
  page,
}, info) => {
  const data = await fixture(page, ['financial_expected']);
  await page.goto('/marketplaces/financials');
  await page.getByRole('combobox', { name: 'Marketplace', exact: true }).selectOption('amazon');
  await page.getByLabel('Date to', { exact: true }).fill('2026-01-31');
  const summary = page.getByRole('region', { name: 'Sales summary', exact: true });
  await expect(summary).toContainText('INR ' + data.financial_expected.contribution);
  await expect(summary).toContainText('Synthetic fixture');
  await expect(page.getByRole('region', { name: 'Financial alerts', exact: true })).toContainText(
    'exceed net sales',
  );
  await expect(page.locator('#financial-agent-heading')).toBeVisible();
  await page.reload();
  // Filters are not persisted by this contract; reapply rather than claiming otherwise.
  await page.getByRole('combobox', { name: 'Marketplace', exact: true }).selectOption('amazon');
  await page.getByLabel('Date to', { exact: true }).fill('2026-01-31');
  await expect(summary).toContainText('INR ' + data.financial_expected.contribution);
  // Settlements were observed at the rehearsal date, outside the January sales filter.
  await page.getByLabel('Date to', { exact: true }).fill('');
  const table = page.getByRole('region', { name: 'Settlement reconciliation table' });
  await expect(table).toContainText('QA3-UNKNOWN');
  await expect(table.getByRole('row').filter({ hasText: 'QA3-UNKNOWN' })).toContainText('UNKNOWN');
  await table.focus();
  await expect(table).toBeFocused();
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('Tab');
  await expect(table).not.toBeFocused();
  await axe(page, info, 'financial-loss-and-unknown');
});

test('QA-P3-04 HUMAN signal acknowledgement, audit and resolved status filter', async ({
  page,
}, info) => {
  const data = await fixture(page, ['browser_signal']);
  await page.goto('/operations/action-center');
  const card = page.locator('.signal-card').filter({ hasText: data.browser_signal.evidence.sku });
  await expect(card).toBeVisible();
  await expect(card).toContainText('InventoryItem');
  await card.getByRole('button', { name: 'Inspect evidence' }).click();
  await card.getByRole('button', { name: 'Acknowledge', exact: true }).click();
  await expect(card).toContainText('ACKNOWLEDGED');
  await card.getByRole('button', { name: 'Resolve', exact: true }).click();
  await expect(card).toHaveCount(0);
  await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption('RESOLVED');
  // A genuine seller action should load the resolved set; do not press a hidden repair CTA.
  await expect
    .soft(card, 'Resolved status filter retrieves persisted resolved signals')
    .toBeVisible();
  const detail = await (
    await page.request.get(`/api/v1/operations/action-center/signals/${data.browser_signal.id}`)
  ).json();
  expect(detail.signal.status).toBe('RESOLVED');
  expect(detail.history.length).toBeGreaterThan(1);
  await attach(info, 'resolved-signal-api', detail);
  await axe(page, info, 'action-center-resolved-filter');
});

test('QA-P3-05 API failure, timeout recovery and committed-response interruption', async ({
  page,
  context,
}, info) => {
  const data = await fixture(page, ['inventory']);
  const url = '**/api/v1/financial/summary*';
  await page.route(url, (route) => route.abort('timedout'));
  await page.goto('/marketplaces/financials');
  await expect(
    page.getByRole('heading', { name: 'Financial evidence is unavailable' }),
  ).toBeVisible();
  await page.unroute(url);
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Sales summary', exact: true })).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Financial evidence is unavailable' }),
  ).toHaveCount(0);
  // Lose the HTTP response after the real canonical commit; replay exactly the same key.
  const current = (await (await page.request.get('/api/v1/inventory')).json()).find(
    (x) => x.id === data.inventory.id,
  );
  const payload = {
    delta: 1,
    expected_version: current.version,
    reason: '[QA SYNTHETIC] interrupted reply',
    idempotency_key: 'qa3-interrupted-response',
  };
  const routePath = `/api/v1/inventory/${current.id}/adjust`;
  await page.route('**' + routePath, async (route) => {
    await route.fetch();
    await route.abort('connectionreset');
  });
  const browserStatus = await page.evaluate(
    async ({ routePath, payload }) => {
      try {
        await fetch(routePath, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        return 'unexpected-response';
      } catch {
        return 'response-lost';
      }
    },
    { routePath, payload },
  );
  expect(browserStatus).toBe('response-lost');
  await page.unroute('**' + routePath);
  const replay = await page.request.post(routePath, {
    data: payload,
    headers: { Origin: process.env.QA_ORIGIN },
  });
  expect(replay.status()).toBe(200);
  expect((await replay.json()).on_hand_quantity).toBe(current.on_hand_quantity + 1);
  const freshPage = await context.newPage();
  await freshPage.goto('/marketplaces/inventory');
  await expect(
    freshPage.getByRole('rowheader', { name: current.internal_sku, exact: true }),
  ).toBeVisible();
  await freshPage.close();
  await attach(info, 'interruption-recovery', {
    browserStatus,
    replay_status: replay.status(),
    balance: await replay.json(),
    actual_process_restart: false,
  });
  const restart = await page.request.post('/__qa/restart', {
    headers: { 'X-QA-Token': process.env.QA_TOKEN },
    // The supervisor allows >30s; a Windows cold restart was measured at 18.9s.
    timeout: 45000,
  });
  expect(restart.status()).toBe(200);
  const restartProof = await restart.json();
  expect(restartProof.after_process).not.toBe(restartProof.before_process);
  await attach(info, 'owned-api-restart', restartProof);
  await page.reload();
  await expect(page.getByRole('region', { name: 'Sales summary', exact: true })).toBeVisible();
  const persistedBalance = (await (await page.request.get('/api/v1/inventory')).json()).find(
    (x) => x.id === current.id,
  );
  expect(persistedBalance.on_hand_quantity).toBe(current.on_hand_quantity + 1);
  await axe(page, info, 'financial-recovered');
});

test('QA-P3-06 investigate original mobile obscured-table contrast states', async ({
  page,
}, info) => {
  test.setTimeout(240000);
  const data = await fixture(page, ['phase2']);
  const p2 = data.phase2;
  const states = [
    [
      'due-diligence',
      `/intelligence/due-diligence?opportunity_id=${p2.opportunity_id}&supplier_id=${p2.supplier_id}`,
      'What has been verified?',
    ],
    [
      'economics',
      `/intelligence/sourcing-economics?opportunity_id=${p2.opportunity_id}`,
      'Modeled contribution / unit',
    ],
    [
      'stale-economics',
      `/intelligence/sourcing-economics?opportunity_id=${p2.stale_opportunity_id}`,
      'Stale acquisition inputs',
    ],
    [
      'human-decision',
      `/intelligence/sourcing-economics?opportunity_id=${p2.opportunity_id}&journey_id=${p2.goal_id}`,
      'Modeled contribution / unit',
    ],
  ];
  for (const [name, route, loaded] of states) {
    await page.goto(route);
    await expect(page.getByText(loaded, { exact: false }).first()).toBeVisible();
    if (name === 'due-diligence') {
      await expect(page.getByText('Open gaps:', { exact: false }).first()).toBeVisible();
    }
    if (name === 'human-decision') {
      const controls = page.locator('[aria-label="Explicit human decision options"]');
      await expect(controls).toBeVisible();
      await expect(controls.getByRole('button', { name: 'Proceed', exact: true })).toBeDisabled();
      const sent = page.waitForResponse(
        (r) =>
          r.url().endsWith(`/commerce-journeys/${p2.goal_id}/decision`) &&
          r.request().method() === 'POST',
      );
      await controls.getByRole('button', { name: 'Keep under review', exact: true }).click();
      const decision = await sent;
      expect(decision.status()).toBe(200);
      await attach(info, 'contrast-review-human-decision', await decision.json());
      await page.reload();
      await expect(
        page.locator('.decision-control-panel p.callout').filter({ hasText: 'Your decision:' }),
      ).toContainText('KEEP_UNDER_REVIEW');
    }
    const full = await axe(page, info, 'review-' + name);
    const targets = full.incomplete
      .filter((r) => r.id === 'color-contrast')
      .flatMap((r) => r.nodes.map((n) => n.target));
    const diagnostics = [];
    for (const target of targets) {
      if (target.length !== 1 || typeof target[0] !== 'string') continue;
      const element = page.locator(target[0]);
      if ((await element.count()) !== 1) continue;
      await element.scrollIntoViewIfNeeded();
      const result = await page.evaluate(async (selector) => {
        const element = document.querySelector(selector);
        const rect = element.getBoundingClientRect();
        const result = await globalThis.axe.run(element, {
          runOnly: { type: 'rule', values: ['color-contrast'] },
        });
        return {
          selector,
          bounds: { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom },
          violations: result.violations.map((r) => ({
            id: r.id,
            nodes: r.nodes.map((n) => ({ target: n.target, remediation: n.failureSummary })),
          })),
          incomplete: result.incomplete.map((r) => ({
            id: r.id,
            nodes: r.nodes.map((n) => ({ target: n.target, remediation: n.failureSummary })),
          })),
          passes: result.passes.map((r) => r.id),
        };
      }, target[0]);
      diagnostics.push(result);
      expect
        .soft(result.violations, 'Scrolled target has no confirmed contrast violation')
        .toEqual([]);
    }
    await attach(info, 'obscured-table-' + name, {
      purpose:
        'Diagnostic established-engine checks after real scrolling; does not replace the full-document scan.',
      targets,
      diagnostics,
    });
    await info.attach('scrolled-' + name, {
      contentType: 'image/png',
      body: await page.screenshot(),
    });
  }
});
