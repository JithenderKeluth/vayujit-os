// WP2 end-to-end UI, with explicitly synthetic canonical fixtures and zero acquisition.
import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp2Fixtures, wp2Owner } from './wp2-fixtures.mjs';

const session = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const witness = await fetch(session.origin + '/__qa/witness').then((r) => r.json());
if (
  !session.synthetic ||
  session.schema !== 'ALEMBIC_HEAD' ||
  !witness.disposable ||
  witness.token !== session.token
)
  throw Error('OWNED_MIGRATION_BACKED_QA_REQUIRED');
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
});
const result = {
  token: session.token,
  synthetic: true,
  status: 'RUNNING',
  stage: 'setup',
  checks: [],
  axe: [],
};
const runs = [];
let acceptDialogs = true;
const check = (name, ok) => {
  result.checks.push({ name, status: ok ? 'PASS' : 'FAIL' });
  if (!ok) throw Error('ASSERTION_FAILED');
};
try {
  const desktop = await start(browser, session, { width: 1440, height: 900 }, 'wp2-desktop');
  runs.push(desktop);
  const page = desktop.page;
  page.setDefaultTimeout(15000);
  page.on('dialog', (dialog) => (acceptDialogs ? dialog.accept() : dialog.dismiss()));
  await page.goto(session.origin + '/setup');
  await page.locator('#full-name').fill('[QA SYNTHETIC] WP2 Seller');
  await page.locator('#email').fill(wp2Owner.email);
  await page.locator('#password').fill(wp2Owner.password);
  await page.locator('#confirmation').fill(wp2Owner.password);
  await page.getByRole('button', { name: 'Create owner', exact: true }).click();
  await page.waitForURL('**/dashboard');
  result.stage = 'empty goals and goal creation';
  await page.goto(session.origin + '/intelligence/research');
  await expect(
    page.getByRole('heading', { name: 'No saved goals yet', exact: true }),
  ).toBeVisible();
  await capture(desktop, 'empty-saved-goals');
  check('New seller sees truthful empty saved research', true);
  await page.goto(session.origin + '/intelligence/product-opportunities');
  await expect(page.getByText('Research not started', { exact: true })).toBeVisible();
  check(
    'Empty opportunities do not claim research completion',
    !(await page.locator('main').innerText()).includes('RESEARCH COMPLETE'),
  );
  await capture(desktop, 'research-not-started');
  await page.goto(session.origin + '/intelligence/research');
  await page.getByRole('link', { name: 'Create a research goal', exact: true }).click();
  const goalInput = page.locator('textarea[name=goal]');
  await goalInput.fill('abc');
  await page.getByRole('button', { name: 'Create research goal', exact: true }).click();
  await expect(
    page.getByText('Enter at least five characters describing the outcome you want.', {
      exact: true,
    }),
  ).toBeVisible();
  check('Invalid short goal remains visible and rejected', true);
  await goalInput.fill(
    'Find products in kids category for Amazon India with INR 300000. Synthetic local QA only.',
  );
  const goalWait = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().endsWith('/business-agent/goals'),
  );
  await page.getByRole('button', { name: 'Create research goal', exact: true }).click();
  const goal = await (await goalWait).json();
  await page.getByRole('button', { name: 'Create versioned research plan', exact: true }).click();
  await expect(page.getByText(/Plan v1/).first()).toBeVisible();
  check('UI goal and versioned plan persist', true);
  await capture(desktop, 'goal-plan-guidance');
  const api = async (method, suffix, data) => {
    const r = await page.request[method](session.origin + '/api/v1/' + suffix, { data });
    if (!r.ok()) throw Error('CANONICAL_FIXTURE_REJECTED');
    return r.json();
  };
  const run = await api('post', `intelligence/business-agent/goals/${goal.id}/runs`, {
    idempotency_key: 'wp2-zero-provider-run',
    max_steps: 1,
    max_provider_calls: 0,
    max_elapsed_seconds: 10,
  });
  check(
    'Fixture cohort run is QUEUED with zero provider budget and is not executed',
    run.status === 'QUEUED',
  );
  const { items } = await wp2Fixtures(page, session.origin, run.id);
  const [first, second] = items;
  await api('post', 'brands', {
    name: '[QA SYNTHETIC] WP2 Brand',
    tagline: 'Disposable local QA only',
  });
  result.stage = 'opportunity list and comparison';
  const listUrl = session.origin + `/intelligence/product-opportunities?goal_id=${goal.id}`;
  await page.goto(listUrl);
  await expect(page.getByRole('heading', { name: first.name, exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: second.name, exact: true })).toBeVisible();
  check('Two exact synthetic identities appear under their original goal', true);
  await page.getByRole('button', { name: 'Add to comparison', exact: true }).nth(0).click();
  await page.getByRole('button', { name: 'Add to comparison', exact: true }).nth(0).click();
  await page.getByRole('button', { name: 'Compare selected products', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Evidence-backed comparison', exact: true }),
  ).toBeVisible();
  check(
    'Missing-evidence alternatives compare without a fabricated rank',
    (await page.locator('.comparison-panel').innerText()).includes('NOT_COMPARABLE'),
  );
  await capture(desktop, 'not-comparable-alternatives');
  result.axe.push(await axe(desktop, 'comparison'));
  await page.goto(
    session.origin + `/intelligence/product-opportunities/${first.id}?goal_id=${goal.id}`,
  );
  const actions = page.locator('app-opportunity-next-actions');
  await expect(
    actions.getByText('Not selected. Review the evidence before deciding.', { exact: true }),
  ).toBeVisible();
  result.stage = 'research feedback';
  for (const name of [
    'Load Trend evidence',
    'Load competition evidence',
    'Load customer evidence',
    'Load supplier evidence',
    'Load economics',
    'Load risk evidence',
  ]) {
    const button = page.getByRole('button', { name, exact: true });
    await expect(button).toBeVisible();
    await button.click();
    await expect(
      page.getByText(/No saved assessment exists for this evidence area/).first(),
    ).toBeVisible();
  }
  check(
    'Absent saved evidence has actionable feedback and retains product identity',
    (await page.getByRole('heading', { name: first.name, exact: true, level: 1 }).count()) === 1,
  );
  await capture(desktop, 'research-gaps-feedback');
  result.axe.push(await axe(desktop, 'research-insufficient-evidence'));
  result.stage = 'HUMAN select reject revisit';
  acceptDialogs = false;
  await actions.getByRole('button', { name: 'Reject this product', exact: true }).click();
  acceptDialogs = true;
  check(
    'Cancelled rejection creates no decision',
    (await api('get', `intelligence/product-opportunities/${first.id}/decisions`)).length === 0,
  );
  await actions
    .getByRole('button', { name: 'Select for further investigation', exact: true })
    .click();
  await expect(
    actions.getByText('Selected for further investigation.', { exact: true }),
  ).toBeVisible();
  const selected = await api('get', `intelligence/product-opportunities/${first.id}/decisions`);
  check(
    'HUMAN selection recorded with exact assessment',
    selected[0].assessment_id === first.assessment_id,
  );
  await actions.getByRole('button', { name: 'Reject this product', exact: true }).click();
  await expect(
    actions.getByText('Rejected. History is retained; select again only after explicit review.', {
      exact: true,
    }),
  ).toBeVisible();
  const afterReject = await api(
    'get',
    `intelligence/product-opportunities/research-results?goal_id=${goal.id}`,
  );
  check(
    'Rejection revokes current selection',
    !afterReject.selected_candidate_ids.includes(first.id),
  );
  await capture(desktop, 'rejection-history');
  await page.reload();
  await expect(
    actions.getByText('Rejected. History is retained; select again only after explicit review.', {
      exact: true,
    }),
  ).toBeVisible();
  await actions
    .getByRole('button', { name: 'Select for further investigation', exact: true })
    .click();
  await expect(
    actions.getByText('Selected for further investigation.', { exact: true }),
  ).toBeVisible();
  check(
    'Explicit reselection appends rather than overwrites history',
    (await api('get', `intelligence/product-opportunities/${first.id}/decisions`)).length === 3,
  );
  result.stage = 'Catalog confirmation and persistence';
  await actions.getByText('Prepare this selected product in Catalog', { exact: true }).click();
  await actions
    .locator('select[name=catalogBrand]')
    .selectOption({ label: '[QA SYNTHETIC] WP2 Brand' });
  await expect(
    actions.getByRole('button', { name: 'Create or open Catalog draft', exact: true }),
  ).toBeDisabled();
  check('Catalog requires explicit local-draft confirmation', true);
  await actions.locator('input[name=confirmCatalog]').check();
  const conversionPattern = `**/catalog/opportunities/${first.id}/convert`;
  await page.route(conversionPattern, (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Injected synthetic QA failure' }),
    }),
  );
  await actions.getByRole('button', { name: 'Create or open Catalog draft', exact: true }).click();
  await expect(actions.getByRole('alert')).toContainText('Catalog draft not confirmed');
  check(
    'Injected conversion failure preserves product and decision context',
    await page.getByRole('heading', { name: first.name, exact: true, level: 1 }).isVisible(),
  );
  await capture(desktop, 'conversion-failure-recovery');
  await page.unroute(conversionPattern);
  await actions.getByRole('button', { name: 'Reload decision', exact: true }).click();
  await expect(
    actions.getByRole('button', { name: 'Create or open Catalog draft', exact: true }),
  ).toBeEnabled();
  const conversionWait = page.waitForResponse(
    (r) =>
      r.request().method() === 'POST' && /\/catalog\/opportunities\/.+\/convert$/.test(r.url()),
  );
  await actions.getByRole('button', { name: 'Create or open Catalog draft', exact: true }).click();
  const converted = await (await conversionWait).json();
  await expect(
    actions.getByRole('link', { name: 'Open saved Catalog product', exact: true }),
  ).toBeVisible();
  check(
    'Catalog conversion preserves canonical opportunity and HUMAN lineage',
    converted.lineage.opportunity_id === first.id &&
      converted.lineage.assessment_id === first.assessment_id &&
      converted.product.price_amount === null,
  );
  await actions.getByRole('link', { name: 'Open saved Catalog product', exact: true }).click();
  await page.waitForURL('**/catalog/' + converted.product.id);
  await expect(page.getByRole('heading', { name: first.name, exact: true })).toBeVisible();
  await capture(desktop, 'converted-catalog');
  await page.reload();
  check(
    'Catalog refresh retains exact product',
    page.url().endsWith('/catalog/' + converted.product.id),
  );
  await page.goto(
    session.origin + `/intelligence/product-opportunities/${first.id}?goal_id=${goal.id}`,
  );
  await expect(
    actions.getByRole('link', { name: 'Continue toward suppliers', exact: true }),
  ).toBeVisible();
  await actions.getByRole('link', { name: 'Continue toward suppliers', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Find suppliers for this product', exact: true }),
  ).toBeEnabled();
  check(
    'Selected product continues toward suppliers with exact context',
    page.url().includes(first.id),
  );
  await capture(desktop, 'supplier-handoff-no-acquisition');
  result.stage = 'mobile saved research and exact scope';
  const mobile = await start(browser, session, { width: 390, height: 844 }, 'mobile');
  runs.push(mobile);
  const mp = mobile.page;
  mp.setDefaultTimeout(15000);
  mp.on('dialog', (d) => d.accept());
  await mp.goto(session.origin + '/login');
  await mp.locator('#email').fill(wp2Owner.email);
  await mp.locator('#password').fill(wp2Owner.password);
  await mp.getByRole('button', { name: 'Sign in', exact: true }).click();
  await mp.waitForURL('**/dashboard');
  await mp.goto(session.origin + '/intelligence/research');
  await expect(
    mp.getByRole('link', { name: 'Open goal, plan and research', exact: true }),
  ).toBeVisible();
  await capture(mobile, 'saved-goals');
  result.axe.push(await axe(mobile, 'saved-research'));
  await mp.getByRole('link', { name: "Review this goal's opportunities", exact: true }).click();
  await expect(mp.getByRole('heading', { name: first.name, exact: true })).toBeVisible();
  check('Mobile saved goal opens its scoped opportunities', mp.url().includes(goal.id));
  await mp.goto(
    session.origin + `/intelligence/product-opportunities/${first.id}?goal_id=${goal.id}`,
  );
  const ma = mp.locator('app-opportunity-next-actions');
  await expect(ma.getByText('Selected for further investigation.', { exact: true })).toBeVisible();
  await capture(mobile, 'selected-decision');
  result.axe.push(await axe(mobile, 'selected-product'));
  await ma.getByRole('button', { name: 'Reject this product', exact: true }).focus();
  await mp.keyboard.press('Tab');
  check(
    'Keyboard navigation moves from rejection to supplier handoff',
    (await mp.locator(':focus').innerText()).includes('Continue toward suppliers'),
  );
  await mp.keyboard.press('Shift+Tab');
  check(
    'Reverse keyboard returns to reject action',
    (await mp.locator(':focus').innerText()).includes('Reject this product'),
  );
  await mp.goto(
    session.origin + `/intelligence/product-opportunities/${second.id}?goal_id=${goal.id}`,
  );
  await expect(
    ma.getByText('Not selected. Review the evidence before deciding.', { exact: true }),
  ).toBeVisible();
  check('Switching to an unselected alternative never inherits prior selection', true);
  await mp.goBack();
  await expect(ma.getByText('Selected for further investigation.', { exact: true })).toBeVisible();
  await mp.reload();
  check('Back and refresh preserve original selected opportunity', mp.url().includes(first.id));
  await mp.goto(session.origin + `/catalog/${converted.product.id}`);
  await expect(mp.getByRole('heading', { name: first.name, exact: true })).toBeVisible();
  await capture(mobile, 'catalog-saved-product');
  await page.goto(session.origin + `/intelligence/business-agent?goal_id=${goal.id}`);
  await page.getByRole('button', { name: 'Prepare a revised goal', exact: true }).click();
  await expect(goalInput).toBeFocused();
  check(
    'Goal revision prepares a new draft without changing persisted goal',
    (await api('get', `intelligence/business-agent/goals/${goal.id}`)).raw_goal === goal.raw_goal,
  );
  result.fixture = {
    goal_id: goal.id,
    opportunity_ids: items.map((x) => x.id),
    product_id: converted.product.id,
  };
  result.status = 'PASS_BOUNDED_LOCAL_WP2';
} catch (error) {
  if (runs.length) {
    try {
      await capture(runs[runs.length - 1], 'failure-' + result.stage);
    } catch {
      /* keep original failure */
    }
  }
  result.status = 'FAIL';
  result.safe_error =
    error.name === 'TimeoutError' ? 'BROWSER_TIMEOUT' : 'ASSERTION_OR_BROWSER_FAILED';
} finally {
  for (const run of runs) {
    try {
      await finish(run);
    } catch {
      result.trace_finalization_failed = true;
    }
  }
  await browser.close();
  await fs.writeFile(
    path.join(session.folder, 'wp2-browser.json'),
    JSON.stringify(result, null, 2),
  );
  await fs.writeFile(path.join(session.folder, 'stop.request'), 'Stop owned WP2 runtime');
  console.log(
    JSON.stringify({
      status: result.status,
      stage: result.stage,
      passed: result.checks.filter((c) => c.status === 'PASS').length,
      failed: result.checks.filter((c) => c.status === 'FAIL').length,
      report: path.join(session.folder, 'wp2-browser.json'),
    }),
  );
  process.exitCode = result.status === 'PASS_BOUNDED_LOCAL_WP2' ? 0 : 1;
}
