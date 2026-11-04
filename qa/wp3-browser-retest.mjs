import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { start, capture, finish, axe } from './seller-browser-explore.mjs';
import { wp3Product, wp3Economics, wp3Owner } from './wp3-fixtures.mjs';
import { wp3UnexpectedSignals } from './wp3-reporting.mjs';

const session = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
if (!session.synthetic || session.schema !== 'ALEMBIC_HEAD' || session.status !== 'READY')
  throw Error('WP3_DISPOSABLE_SESSION_REQUIRED');
const witness = await fetch(session.origin + '/__qa/witness').then((r) => r.json());
if (!witness.disposable || witness.token !== session.token) throw Error('WP3_WITNESS_REQUIRED');
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
});
const runs = [];
const result = {
  token: session.token,
  status: 'RUNNING',
  synthetic: true,
  checks: [],
  observations: [],
  ids: {},
};
async function exposeContrast(run, scan) {
  const rows = [];
  for (const rule of scan.incomplete.filter((item) => item.id === 'color-contrast')) {
    for (const node of rule.nodes) {
      const selector = node.target.length === 1 ? node.target[0] : null;
      if (typeof selector !== 'string') {
        rows.push({ target: node.target, status: 'MANUAL_REVIEW_REQUIRED' });
        continue;
      }
      const target = run.page.locator(selector);
      if ((await target.count()) !== 1) {
        rows.push({ target: node.target, status: 'AMBIGUOUS_NOT_TESTED' });
        continue;
      }
      await target.evaluate((el) => el.scrollIntoView({ block: 'center', inline: 'center' }));
      const exposed = await target.evaluate(async (el) => {
        const result = await window.axe.run(el, {
          runOnly: { type: 'rule', values: ['color-contrast'] },
        });
        return {
          violations: result.violations,
          incomplete: result.incomplete,
          passes: result.passes.length,
        };
      });
      rows.push({
        target: node.target,
        ...exposed,
        status:
          exposed.violations.length || exposed.incomplete.length
            ? 'REVIEW_REQUIRED'
            : 'PASS_EXPOSED_NODE',
      });
    }
  }
  return rows;
}
async function check(name, action) {
  try {
    await action();
    result.checks.push({ name, status: 'PASS' });
  } catch (error) {
    result.checks.push({ name, status: 'FAIL', error: error.message.slice(0, 1500) });
    throw error;
  }
}
try {
  const desktop = await start(browser, session, { width: 1440, height: 900 }, 'wp3-after-desktop');
  runs.push(desktop);
  const page = desktop.page;
  page.setDefaultTimeout(15000);
  page.on('dialog', (d) => d.accept());
  await page.goto(session.origin + '/setup');
  await page.locator('#full-name').fill('[QA SYNTHETIC] WP3 Seller');
  await page.locator('#email').fill(wp3Owner.email);
  await page.locator('#password').fill(wp3Owner.password);
  await page.locator('#confirmation').fill(wp3Owner.password);
  await page.getByRole('button', { name: 'Create owner', exact: true }).click();
  await page.waitForURL('**/dashboard');
  const { api, op, assessment, goal, brand } = await wp3Product(page, session.origin);
  result.ids = { opportunity: op.id, assessment: assessment.id, goal: goal.id };
  await check('013 primary Suppliers opens discovery, not sourcing decisions', async () => {
    await page.getByRole('link', { name: 'Suppliers', exact: true }).first().click();
    await page.waitForURL('**/intelligence/cross-marketplace');
    await expect(
      page.getByRole('heading', { name: 'Cross-marketplace Supplier Intelligence', exact: true }),
    ).toBeVisible();
    await capture(desktop, 'suppliers-primary-navigation');
  });
  await check('selected product to LOCAL_FIXTURE supplier with provenance', async () => {
    await page.goto(
      session.origin + `/intelligence/product-opportunities/${op.id}?goal_id=${goal.id}`,
    );
    await page
      .getByRole('button', { name: 'Select this product for supplier research', exact: true })
      .click();
    await page.getByRole('link', { name: 'Find suppliers', exact: true }).click();
    await expect(
      page.getByText('Local demo data — not live market evidence.', { exact: true }),
    ).toBeVisible();
    await page
      .getByRole('button', { name: 'Find suppliers for this product', exact: true })
      .click();
    await page.getByRole('button', { name: 'View supplier', exact: true }).click();
    const projected = await api(
      'get',
      `intelligence/suppliers/research-results?opportunity_id=${op.id}`,
    );
    result.ids.supplier = projected.suppliers[0].id;
    result.supplier = projected.suppliers[0];
    await capture(desktop, 'supplier-provenance');
  });
  await check(
    '007 persisted HUMAN shortlist refreshes canonical counts without reload',
    async () => {
      await page.getByRole('link', { name: 'Shortlist this supplier', exact: true }).click();
      await page.getByRole('button', { name: 'Evaluate current shortlist', exact: true }).click();
      await expect(page.locator('.metrics')).toContainText('Shortlists 1');
      await page.getByRole('button', { name: 'Shortlist for verification', exact: true }).click();
      await expect(
        page.getByRole('link', { name: "Assess this supplier's evidence", exact: true }),
      ).toBeVisible();
      await expect(page.locator('.metrics')).toContainText('Active contexts 1');
      result.metrics = await api('get', 'intelligence/supplier-shortlisting/operations');
      expect(result.metrics.shortlist_count).toBe(1);
      expect(result.metrics.integrity.decision_count).toBe(1);
      await capture(desktop, 'shortlist-counts');
    },
  );
  await check(
    'existing evidence assessment is discoverable and does not verify synthetic supplier',
    async () => {
      await page
        .getByRole('link', { name: "Assess this supplier's evidence", exact: true })
        .click();
      await expect(
        page.getByRole('button', { name: 'Assess existing evidence', exact: true }),
      ).toBeEnabled();
      const assessedWait = page.waitForResponse(
        (r) =>
          r.request().method() === 'POST' &&
          /\/contexts\/[^/]+\/assess$/.test(new URL(r.url()).pathname),
      );
      await page.getByRole('button', { name: 'Assess existing evidence', exact: true }).focus();
      await page.keyboard.press('Enter');
      const assessed = await (await assessedWait).json();
      expect(assessed.open_gaps).toBeGreaterThan(0);
      expect(assessed.readiness).not.toBe('SUFFICIENT');
      await capture(desktop, 'due-diligence-entry');
      result.dueDiligenceText = (await page.locator('main').innerText()).slice(0, 10000);
    },
  );
  const economics = await wp3Economics(api, op, assessment);
  result.economics = economics;
  await check(
    'canonical financial arithmetic remains precise, assumed and incomplete (not net profit)',
    async () => {
      const unit = economics.unit;
      expect(unit.per_unit_landed_cost).toBe('105.12500000');
      expect(unit.per_unit_selling_cost).toBe('25.10000000');
      expect(unit.per_unit_total_cost).toBe('130.22500000');
      expect(unit.per_unit_contribution).toBe('119.77500000');
      expect(unit.contribution_margin).toBe('0.47910000');
      expect(unit.capital_required).toBe('52562.50000000');
      expect(unit.selling_price_provenance).toBe('DETERMINISTIC_TEST');
      expect(unit.unknown_excluded.some((r) => r.key === 'tax')).toBe(true);
    },
  );
  const supplierUrl = `/intelligence/sourcing-economics?opportunity_id=${op.id}&supplier_id=${result.ids.supplier}`;
  await check(
    'supplier brief blocked until exact scoped economic inputs exist, with useful next action',
    async () => {
      await page.goto(session.origin + supplierUrl);
      await expect(
        page.getByText('Checking product and supplier context...', { exact: true }),
      ).toHaveCount(0);
      await expect(page.locator('section[aria-labelledby=scope-title]')).toContainText(op.name);
      await expect(
        page.getByRole('button', { name: 'Load decision brief', exact: true }),
      ).toBeDisabled();
      await expect(
        page.getByRole('link', { name: "Set up this supplier's economic inputs", exact: true }),
      ).toBeVisible();
      await capture(desktop, 'supplier-context-prerequisite');
      await page.locator('input[name=currency]').fill('INR');
      await page.locator('input[name=quantity]').fill('500');
      const savedWait = page.waitForResponse(
        (r) => r.request().method() === 'POST' && r.url().endsWith('/sourcing-economics/contexts'),
      );
      await page.getByRole('button', { name: 'Create context', exact: true }).click();
      const saved = (await (await savedWait).json()).context;
      expect(saved.product_opportunity_id).toBe(op.id);
      expect(saved.canonical_supplier_id).toBe(result.ids.supplier);
      result.ids.economicContext = saved.id;
      await expect(
        page.getByText('Saved evaluation restored. Missing commercial inputs remain UNKNOWN.', {
          exact: true,
        }),
      ).toBeVisible();
      await page.reload();
      await expect(
        page.getByText('Saved evaluation restored. Missing commercial inputs remain UNKNOWN.', {
          exact: true,
        }),
      ).toBeVisible();
      await page.getByRole('button', { name: 'Load decision brief', exact: true }).click();
      await expect(page.locator('.seller-cost-summary')).toContainText(
        'Cost and profitability are UNKNOWN',
      );
      await expect(page.locator('.unit-economics-summary')).toHaveCount(0);
      await capture(desktop, 'saved-supplier-context-unknown-not-product-substitution');
    },
  );
  const productUrl = `/intelligence/sourcing-economics?opportunity_id=${op.id}`;
  await check(
    '015/016 product-level summary, INR grouping, percentages, exact evidence retained',
    async () => {
      await page.goto(session.origin + productUrl);
      await expect(page.locator('.seller-cost-summary')).toContainText('47.91%');
      await expect(page.locator('.seller-cost-summary')).toContainText('₹52,562.50');
      await expect(page.locator('.seller-cost-summary')).toContainText('Product-level scenario');
      await expect(page.locator('.unit-economics-summary')).toContainText('₹119.78');
      const exact = page.getByText('Exact canonical decimal values (unrounded)', { exact: true });
      await exact.click();
      await expect(page.locator('.unit-economics-summary')).toContainText('119.77500000');
      await exact.click();
      await page.locator('.seller-cost-summary').scrollIntoViewIfNeeded();
      await capture(desktop, 'economic-summary');
      result.desktopHeight = await page.evaluate(() => document.documentElement.scrollHeight);
    },
  );
  await check(
    'original warning evidence remains keyboard discoverable, not parsed into financial facts',
    async () => {
      const summary = page.getByText('Review decision readiness, warnings and unknowns', {
        exact: true,
      });
      await summary.focus();
      await page.keyboard.press('Enter');
      await expect(
        page.getByRole('heading', { name: 'Decision readiness', exact: true }),
      ).toBeVisible();
      const note = page
        .locator('app-economic-evidence-note')
        .filter({ hasText: 'Commercial input is assumed' })
        .first();
      await expect(note).toBeVisible();
      await note.getByText('Original evidence detail', { exact: true }).click();
      await expect(note.locator('pre')).toContainText('100.125');
      await capture(desktop, 'original-evidence-preserved');
      result.desktopAxe = await axe(desktop, 'readiness-details-open');
      await note.getByText('Original evidence detail', { exact: true }).click();
      await summary.click();
    },
  );
  await check('006 Catalog conversion and authoritative INR currency survives reload', async () => {
    await page.goto(
      session.origin + `/intelligence/product-opportunities/${op.id}?goal_id=${goal.id}`,
    );
    const actions = page.locator('app-opportunity-next-actions');
    await actions.getByText('Prepare this selected product in Catalog', { exact: true }).click();
    await actions.locator('select[name=catalogBrand]').selectOption(brand.id);
    await actions.locator('input[name=confirmCatalog]').check();
    const wait = page.waitForResponse(
      (r) =>
        r.request().method() === 'POST' &&
        r.url().endsWith(`/catalog/opportunities/${op.id}/convert`),
    );
    await actions
      .getByRole('button', { name: 'Create or open Catalog draft', exact: true })
      .click();
    result.ids.product = (await (await wait).json()).product.id;
    await actions.getByRole('link', { name: 'Open saved Catalog product', exact: true }).click();
    await expect(page.locator('section[aria-labelledby=economics-title]')).toContainText(
      /Currency\s*INR/,
    );
    await page.reload();
    await expect(page.locator('section[aria-labelledby=economics-title]')).toContainText(
      /Currency\s*INR/,
    );
    const link = page.getByRole('link', { name: "Review this product's economics", exact: true });
    expect(await link.getAttribute('href')).toContain(op.id);
    await capture(desktop, 'catalog-currency-and-context');
  });
  await check(
    'canonical supplier to local pricing draft and seller-entered quotation, no dispatch',
    async () => {
      await page.goto(session.origin + `/intelligence/cross-marketplace?opportunity_id=${op.id}`);
      await page.getByRole('button', { name: 'View supplier', exact: true }).click();
      await page
        .getByRole('link', { name: 'Prepare local requirements and record quotes', exact: true })
        .click();
      await expect(page).toHaveURL(
        new RegExp(`/intelligence/sourcing\\?.*opportunity_id=${op.id}`),
      );
      expect(new URL(page.url()).searchParams.get('supplier_id')).toBe(result.ids.supplier);
      await expect(
        page.getByRole('button', { name: 'Confirm requirement', exact: true }),
      ).toBeEnabled();
      const wait = page.waitForResponse(
        (r) => r.request().method() === 'POST' && r.url().endsWith('/sourcing/requirements'),
      );
      await page.getByRole('button', { name: 'Confirm requirement', exact: true }).click();
      const r = await wait;
      expect(r.status()).toBe(201);
      expect(r.request().postDataJSON().product_id).toBe(result.ids.product);
      expect(r.request().postDataJSON().opportunity_id).toBeNull();
      const sourceId = (
        await api('get', `intelligence/cross-marketplace/suppliers/${result.ids.supplier}`)
      ).identity.supplier_ids[0];
      await page.locator('#rfqs input[type=checkbox]').first().check();
      const draftWait = page.waitForResponse(
        (r) => r.request().method() === 'POST' && r.url().endsWith('/sourcing/rfqs'),
      );
      await page.getByRole('button', { name: 'Prepare RFQ for review', exact: true }).click();
      const draft = (await (await draftWait).json()).rfq;
      expect(draft.dispatch_status).toBe('not_sent');
      expect(draft.approved_at).toBeNull();
      result.ids.rfq = draft.id;
      await expect(page.locator('select[name=saved-rfq]')).toHaveValue(draft.id);
      await page.locator('select[name=quote-supplier]').selectOption(sourceId);
      await page
        .locator('input[name=quote-reference]')
        .fill('[QA SYNTHETIC] WP3 quotation, not real terms');
      await page.locator('input[name=quote-price]').fill('100.125');
      await page.locator('input[name=quote-moq]').fill('10');
      const quoteWait = page.waitForResponse(
        (r) => r.request().method() === 'POST' && r.url().endsWith('/sourcing/quotes'),
      );
      await page.getByRole('button', { name: 'Record supplier quote', exact: true }).click();
      const quote = await (await quoteWait).json();
      expect(quote.supplier_id).toBe(sourceId);
      expect(quote.rfq_id).toBe(draft.id);
      expect(quote.unit_price).toBe(100.125);
      result.ids.quote = quote.id;
      const replayWait = page.waitForResponse(
        (r) => r.request().method() === 'POST' && r.url().endsWith('/sourcing/quotes'),
      );
      await expect(
        page.getByRole('button', { name: 'Record supplier quote', exact: true }),
      ).toBeEnabled();
      await page.getByRole('button', { name: 'Record supplier quote', exact: true }).click();
      expect((await (await replayWait).json()).id).toBe(quote.id);
      await expect(page.locator('#quotes')).toContainText('Validity UNKNOWN');
      await capture(desktop, 'local-quote-scoped-and-unverified');
      const savedUrl = page.url();
      await page.reload();
      await expect(page.locator('select[name=saved-rfq]')).toHaveValue(draft.id);
      await expect(page.locator('#quotes')).toContainText('[QA SYNTHETIC] WP3 quotation');
      expect(page.url()).toBe(savedUrl);
      const persistedDraft = await api('get', `intelligence/sourcing/rfqs/${draft.id}`);
      expect(persistedDraft.dispatch_status).toBe('not_sent');
      expect(persistedDraft.approved_at).toBeNull();
      result.quotesAxe = await axe(desktop, 'scoped-local-quote-reloaded');
    },
  );
  const mobile = await start(browser, session, { width: 390, height: 844 }, 'mobile');
  runs.push(mobile);
  await mobile.page.goto(session.origin + '/login');
  await mobile.page.locator('#email').fill(wp3Owner.email);
  await mobile.page.locator('#password').fill(wp3Owner.password);
  await mobile.page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await mobile.page.waitForURL('**/dashboard');
  await check(
    'mobile persisted economics, readable summary, no document overflow, keyboard links',
    async () => {
      await mobile.page.goto(session.origin + productUrl);
      await expect(mobile.page.locator('.seller-cost-summary')).toContainText('47.91%');
      const nav = mobile.page.locator('nav[aria-label="Sourcing evaluation sections"]');
      await nav.getByRole('link', { name: 'Review inputs', exact: true }).focus();
      await mobile.page.keyboard.press('Enter');
      expect(new URL(mobile.page.url()).hash).toBe('#context-title');
      await expect(
        mobile.page.getByRole('heading', { name: 'Sourcing context', exact: true }),
      ).toBeVisible();
      const size = await mobile.page.evaluate(() => ({
        width: innerWidth,
        scroll: document.documentElement.scrollWidth,
        height: document.documentElement.scrollHeight,
      }));
      expect(size.scroll).toBeLessThanOrEqual(size.width + 1);
      result.mobileSize = size;
      await capture(mobile, 'mobile-economics-after', true);
      result.mobileAxe = await axe(mobile, 'economics-mobile');
      result.exposedMobileContrast = await exposeContrast(mobile, result.mobileAxe);
      await capture(mobile, 'exposed-financial-table-contrast');
    },
  );
  await check(
    'mobile quotation deep link preserves exact saved draft and unverified quote',
    async () => {
      await mobile.page.goto(
        session.origin +
          `/intelligence/sourcing?opportunity_id=${op.id}&supplier_id=${result.ids.supplier}&rfq_id=${result.ids.rfq}`,
      );
      await expect(mobile.page.locator('select[name=saved-rfq]')).toHaveValue(result.ids.rfq);
      await expect(mobile.page.locator('#quotes')).toContainText('[QA SYNTHETIC] WP3 quotation');
      await expect(mobile.page.locator('#quotes')).toContainText('unverified');
      await capture(mobile, 'mobile-quote-context');
      result.mobileQuoteAxe = await axe(mobile, 'mobile-local-quote');
    },
  );
  await check(
    'invalid supplier context fails closed without another supplier or cost substitution',
    async () => {
      await page.goto(
        session.origin +
          `/intelligence/sourcing-economics?opportunity_id=${op.id}&supplier_id=11111111-1111-4111-8111-111111111111`,
      );
      await expect(page.locator('section[aria-labelledby=scope-title]')).toContainText(
        'no alternative was substituted',
      );
      await expect(
        page.getByRole('button', { name: 'Create context', exact: true }),
      ).toBeDisabled();
      await capture(desktop, 'invalid-supplier-context');
    },
  );
  await check('manual Catalog product stays distinct from a researched opportunity', async () => {
    const manual = await api('post', 'products', {
      brand_id: brand.id,
      name: '[QA SYNTHETIC] Manual WP3',
      slug: 'wp3-manual',
      product_type: 'physical',
      status: 'draft',
    });
    const projection = await api('get', `catalog/products/${manual.id}/economics`);
    expect(projection.available).toBe(false);
    expect(projection.opportunity_id).toBeNull();
    await page.goto(session.origin + `/catalog/${manual.id}`);
    await expect(page.locator('section[aria-labelledby=economics-title]')).toContainText(
      'not automatically a researched or fully costed product',
    );
    await capture(desktop, 'manual-product-lineage-gap');
    result.manualProduct = manual.id;
  });
  await check(
    'backend read failure is explicit and recovery restores the same economic scope',
    async () => {
      // Explicit browser fault injection only for this read. Main persisted journeys
      // above used unmocked APIs. No provider/approval behavior is simulated.
      const paths = [
        `/api/v1/intelligence/product-opportunities/${op.id}/decision-brief`,
        `/api/v1/commerce-journeys/${goal.id}/decision-brief`,
      ];
      const route = (url) => paths.includes(url.pathname);
      desktop.signals.expected_http_errors = paths.map((path) => ({ path, status: 503 }));
      await page.route(route, (r) =>
        r.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Synthetic QA read outage' }),
        }),
      );
      await page.goto(session.origin + productUrl);
      await expect(
        page.getByRole('button', { name: 'Retry decision brief', exact: true }),
      ).toBeVisible();
      await capture(desktop, 'economic-read-failure');
      await page.unroute(route);
      await page.getByRole('button', { name: 'Retry decision brief', exact: true }).click();
      await expect(page.locator('.seller-cost-summary')).toContainText(op.name);
      await expect(page.locator('.seller-cost-summary')).toContainText('47.91%');
      await capture(desktop, 'economic-read-recovery');
    },
  );
  await check(
    'explicit HUMAN keep-under-review persists; unknown/synthetic evidence cannot enable Proceed',
    async () => {
      const prepare = page.getByRole('button', {
        name: 'Prepare advisory assessment for review',
        exact: true,
      });
      if (await prepare.count()) await prepare.click();
      const actions = page.getByRole('group', {
        name: 'Explicit human decision options',
        exact: true,
      });
      await expect(actions.getByRole('button', { name: 'Proceed', exact: true })).toBeDisabled();
      const savedWait = page.waitForResponse(
        (r) =>
          r.request().method() === 'POST' &&
          r.url().endsWith(`/commerce-journeys/${goal.id}/decision`),
      );
      await actions.getByRole('button', { name: 'Keep under review', exact: true }).click();
      const saved = (await (await savedWait).json()).decision;
      expect(saved.provenance).toBe('HUMAN');
      expect(saved.decision).toBe('KEEP_UNDER_REVIEW');
      await expect(page.locator('.decision-control-panel')).toContainText('Your decision:');
      await page.reload();
      await expect(page.locator('.decision-control-panel')).toContainText('KEEP_UNDER_REVIEW');
      await capture(desktop, 'human-review-decision-persisted');
    },
  );
  await check('no unexpected Angular console, page, network or provider errors', async () => {
    for (const run of runs) {
      expect(wp3UnexpectedSignals(run.signals)).toEqual({
        console_errors: [],
        page_errors: [],
        failed_requests: [],
        denied_requests: [],
        server_errors: [],
      });
    }
  });
  result.status = 'COMPLETE';
} catch (error) {
  result.status = 'INCOMPLETE';
  result.error = error.message.slice(0, 1500);
  for (const run of runs) await capture(run, 'retest-blocker').catch(() => {});
} finally {
  for (const run of runs) await finish(run);
  await browser.close();
  await fs.writeFile(path.join(session.folder, 'wp3-retest.json'), JSON.stringify(result, null, 2));
  await fs.writeFile(path.join(session.folder, 'stop.request'), 'WP3 retest completed');
  console.log(
    JSON.stringify({
      status: result.status,
      token: session.token,
      passed: result.checks.filter((c) => c.status === 'PASS').length,
      failed: result.checks.filter((c) => c.status === 'FAIL').length,
      error: result.error,
    }),
  );
}
process.exitCode = result.status === 'COMPLETE' ? 0 : 1;
