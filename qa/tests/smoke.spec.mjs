import { test as base, expect } from '@playwright/test';
import { allowRequest, safeRoute, unexpectedServerErrors } from '../safety.mjs';

const email = 'qa-synthetic-owner@example.com';
const password = 'SyntheticQaOnly123!';
const test = base.extend({
  evidence: [
    async ({ page, context, baseURL }, use, info) => {
      const signals = {
        visited_routes: [],
        console_errors: [],
        page_errors: [],
        failed_requests: [],
        http_errors: [],
        expected_http_errors: [],
        denied_requests: [],
      };
      const witness = await (await page.request.get('/__qa/witness')).json();
      expect(witness).toMatchObject({ token: process.env.QA_TOKEN, disposable: true });
      await context.route('**/*', async (route) => {
        const request = route.request();
        if (!allowRequest(request.url(), request.method(), baseURL)) {
          signals.denied_requests.push({
            method: request.method(),
            path: safeRoute(request.url()),
          });
          await route.abort('blockedbyclient');
          return;
        }
        await route.continue();
      });
      page.on('console', (message) => {
        if (message.type() === 'error') signals.console_errors.push(message.text().slice(0, 200));
      });
      page.on('framenavigated', (frame) => {
        if (frame === page.mainFrame() && frame.url().startsWith(baseURL))
          signals.visited_routes.push(safeRoute(frame.url()));
      });
      page.on('pageerror', (error) => signals.page_errors.push(error.message.slice(0, 200)));
      page.on('requestfailed', (request) =>
        signals.failed_requests.push({
          path: safeRoute(request.url()),
          code: request.failure()?.errorText,
        }),
      );
      page.on('response', (response) => {
        if (response.status() >= 400)
          signals.http_errors.push({ path: safeRoute(response.url()), status: response.status() });
      });
      await use(signals);
      await info.attach('network-and-console', {
        body: JSON.stringify(signals, null, 2),
        contentType: 'application/json',
      });
      await info.attach('final-screen', {
        body: await page.screenshot({ fullPage: true }),
        contentType: 'image/png',
      });
      expect(signals.page_errors, 'No unhandled browser exceptions').toEqual([]);
      expect(signals.denied_requests, 'No external or unauthorized mutations attempted').toEqual(
        [],
      );
      expect(unexpectedServerErrors(signals), 'No server exceptions').toEqual([]);
    },
    { auto: true },
  ],
});

async function axe(page, info, state) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.addScriptTag({ path: 'node_modules/axe-core/axe.min.js' });
  const result = await page.evaluate(async () => {
    const scanned = await globalThis.axe.run(document);
    return {
      route: location.pathname,
      violations: scanned.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        help: v.help,
        nodes: v.nodes.map((n) => ({ target: n.target, remediation: n.failureSummary })),
      })),
      incomplete: scanned.incomplete.map((v) => ({
        id: v.id,
        impact: v.impact,
        count: v.nodes.length,
        nodes: v.nodes.map((n) => ({ target: n.target, remediation: n.failureSummary })),
      })),
      passes: scanned.passes.length,
    };
  });
  await info.attach(`axe-${state}`, {
    body: JSON.stringify(result, null, 2),
    contentType: 'application/json',
  });
  expect
    .soft(
      result.violations.filter((v) => ['critical', 'serious'].includes(v.impact)),
      `${state}: no serious/critical axe violations`,
    )
    .toEqual([]);
}

async function signIn(page) {
  const status = await (await page.request.get('/api/v1/auth/setup-status')).json();
  if (!status.ownerExists) {
    // Canonical fallback keeps independent tests runnable when owner-UI test fails.
    const created = await page.request.post('/api/v1/auth/setup-owner', {
      data: {
        full_name: '[QA SYNTHETIC] Owner',
        email,
        password,
        password_confirmation: password,
      },
    });
    expect(created.status()).toBe(201);
  }
  await page.goto('/login');
  // A canonical setup call may already have authenticated this isolated context.
  if (new URL(page.url()).pathname === '/login') {
    await page.getByLabel('Email', { exact: true }).fill(email);
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  }
  await expect(page).toHaveURL(/\/dashboard$/);
}

test('QA-SMOKE-01 owner onboarding, invalid input and keyboard', async ({ page }, info) => {
  await test.step('Readiness and genuine empty installation', async () => {
    expect((await page.request.get('/health/live')).status()).toBe(200);
    expect(await (await page.request.get('/api/v1/auth/setup-status')).json()).toEqual({
      ownerExists: false,
    });
    const readiness = await page.request.get('/health/ready');
    await info.attach('readiness-orm-fixture-not-migration-certified', {
      body: await readiness.body(),
      contentType: 'application/json',
    });
    expect((await page.request.get('/api/v1/products')).status()).toBe(401);
    await page.goto('/setup');
    await expect(page.getByRole('heading', { name: 'Create your owner account' })).toBeVisible();
  });
  await test.step('Keyboard, invalid email, mismatched password', async () => {
    await expect(page.getByRole('button', { name: 'Create owner', exact: true })).toBeDisabled();
    await page.getByLabel('Email', { exact: true }).focus();
    await page.keyboard.press('Tab');
    await expect(page.getByLabel('Password', { exact: true })).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(page.getByLabel('Email', { exact: true })).toBeFocused();
    await page.getByLabel('Full name').fill('[QA SYNTHETIC] Owner');
    await page.getByLabel('Email', { exact: true }).fill('not-an-email');
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByLabel('Confirm password').fill('Mismatch123!');
    await expect(page.getByRole('button', { name: 'Create owner', exact: true })).toBeDisabled();
    await page.getByLabel('Email', { exact: true }).fill(email);
    await page.getByRole('button', { name: 'Create owner', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Passwords do not match');
    await axe(page, info, 'owner-validation');
  });
  await test.step('Create owner through UI; single-owner enforcement', async () => {
    await page.getByLabel('Confirm password').fill(password);
    await page.getByRole('button', { name: 'Create owner', exact: true }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    expect(await (await page.request.get('/api/v1/auth/setup-status')).json()).toEqual({
      ownerExists: true,
    });
    const duplicate = await page.request.post('/api/v1/auth/setup-owner', {
      data: {
        full_name: 'Forbidden second owner',
        email: 'qa-second@example.com',
        password,
        password_confirmation: password,
      },
    });
    expect(duplicate.status()).toBe(409);
    await axe(page, info, 'dashboard');
  });
});

test('QA-SMOKE-02 seller creates and edits INR catalog product; persistence and blockers', async ({
  page,
}, info) => {
  await signIn(page);
  await page.goto('/catalog');
  await expect(
    page.getByRole('heading', { name: 'Product master & listing preparation' }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Your catalog is empty', exact: true }),
  ).toBeVisible();
  await axe(page, info, 'catalog-empty');
  await page.goto('/brands/new');
  await page.getByLabel('Name *', { exact: true }).fill('[QA SYNTHETIC] Vayujit');
  await page.getByRole('button', { name: 'Save brand', exact: true }).click();
  await expect(page).toHaveURL(/\/brands\/[a-f0-9-]+$/);
  await page.goto('/products/new');
  const initialCurrency = await page.getByLabel('Currency', { exact: true }).inputValue();
  if (initialCurrency === 'USD') {
    await info.attach('ux-observations', {
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: `QA-UX-CURRENCY-${info.project.name.toUpperCase()}`,
          feature: 'Indian seller product creation',
          route: '/products/new',
          type: 'USABILITY',
          severity: 'MINOR',
          priority: 'P2',
          expected:
            'A seller should understand and explicitly confirm the intended pricing currency.',
          actual:
            'The new product form defaults to USD even in this Indian-seller journey; INR must be entered manually.',
          reproduction_steps: [
            'Create a brand',
            'Open /products/new',
            'Inspect Currency before entering a price',
          ],
          evidence: [],
          confidence: 'RECOMMENDATION',
          suggested_fix:
            'Consider using an explicitly configured business currency or a prominent currency confirmation; do not infer currency silently.',
          retest_status: 'NOT_RETESTED',
        },
      ]),
    });
  }
  await expect(page.getByRole('button', { name: 'Save product', exact: true })).toBeDisabled();
  const brandSelect = page.locator('select[formcontrolname="brand_id"]');
  await expect(brandSelect.locator('option')).toContainText(['[QA SYNTHETIC] Vayujit']);
  await brandSelect.selectOption({ label: '[QA SYNTHETIC] Vayujit' });
  await page.getByLabel('Name *', { exact: true }).fill('[QA SYNTHETIC] Resistance Band');
  await page.getByLabel('Category', { exact: true }).fill('Sports and outdoor fitness');
  await page.getByLabel('Price', { exact: true }).fill('599.50');
  await page.getByLabel('Currency', { exact: true }).fill('INR');
  await page.getByLabel('Cost', { exact: true }).fill('199.25');
  await page.getByLabel('SKU', { exact: true }).fill('QA-BAND-001');
  const created = page.waitForResponse(
    (r) => r.url().endsWith('/api/v1/products') && r.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Save product', exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  const product = await response.json();
  await expect(page).toHaveURL(new RegExp(`/products/${product.id}$`));
  const persisted = await (await page.request.get(`/api/v1/products/${product.id}`)).json();
  expect(persisted).toMatchObject({
    price_amount: '599.50',
    cost_amount: '199.25',
    price_currency: 'INR',
    sku: 'QA-BAND-001',
    category: 'Sports and outdoor fitness',
  });
  await page.goto(`/products/${product.id}/edit`);
  await page.getByLabel('Price', { exact: true }).fill('649.75');
  await page.getByRole('button', { name: 'Save product', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/products/${product.id}$`));
  await page.reload();
  expect(
    (await (await page.request.get(`/api/v1/products/${product.id}`)).json()).price_amount,
  ).toBe('649.75');
  await page.goto(`/catalog/${product.id}`);
  await expect(
    page.getByRole('heading', { name: '[QA SYNTHETIC] Resistance Band', exact: true }),
  ).toBeVisible();
  const readiness = await (
    await page.request.get(`/api/v1/catalog/products/${product.id}/readiness`)
  ).json();
  expect(readiness).toMatchObject({
    readiness: 'BLOCKED',
    blockers: ['listing_draft_required'],
    external_publication: 'DISABLED_IN_PR_SOS_01',
  });
  const economics = await (
    await page.request.get(`/api/v1/catalog/products/${product.id}/economics`)
  ).json();
  expect(economics.available).toBe(false); // UNKNOWN is never coerced to zero.
  await axe(page, info, 'catalog-detail');
  const noOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth <= innerWidth + 1,
  );
  expect(noOverflow, 'Catalog detail fits viewport').toBe(true);
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`/products/${product.id}$`));
  await page.goForward();
  await expect(page).toHaveURL(new RegExp(`/catalog/${product.id}$`));
});

test('QA-SMOKE-03 navigation, failed API recovery, logout and protected deep link', async ({
  page,
  evidence,
}, info) => {
  await signIn(page);
  for (const [route, heading] of [
    ['/catalog', 'Product master & listing preparation'],
    ['/operations/action-center', 'Action Center'],
    ['/operations/launch-readiness', 'Launch readiness'],
  ]) {
    await page.goto(route);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
  }
  const failure = '**/api/v1/products?*';
  evidence.expected_http_errors.push({ path: '/api/v1/products', status: 503 });
  await page.route(failure, (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: '{"detail":"Synthetic QA transport failure"}',
    }),
  );
  await page.goto('/catalog');
  await expect(page.getByRole('button', { name: 'Retry', exact: true })).toBeVisible();
  await page.unroute(failure);
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Retry', exact: true })).toHaveCount(0);
  await info.attach('recovery-context', {
    body: '503 intentionally injected in browser transport, then restored to canonical API.',
    contentType: 'text/plain',
  });
  const logout = await page.request.post('/api/v1/auth/logout', { data: {} });
  expect(logout.status()).toBe(204);
  await page.goto('/catalog/00000000-0000-0000-0000-000000000000');
  await expect(page).toHaveURL(/\/login$/);
  expect((await page.request.get('/api/v1/products')).status()).toBe(401);
  await axe(page, info, 'login');
});

test('QA-SMOKE-04 business goal to persisted plan; no discovery execution', async ({
  page,
}, info) => {
  await signIn(page);
  await page.goto('/intelligence/business-agent');
  const goal =
    'I have INR 300000 and want to start selling on Amazon India. Help me find a product in kids category.';
  await page.locator('textarea[name="goal"]').fill(goal);
  const created = page.waitForResponse(
    (r) =>
      r.url().endsWith('/api/v1/intelligence/business-agent/goals') &&
      r.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Create research goal', exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  const saved = await response.json();
  await page.getByRole('button', { name: 'Create versioned research plan', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Start run', exact: true })).toBeVisible();
  const plan = await (
    await page.request.get(`/api/v1/intelligence/business-agent/goals/${saved.id}/plan`)
  ).json();
  expect(plan.goal_id).toBe(saved.id);
  expect(plan.steps.length).toBeGreaterThan(0);
  const goals = await (await page.request.get('/api/v1/intelligence/business-agent/goals')).json();
  const persisted = goals.find((g) => g.id === saved.id);
  expect(JSON.stringify(persisted)).toContain('kids');
  expect(JSON.stringify(persisted)).toContain('300000');
  await page.reload();
  await expect(page.getByText(goal, { exact: true })).toBeVisible();
  await axe(page, info, 'goal-plan');
  await info.attach('journey-boundary', {
    body: 'Goal creation and planning only. Start run was NOT clicked. Product/supplier discovery, HUMAN selection and commercial decisions NOT EXECUTED.',
    contentType: 'text/plain',
  });
});
