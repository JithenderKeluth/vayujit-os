// Actual UI interactions + canonical persisted state; no external providers/workers.
import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect as baseExpect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Owner, wp3Api } from './wp3-fixtures.mjs';
const expect = baseExpect.configure({ timeout: 15000 });
const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const witness = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (
  s.qa_phase !== 'WP7A' ||
  !s.synthetic ||
  s.schema !== 'ALEMBIC_HEAD' ||
  !witness.disposable ||
  witness.token !== s.token
)
  throw Error('EXACT_APPROVED_WP7A_REQUIRED');
const report = {
  token: s.token,
  synthetic: true,
  status: 'RUNNING',
  checks: [],
  scans: [],
  database: [],
  injected: [],
  versions: {},
  historical_ads_502: 'UNREPRODUCED_CAUSE_UNCLASSIFIED',
  workers_executed: false,
};
const runs = [],
  browsers = [];
const persist = () =>
  fs.writeFile(path.join(s.folder, 'wp7a-browser.json'), JSON.stringify(report, null, 2));
const responseFor = (page, predicate) => page.waitForResponse(predicate).catch(() => null);
async function check(run, id, name, fn) {
  try {
    await fn();
    report.checks.push({ context: run.label, id, matrix_id: id[0], name, status: 'PASS' });
  } catch (e) {
    report.checks.push({
      context: run.label,
      id,
      matrix_id: id[0],
      name,
      status: 'FAIL',
      safe_error: e.message.slice(0, 1400),
    });
    await capture(run, 'FAILED-' + id).catch(() => {});
  }
  await persist();
}
async function snapshot(run, label) {
  const r = await run.page.request.get(s.origin + '/__qa/wp7a/state', {
    headers: { 'x-qa-token': s.token },
  });
  expect(r.status()).toBe(200);
  const data = await r.json();
  expect(data.token).toBe(s.token);
  report.database.push({ context: run.label, label, ...data });
  await persist();
  return data;
}
async function control(run, scenario, account_id) {
  const r = await run.page.request.post(s.origin + '/__qa/wp7a/control', {
    headers: { 'x-qa-token': s.token },
    data: { scenario, ...(account_id ? { account_id } : {}) },
  });
  expect(r.status()).toBe(200);
}
async function scan(run, label) {
  await capture(run, label, true);
  const result = await axe(run, label);
  report.scans.push({ context: run.label, ...result });
  expect(result.violations).toEqual([]);
}
async function login(run) {
  const p = run.page;
  await p.goto(s.origin + '/login');
  await p.locator('#email').fill(wp3Owner.email);
  await p.locator('#password').fill(wp3Owner.password);
  await p.getByRole('button', { name: 'Sign in', exact: true }).click();
  await p.waitForURL('**/dashboard');
}
async function research(run, api, label) {
  const p = run.page;
  let goal, first;
  await check(
    run,
    'B-01',
    'UI goal, plan, research initiation and persisted synthetic partial evidence',
    async () => {
      await p.goto(s.origin + '/intelligence/business-agent');
      await p.waitForLoadState('networkidle');
      const creator = p.locator('details.goal-creation');
      await expect(creator).toBeVisible();
      if ((await creator.getAttribute('open')) === null)
        await creator.locator(':scope > summary').click();
      await expect(p.locator('textarea[name=goal]')).toBeVisible();
      const text = `[QA SYNTHETIC] WP7A ${label}: I have INR 300000. Find 2 products in the Home & Kitchen category for Amazon India. Analyze customer reviews, demand and competition.`;
      await p.locator('textarea[name=goal]').fill(text);
      await p.getByText('Advanced research options', { exact: true }).click();
      await p.getByLabel('Include customer-feedback evidence', { exact: true }).check();
      await p.getByLabel('Include Trend Intelligence', { exact: true }).check();
      const created = responseFor(
        p,
        (r) =>
          r.url().endsWith('/business-agent/goals') &&
          r.request().method() === 'POST' &&
          r.status() === 201,
      );
      await p.getByRole('button', { name: 'Create research goal', exact: true }).click();
      goal = await (await created).json();
      const card = p
        .locator('.goal-card')
        .filter({ has: p.getByRole('heading', { name: text, exact: true }) });
      await card
        .getByRole('button', { name: 'Create versioned research plan', exact: true })
        .click();
      await control(run, 'PROVIDER_UNAVAILABLE');
      const started = responseFor(
        p,
        (r) => /\/runs\/[^/]+\/start$/.test(r.url()) && r.request().method() === 'POST',
      );
      await card.getByRole('button', { name: 'Start run', exact: true }).click();
      first = await (await started).json();
      expect(first.candidates.length).toBeGreaterThan(0);
      expect(first.status).toBe('PARTIAL');
      expect(first.steps.some((step) => step.status === 'COMPLETED')).toBe(true);
      await expect(card).toContainText(/Research|research/);
      await snapshot(run, 'B-01-created-partial');
    },
  );
  await check(
    run,
    'B-02',
    'Provider-unavailable persisted failure is visible with partial evidence and no fabricated verification',
    async () => {
      expect(first?.id).toBeTruthy();
      expect(first.steps.some((step) => step.result?.code === 'PROVIDER_UNAVAILABLE')).toBe(true);
      await expect(p.locator('.goal-card.selected')).toContainText(
        /needs attention|need attention|failed|blocker/i,
      );
      const state = await snapshot(run, 'B-02-offline-unavailable');
      expect(
        state.candidates.every((c) => c.tags.includes('LOCAL_DETERMINISTIC_RESEARCH_FIXTURE')),
      ).toBe(true);
      expect(state.candidates.every((c) => c.state !== 'verified')).toBe(true);
      await scan(run, 'research-partial-offline-provider');
    },
  );
  await check(
    run,
    'B-03',
    'Real retry after offline recovery, repeated retry, reload, evidence lineage and candidate identity',
    async () => {
      await control(run, 'NONE');
      expect(first?.id).toBeTruthy();
      const before = await snapshot(run, 'B-03-before-retry');
      const retry = p
        .locator('.goal-card.selected')
        .getByRole('button', { name: /Retry product discovery|Retry through existing runtime/ });
      const completed = responseFor(
        p,
        (r) => r.url().endsWith(`/runs/${first.id}/retry`) && r.request().method() === 'POST',
      );
      await retry.click();
      expect((await completed).status()).toBe(200);
      const retried = await api('get', `intelligence/business-agent/runs/${first.id}`);
      expect(
        retried.steps.filter((step) => step.result?.code === 'PROVIDER_UNAVAILABLE'),
      ).toHaveLength(0);
      for (let n = 0; n < 2; n++)
        await api('post', `intelligence/business-agent/runs/${first.id}/retry`, {});
      await p.reload();
      await expect(p.locator('.goal-card.selected')).toBeVisible();
      const after = await snapshot(run, 'B-03-after-retry');
      expect(after.candidates.map((c) => c.id).sort()).toEqual(
        before.candidates.map((c) => c.id).sort(),
      );
      expect(after.runs.filter((r) => r.goal_id === goal.id)).toHaveLength(1);
      await scan(run, 'research-retry-persisted');
    },
  );
  await check(
    run,
    'B-04',
    'Interrupted research response after server commit reconciles on reload without another run',
    async () => {
      const alternate = await api('post', 'intelligence/business-agent/goals', {
        raw_goal: `[QA SYNTHETIC] WP7A interrupted ${label}. Find 1 product in Home & Kitchen category for Amazon India.`,
        idempotency_key: `wp7a-interrupt-${label}`,
      });
      await api('post', `intelligence/business-agent/goals/${alternate.id}/plan`, {});
      await p.goto(s.origin + `/intelligence/business-agent?goal_id=${alternate.id}`);
      let committed;
      const pattern = '**/api/v1/intelligence/business-agent/runs/*/start';
      await p.route(
        pattern,
        async (route) => {
          const response = await route.fetch();
          committed = await response.json();
          report.injected.push({
            context: label,
            id: 'B-04',
            kind: 'COMMITTED_RESPONSE_LOSS',
            server_status: response.status(),
          });
          await route.abort('failed');
        },
        { times: 1 },
      );
      await p
        .locator('.goal-card.selected')
        .getByRole('button', { name: 'Start run', exact: true })
        .click();
      await expect(
        p.getByText('The Business Agent run could not be started.', { exact: true }),
      ).toBeVisible();
      expect(committed.id).toBeTruthy();
      await p.reload();
      await expect(p.locator('.goal-card.selected')).toContainText(/Research progress/);
      const state = await snapshot(run, 'B-04-response-loss-reconciled');
      expect(state.runs.filter((r) => r.goal_id === alternate.id)).toHaveLength(1);
      expect(state.runs.find((r) => r.id === committed.id)).toBeTruthy();
    },
  );
  await check(
    run,
    'B-05',
    'Saved and superseding goal navigation never substitutes another candidate context',
    async () => {
      await p.goto(s.origin + `/intelligence/product-opportunities?goal_id=${goal.id}`);
      for (const candidate of first.candidates)
        await expect(p.getByRole('heading', { name: candidate.name, exact: true })).toBeVisible();
      await p.reload();
      expect(new URL(p.url()).searchParams.get('goal_id')).toBe(goal.id);
      await p.goBack();
      await p.goForward();
      expect(new URL(p.url()).searchParams.get('goal_id')).toBe(goal.id);
      await scan(run, 'research-original-context');
    },
  );
  await check(
    run,
    'B-06',
    'Unsupported local category is a persisted no-candidates result, never HTTP 500 or unrelated fallback',
    async () => {
      const empty = await api('post', 'intelligence/business-agent/goals', {
        raw_goal: `[QA SYNTHETIC] WP7A no fixture ${label}. Find 1 product in sports and outdoor fitness category for Amazon India.`,
        idempotency_key: `wp7a-no-fixture-${label}`,
      });
      await api('post', `intelligence/business-agent/goals/${empty.id}/plan`, {});
      await p.goto(s.origin + `/intelligence/business-agent?goal_id=${empty.id}`);
      const card = p.locator('.goal-card.selected');
      const started = responseFor(
        p,
        (r) => /\/runs\/[^/]+\/start$/.test(r.url()) && r.request().method() === 'POST',
      );
      await card.getByRole('button', { name: 'Start run', exact: true }).click();
      const response = await started;
      expect(response.status()).toBe(200);
      const result = await response.json();
      expect(result.status).toBe('PARTIAL');
      expect(result.failure.code).toBe('NO_USEFUL_PRODUCT_CANDIDATES');
      expect(result.candidates).toEqual([]);
      await expect(card).toContainText('No local fixture matches');
      await p.reload();
      await expect(p.locator('.goal-card.selected')).toContainText('No local fixture matches');
      const state = await snapshot(run, 'B-06-no-fixture');
      expect(state.runs.filter((r) => r.goal_id === empty.id)).toHaveLength(1);
      await scan(run, 'research-no-local-candidates');
    },
  );
}
async function inventory(run, api, product, label) {
  const p = run.page;
  const item = await api('post', 'inventory/items', {
    product_id: product.id,
    internal_sku: product.sku,
    opening_quantity: 10,
    idempotency_key: 'wp7a-opening-' + label,
  });
  const url = s.origin + `/marketplaces/inventory?product_id=${product.id}`;
  const form = () => p.getByRole('form', { name: 'Human stock adjustment', exact: true });
  const open = async () => {
    await p.goto(url);
    await p.getByRole('button', { name: 'Adjust stock', exact: true }).click();
  };
  const fill = async (delta) => {
    await form().getByLabel('Delta', { exact: true }).fill(String(delta));
    await form()
      .getByLabel('Reason', { exact: true })
      .fill('[QA SYNTHETIC] counted ' + label);
  };
  await check(
    run,
    'G-01',
    'Human positive and negative adjustments preserve exact product, balance and persisted ledger',
    async () => {
      for (const delta of [3, -2]) {
        await open();
        await expect(form()).toContainText('Human review required');
        await fill(delta);
        await form().getByRole('button', { name: 'Record adjustment', exact: true }).click();
        await expect(form()).toHaveCount(0);
      }
      const state = await snapshot(run, 'G-01-adjusted');
      const row = state.inventory.find((r) => r.id === item.id);
      expect(row.quantity).toBe(11);
      expect(row.product_id).toBe(product.id);
      expect(row.variant_id).toBeNull();
      expect(
        state.movements.filter((m) => m.item_id === item.id).reduce((n, m) => n + m.delta, 0),
      ).toBe(11);
      await p.getByRole('button', { name: 'View ledger', exact: true }).click();
      await expect(
        p.getByRole('region', { name: 'Inventory movement ledger', exact: true }),
      ).toContainText(product.sku);
      await scan(run, 'inventory-human-ledger');
    },
  );
  await check(
    run,
    'G-02',
    'Zero and insufficient-stock inputs cannot create a stock movement',
    async () => {
      const before = await snapshot(run, 'G-02-before');
      await open();
      await fill(0);
      await form().getByRole('button', { name: 'Record adjustment', exact: true }).click();
      expect((await snapshot(run, 'G-02-zero')).movements.length).toBe(before.movements.length);
      await fill(-100);
      await form().getByRole('button', { name: 'Record adjustment', exact: true }).click();
      await expect(form()).toContainText('adjustment was rejected');
      expect((await snapshot(run, 'G-02-negative-rejected')).movements.length).toBe(
        before.movements.length,
      );
      await scan(run, 'inventory-rejected-negative');
    },
  );
  await check(
    run,
    'G-03',
    'Lost committed adjustment response and immediate retry never duplicate the movement; reload reconciles',
    async () => {
      await open();
      await fill(2);
      let body;
      await p.route(
        `**/api/v1/inventory/${item.id}/adjust`,
        async (route) => {
          body = route.request().postDataJSON();
          const response = await route.fetch();
          expect(response.status()).toBe(200);
          report.injected.push({
            context: label,
            id: 'G-03',
            kind: 'COMMITTED_RESPONSE_LOSS',
            server_status: response.status(),
          });
          await route.abort('failed');
        },
        { times: 1 },
      );
      await form().getByRole('button', { name: 'Record adjustment', exact: true }).click();
      await expect(form()).toContainText('adjustment was rejected');
      const committed = await snapshot(run, 'G-03-uncertain');
      expect(committed.inventory.find((r) => r.id === item.id).quantity).toBe(13);
      await form().getByRole('button', { name: 'Record adjustment', exact: true }).click();
      await expect(form()).toContainText('adjustment was rejected');
      expect((await snapshot(run, 'G-03-stale-retry')).movements.length).toBe(
        committed.movements.length,
      );
      const replay = await api('post', `inventory/${item.id}/adjust`, body);
      expect(replay.on_hand_quantity).toBe(13);
      await p.reload();
      await p.getByRole('button', { name: 'View ledger', exact: true }).click();
      await expect(
        p.getByRole('region', { name: 'Inventory movement ledger', exact: true }),
      ).toContainText('13');
      await scan(run, 'inventory-response-loss-reconciled');
    },
  );
  await check(
    run,
    'G-04',
    'Duplicate clicks and unauthenticated stock writes remain fail-closed',
    async () => {
      await open();
      await fill(1);
      await form().getByRole('button', { name: 'Record adjustment', exact: true }).dblclick();
      await expect(form()).toHaveCount(0);
      expect(
        (await snapshot(run, 'G-04-double-click')).inventory.find((r) => r.id === item.id).quantity,
      ).toBe(14);
      await p.goto(s.origin + '/products/' + product.id);
      await p.goBack();
      expect(new URL(p.url()).searchParams.get('product_id')).toBe(product.id);
      const anonymous = await run.context.browser().newContext();
      try {
        const denied = await anonymous.request.post(
          s.origin + `/api/v1/inventory/${item.id}/adjust`,
          {
            headers: { Origin: s.origin },
            data: {
              delta: 1,
              reason: '[QA SYNTHETIC] unauthorized',
              expected_version: 999,
              idempotency_key: 'wp7a-denied-' + label,
            },
          },
        );
        expect(denied.status()).toBe(401);
      } finally {
        await anonymous.close();
      }
    },
  );
  await check(
    run,
    'G-05',
    'Variant-specific adjustment and reload cannot move parent or sibling stock',
    async () => {
      const variants = [];
      for (const suffix of ['A', 'B']) {
        const variant = await api('post', `catalog/products/${product.id}/variants`, {
          variant_key: 'wp7a-' + suffix,
          title: '[QA SYNTHETIC] variant ' + suffix,
          sku: product.sku + '-' + suffix,
        });
        const stock = await api('post', 'inventory/items', {
          product_id: product.id,
          variant_id: variant.id,
          internal_sku: variant.sku,
          opening_quantity: suffix === 'A' ? 4 : 7,
          idempotency_key: 'wp7a-variant-' + label + suffix,
        });
        variants.push({ variant, stock });
      }
      await p.goto(url + '&sku=' + variants[0].variant.sku);
      await p.getByRole('button', { name: 'Adjust stock', exact: true }).click();
      await fill(-1);
      await form().getByRole('button', { name: 'Record adjustment', exact: true }).click();
      await expect(form()).toHaveCount(0);
      await p.reload();
      const state = await snapshot(run, 'G-05-variant-scope');
      expect(state.inventory.find((r) => r.id === variants[0].stock.id)).toMatchObject({
        variant_id: variants[0].variant.id,
        product_id: product.id,
        quantity: 3,
      });
      expect(state.inventory.find((r) => r.id === variants[1].stock.id).quantity).toBe(7);
      expect(state.inventory.find((r) => r.id === item.id).quantity).toBe(14);
      await scan(run, 'inventory-variant-reload');
    },
  );
}
async function marketplaces(run, api, label) {
  const p = run.page;
  const accounts = [];
  for (const marketplace of ['amazon', 'flipkart'])
    accounts.push(
      await api('post', 'marketplaces/accounts', {
        marketplace,
        display_name: `[QA SYNTHETIC] WP7A ${label} ${marketplace}`,
        seller_account_id: `qa3-wp7a-${label}-${marketplace}`,
        environment: 'sandbox',
        credentials: {},
      }),
    );
  await check(
    run,
    'H-01',
    'Both marketplace destinations with missing credentials remain disabled/unverified, never connected',
    async () => {
      await p.goto(s.origin + '/marketplaces/accounts');
      for (const account of accounts) {
        const row = p
          .locator('tr')
          .filter({ has: p.getByText(account.display_name, { exact: true }) });
        await expect(row).toContainText('AUTHORIZATION_REQUIRED');
        await expect(row).toContainText('UNVERIFIED');
        await expect(row).toContainText('SYNTHETIC');
        await row.getByRole('button', { name: 'Enable', exact: true }).click();
        await expect(
          p.getByText('Marketplace data is unavailable. Check the API connection and try again.', {
            exact: true,
          }),
        ).toBeVisible();
      }
      expect((await snapshot(run, 'H-01-missing')).accounts.every((a) => !a.enabled)).toBe(true);
      await scan(run, 'marketplace-missing-authority');
    },
  );
  await check(
    run,
    'H-02',
    'Expired, invalid and revoked synthetic authorization states persist without verified connection claims',
    async () => {
      for (const account of accounts)
        for (const [scenario, expected] of [
          ['EXPIRED', 'EXPIRED'],
          ['INVALID', 'DEGRADED'],
          ['REVOKED', 'AUTHORIZATION_REQUIRED'],
        ]) {
          await control(run, scenario, account.id);
          await p.reload();
          const row = p
            .locator('tr')
            .filter({ has: p.getByText(account.display_name, { exact: true }) });
          await expect(row).toContainText(expected);
          await expect(row).toContainText('Disabled');
          await expect(row).toContainText('UNVERIFIED');
          await snapshot(run, `H-02-${account.marketplace}-${scenario}`);
        }
      await scan(run, 'marketplace-revoked');
    },
  );
  await check(
    run,
    'H-03',
    'Read failure is explicit; real retry recovers without enabling synchronization/publication',
    async () => {
      const pattern = '**/api/v1/marketplaces/accounts';
      await p.route(
        pattern,
        (route) =>
          route.fulfill({ status: 503, json: { error_code: 'qa_offline_provider_unavailable' } }),
        { times: 1 },
      );
      await p.getByRole('button', { name: 'Refresh', exact: true }).click();
      await expect(p.locator('app-error-state')).toBeVisible();
      await p.getByRole('button', { name: 'Refresh', exact: true }).click();
      await expect(p.getByText(accounts[0].display_name, { exact: true }).first()).toBeVisible();
      expect((await snapshot(run, 'H-03-recovered')).accounts.every((a) => !a.enabled)).toBe(true);
      const invalid = await p.request.get(
        s.origin + '/api/v1/marketplaces/accounts/00000000-0000-0000-0000-000000000000',
      );
      expect(invalid.status()).toBe(404);
      for (const account of accounts) {
        const before = await api('get', `marketplaces/accounts/${account.id}/import-jobs`);
        for (const mode of ['SANDBOX', 'LIVE_READ_ONLY']) {
          const denied = await p.request.post(
            s.origin + `/api/v1/marketplaces/accounts/${account.id}/imports`,
            { data: { operation: 'catalog', mode, idempotency_key: 'wp7a-denial-' + label } },
          );
          expect(denied.status()).toBe(409);
          expect(denied.headers()['x-vayujit-external-write']).toBe('denied');
        }
        expect(await api('get', `marketplaces/accounts/${account.id}/import-jobs`)).toEqual(before);
      }
    },
  );
  await check(
    run,
    'H-04',
    'Expired login rejects protected marketplace UI/API; relogin restores only the same owner records',
    async () => {
      await control(run, 'EXPIRE_SESSION');
      await p.reload();
      await p.waitForURL(/\/login/);
      expect((await p.request.get(s.origin + '/api/v1/marketplaces/accounts')).status()).toBe(401);
      await login(run);
      await p.goto(s.origin + '/marketplaces/accounts');
      await expect(p.getByText(accounts[0].display_name, { exact: true }).first()).toBeVisible();
    },
  );
}
async function creative(run, api, brand, product, label) {
  const p = run.page;
  let generation, board;
  await check(
    run,
    'L-01',
    'Real local-only Video queue creates one version-pinned record; duplicate queue cannot invent provider output',
    async () => {
      await p.goto(s.origin + '/ai/video');
      await expect(p.getByRole('button', { name: 'Queue Video', exact: true })).toBeDisabled();
      await p.getByRole('combobox', { name: 'Brand', exact: true }).selectOption(brand.id);
      await p.getByRole('combobox', { name: 'Product', exact: true }).selectOption(product.id);
      const queued = responseFor(
        p,
        (r) => r.url().endsWith('/ai/video/queue') && r.request().method() === 'POST',
      );
      await p.getByRole('button', { name: 'Queue Video', exact: true }).click();
      expect((await queued).status()).toBe(202);
      generation = (await api('get', 'ai/video/generations')).find(
        (v) => v.product_id === product.id,
      );
      expect(generation.status).toBe('queued');
      await p.getByRole('button', { name: 'Queue Video', exact: true }).click();
      const state = await snapshot(run, 'L-01-local-queue');
      expect(state.videos.filter((v) => v.product_id === product.id)).toHaveLength(1);
      expect(state.videos.every((v) => !v.output)).toBe(true);
    },
  );
  await check(
    run,
    'L-02',
    'Caption blank/unsafe data validation and real content save/reload keep explicit HUMAN review',
    async () => {
      const row = p.locator('#videos tr').filter({ has: p.getByText(product.id, { exact: true }) });
      await expect(row).toHaveCount(1);
      await row.getByRole('button', { name: 'Open review', exact: true }).click();
      await expect(p.getByRole('button', { name: 'Add track', exact: true })).toBeDisabled();
      const locale = p.locator('#captions select');
      await expect(locale).toHaveAccessibleName(/^Locale/);
      await locale.selectOption('en-IN');
      await p
        .getByLabel('Caption text', { exact: true })
        .fill('[QA SYNTHETIC] <script>unsafe</script>');
      await p.getByRole('button', { name: 'Add track', exact: true }).click();
      await expect(
        p.getByText('Caption track could not be created safely.', { exact: true }),
      ).toBeVisible();
      await p
        .getByLabel('Caption text', { exact: true })
        .fill('[QA SYNTHETIC] WP7A caption ' + label);
      await p.getByRole('button', { name: 'Add track', exact: true }).click();
      await expect(p.getByText('Caption track created for review.', { exact: true })).toBeVisible();
      await expect(
        p.getByText('Caption track could not be created safely.', { exact: true }),
      ).toHaveCount(0);
      const captions = await api('get', `ai/video/generations/${generation.id}/captions`);
      expect(captions).toHaveLength(1);
      expect(captions[0].approval_state).toBe('pending_review');
      expect(captions[0].caption_text).toBe('[QA SYNTHETIC] WP7A caption ' + label);
      await scan(run, 'video-caption-error-recovery');
      await p.reload();
      expect((await api('get', `ai/video/generations/${generation.id}/captions`))[0].id).toBe(
        captions[0].id,
      );
    },
  );
  await check(
    run,
    'L-03',
    'Storyboard Add scene, save, version reload and stale write rejection preserve exact product context',
    async () => {
      board = await api('post', 'ai/video/storyboards', {
        brand_id: brand.id,
        product_id: product.id,
        scenes: [
          {
            stable_key: 'wp7a-' + label,
            scene_order: 1,
            scene_text: '[QA SYNTHETIC] initial scene',
            duration_seconds: 3,
          },
        ],
      });
      await p.reload();
      await p
        .locator('#storyboards .card')
        .filter({ has: p.getByText(board.id, { exact: false }) })
        .getByRole('button', { name: 'Open editor', exact: true })
        .click();
      const editor = p.locator('[aria-labelledby=storyboard-editor-title]');
      await editor.getByRole('button', { name: 'Add scene', exact: true }).click();
      await editor
        .getByLabel('On-screen text', { exact: true })
        .last()
        .fill('[QA SYNTHETIC] added scene ' + label);
      await editor.getByRole('button', { name: 'Save', exact: true }).focus();
      const saved = responseFor(
        p,
        (r) => r.url().endsWith('/storyboards/' + board.id) && r.request().method() === 'PUT',
      );
      await p.keyboard.press('Enter');
      expect((await saved).status()).toBe(200);
      const current = await api('get', 'ai/video/storyboards/' + board.id);
      // Editing a draft increments its concurrency token, not the approved
      // immutable storyboard version. Version cloning is a separate authority.
      expect(current.version).toBe(board.version);
      expect(current.row_version).toBeGreaterThan(board.row_version);
      expect(current.scenes).toHaveLength(2);
      expect(current.state).toBe('draft');
      const stale = await p.request.put(s.origin + '/api/v1/ai/video/storyboards/' + board.id, {
        data: { expected_row_version: board.row_version, scenes: board.scenes },
      });
      expect(stale.status()).toBe(409);
      await p.reload();
      await p
        .locator('#storyboards .card')
        .filter({ has: p.getByText(board.id, { exact: false }) })
        .getByRole('button', { name: 'Open editor', exact: true })
        .click();
      await expect(p.getByLabel('On-screen text', { exact: true }).last()).toHaveValue(
        '[QA SYNTHETIC] added scene ' + label,
      );
      await scan(run, 'storyboard-persisted-second-version');
    },
  );
  await check(
    run,
    'L-04',
    'Unavailable creative reads hide stale results and Retry restores canonical state',
    async () => {
      await p.route(
        '**/api/v1/ai/video/generations',
        (route) =>
          route.fulfill({ status: 503, json: { error_code: 'qa_offline_provider_unavailable' } }),
        { times: 1 },
      );
      await p.reload();
      await expect(
        p.getByText('Video data is unavailable. Check the authenticated API connection.', {
          exact: true,
        }),
      ).toBeVisible();
      await expect(
        p.locator('#videos').getByRole('button', { name: 'Open review', exact: true }),
      ).toHaveCount(0);
      await p.getByRole('button', { name: 'Retry', exact: true }).click();
      await expect(
        p.getByText('Video data is unavailable. Check the authenticated API connection.', {
          exact: true,
        }),
      ).toHaveCount(0);
      await expect(
        p.locator('#videos').getByRole('button', { name: 'Open review', exact: true }).first(),
      ).toBeVisible();
      await snapshot(run, 'L-04-provider-recovery');
    },
  );
  await check(
    run,
    'L-05',
    'Ads campaign preparation, missing prerequisites and historical-502 monitoring preserve HUMAN boundary',
    async () => {
      await p.goto(s.origin + '/ads/create');
      const campaignName = '[QA SYNTHETIC] WP6A WP7A ' + label;
      await p.getByLabel('Campaign name', { exact: true }).fill(campaignName);
      const account = p.locator('select[name=account_id]');
      await expect(account).toHaveAccessibleName(/^Account/);
      await expect(account).toHaveValue('');
      await p.getByRole('button', { name: 'Next', exact: true }).click();
      await p.getByRole('button', { name: 'Back', exact: true }).click();
      await expect(p.getByLabel('Campaign name', { exact: true })).toHaveValue(campaignName);
      for (let step = 0; step < 4; step++)
        await p.getByRole('button', { name: 'Next', exact: true }).click();
      const blocked = responseFor(
        p,
        (r) => r.url().endsWith('/ads/campaigns/preview') && r.request().method() === 'POST',
      );
      await p.getByRole('button', { name: 'Run server preview', exact: true }).click();
      expect((await blocked).status()).toBe(422);
      await expect(p.locator('main')).toContainText(
        'The request was rejected. Review the fields and try again.',
      );
      expect(await api('get', 'ads/campaigns')).toEqual([]);
      await p.goto(s.origin + '/ads/recovery');
      await expect(p.locator('main')).toContainText(/Recovery|recovery/);
      const catalog = await api('get', 'ads/recovery');
      expect(catalog.length).toBeGreaterThan(0);
      for (const failure of catalog) {
        expect(typeof failure.retryable).toBe('boolean');
        expect(Array.isArray(failure.recovery_actions)).toBe(true);
        await expect(
          p.getByRole('cell', { name: failure.failure_code, exact: true }),
        ).toBeVisible();
        await expect(
          p.getByRole('cell', { name: failure.safe_message, exact: true }),
        ).toBeVisible();
        expect(failure.observed).toBe(false);
      }
      await p.reload();
      await p.goBack();
      await p.goForward();
      await scan(run, 'ads-preparation-recovery-no-confirm');
      for (const route of ['ads/overview', 'ads/comparison', 'ads/campaigns'])
        expect((await p.request.get(s.origin + '/api/v1/' + route)).status()).toBe(200);
    },
  );
}
try {
  for (const channel of process.argv.includes('--focused') ? ['chrome'] : ['chrome', 'msedge']) {
    const browser = await chromium.launch({ channel, headless: true });
    browsers.push(browser);
    report.versions[channel] = browser.version();
    for (const width of process.argv.includes('--focused') ? [1440] : [1440, 390]) {
      const label = `wp7a-${channel}-${width}`;
      const run = await start(browser, s, { width, height: 900 }, label);
      runs.push(run);
      const p = run.page;
      p.setDefaultTimeout(15000);
      const setup = await p.request
        .get(s.origin + '/api/v1/auth/setup-status')
        .then((r) => r.json());
      if (!setup.ownerExists) {
        await p.goto(s.origin + '/setup');
        await p.locator('#full-name').fill('[QA SYNTHETIC] WP7A Owner');
        await p.locator('#email').fill(wp3Owner.email);
        await p.locator('#password').fill(wp3Owner.password);
        await p.locator('#confirmation').fill(wp3Owner.password);
        await p.getByRole('button', { name: 'Create owner', exact: true }).click();
        await p.waitForURL('**/dashboard');
      } else await login(run);
      const api = wp3Api(p, s.origin);
      const brand = await api('post', 'brands', { name: '[QA SYNTHETIC] WP7A ' + label });
      const product = await api('post', 'products', {
        brand_id: brand.id,
        name: '[QA SYNTHETIC] WP7A ' + label,
        sku: 'QA-' + label,
        product_type: 'physical',
        description: '[QA SYNTHETIC] Disposable WP7A product; no real market or supplier evidence.',
        price_amount: '100.25',
        price_currency: 'INR',
      });
      await api('post', `products/${product.id}/activate`, {});
      await research(run, api, label);
      await control(run, 'NONE');
      await inventory(run, api, product, label);
      await marketplaces(run, api, label);
      await creative(run, api, brand, product, label);
    }
  }
} catch (error) {
  report.startup_failure = {
    safe_code: /^WP3_FIXTURE_\d+_[a-z-]+$/.test(error.message)
      ? error.message
      : 'WP7A_BROWSER_SETUP_FAILED',
    raw_output_persisted: false,
  };
} finally {
  for (const run of runs) await finish(run);
  for (const browser of browsers) await browser.close();
  report.status =
    report.checks.length === (process.argv.includes('--focused') ? 20 : 80) &&
    report.checks.every((c) => c.status === 'PASS')
      ? 'PASS'
      : 'INCOMPLETE';
  await persist();
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP7A complete');
  console.log(
    JSON.stringify({
      token: s.token,
      status: report.status,
      passed: report.checks.filter((c) => c.status === 'PASS').length,
      failed: report.checks.filter((c) => c.status === 'FAIL').length,
    }),
  );
}
process.exitCode = report.status === 'PASS' ? 0 : 1;
