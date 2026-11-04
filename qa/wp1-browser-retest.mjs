// Bounded, synthetic, canonical-API + actual-UI replay. Start the signed host first.
import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';

const session = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
if (
  !/^[a-f0-9]{16}$/.test(session.token) ||
  session.status !== 'READY' ||
  !session.synthetic ||
  !/^http:\/\/127\.0\.0\.1:\d+$/.test(session.origin) ||
  session.schema !== 'ALEMBIC_HEAD'
)
  throw new Error('SIGNED_MIGRATION_BACKED_SESSION_REQUIRED');
const witness = await fetch(session.origin + '/__qa/witness').then((r) => r.json());
if (!witness.disposable || witness.token !== session.token)
  throw new Error('OWNED_WITNESS_REQUIRED');
const result = {
  token: session.token,
  status: 'RUNNING',
  synthetic: true,
  checks: [],
  axe: [],
  stage: 'launch',
};
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
});
const runs = [];
const check = (name, ok) => {
  result.checks.push({ name, status: ok ? 'PASS' : 'FAIL' });
  if (!ok) throw new Error('ASSERTION_FAILED');
};
const originNote = 'Contains synthetic fixture evidence — not live supplier verification.';
const credentials = { email: 'qa-phase2-owner@example.com', password: 'SyntheticWP1Only123!' };
try {
  const desktop = await start(browser, session, { width: 1440, height: 900 }, 'final-desktop');
  runs.push(desktop);
  const page = desktop.page;
  page.setDefaultTimeout(15000);
  result.stage = 'synthetic owner onboarding';
  await page.goto(session.origin + '/setup');
  await page.locator('#full-name').fill('[QA SYNTHETIC] WP1 Final Seller');
  await page.locator('#email').fill(credentials.email);
  await page.locator('#password').fill(credentials.password);
  await page.locator('#confirmation').fill(credentials.password);
  await page.getByRole('button', { name: 'Create owner', exact: true }).click();
  await page.waitForURL('**/dashboard');
  check('Authenticated synthetic owner onboarding', true);
  const api = async (method, url, data) => {
    const response = await page.request[method](session.origin + url, { data });
    if (!response.ok()) throw new Error('CANONICAL_FIXTURE_API_FAILED');
    return response.json();
  };
  result.stage = 'canonical fixture preparation';
  const op = await api('post', '/api/v1/intelligence/product-opportunities', {
    name: '[QA SYNTHETIC] WP1 Final Bottle',
    description: 'Synthetic reusable water bottle fixture for local seller-journey QA only.',
    product_concept: 'stainless steel insulated water bottles',
    category: 'Home & Kitchen',
    target_marketplace: 'AMAZON_IN',
    target_region: 'IN',
    origin: 'manual',
    notes: 'DETERMINISTIC_TEST; not live market evidence',
    idempotency_key: 'wp1-final-op',
  });
  const constraint = await api(
    'post',
    `/api/v1/intelligence/product-opportunities/${op.id}/constraints`,
    {
      available_capital: '300000',
      currency: 'INR',
      marketplace: 'AMAZON_IN',
      idempotency_key: 'wp1-final-constraint',
    },
  );
  const assessment = await api(
    'post',
    `/api/v1/intelligence/product-opportunities/${op.id}/assessments`,
    {
      constraint_version_id: constraint.id,
      evidence_state: 'insufficient_evidence',
      status: 'created',
      input_snapshot: { evidence_environment: 'DETERMINISTIC_TEST' },
    },
  );
  await api(
    'post',
    `/api/v1/intelligence/product-opportunities/${op.id}/assessments/${assessment.id}/score`,
    { idempotency_key: 'wp1-final-score' },
  );
  const goal = await api('post', '/api/v1/intelligence/business-agent/goals', {
    raw_goal: 'Research a water bottle with INR 300000 for Amazon India. Local synthetic QA only.',
    structured_goal: {
      marketplace: 'AMAZON_IN',
      category: 'Home & Kitchen',
      capital: 300000,
      currency: 'INR',
      product_opportunity_id: op.id,
    },
    provenance: { mode: 'LOCAL_FIXTURE', evidence_environment: 'DETERMINISTIC_TEST' },
    idempotency_key: 'wp1-final-goal',
  });
  await api('post', `/api/v1/intelligence/business-agent/goals/${goal.id}/plan`, {});
  result.stage = 'HUMAN product selection and synthetic discovery';
  await page.goto(session.origin + `/intelligence/product-opportunities/${op.id}`);
  await page
    .getByRole('button', { name: 'Select this product for supplier research', exact: true })
    .click();
  await page.getByRole('link', { name: 'Find suppliers', exact: true }).click();
  const find = page.getByRole('button', { name: 'Find suppliers for this product', exact: true });
  await expect(find).toBeEnabled();
  const discoveryWait = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().endsWith('/suppliers/research'),
  );
  await find.click();
  const discovery = await discoveryWait;
  const discovered = await discovery.json();
  check(
    'Discovery requests LOCAL_FIXTURE and performs zero external calls',
    discovery.ok() &&
      discovery.request().postDataJSON().mode === 'LOCAL_FIXTURE' &&
      discovered.result.external_calls === false,
  );
  await page.getByRole('button', { name: 'View supplier', exact: true }).click();
  const projection = await api(
    'get',
    `/api/v1/intelligence/suppliers/research-results?opportunity_id=${op.id}`,
  );
  const supplier = projection.suppliers[0];
  check(
    'Canonical accepted sources retain fixture markers',
    supplier.freshness.sources.length > 0 &&
      supplier.freshness.sources.every((s) => s.synthetic === true),
  );
  await capture(desktop, 'synthetic-discovery');
  await page.getByRole('link', { name: 'Shortlist this supplier', exact: true }).click();
  const evaluate = page.getByRole('button', { name: 'Evaluate current shortlist', exact: true });
  await expect(evaluate).toBeEnabled();
  await evaluate.click();
  await page.getByRole('button', { name: 'Shortlist for verification', exact: true }).click();
  await page.getByRole('link', { name: "Assess this supplier's evidence", exact: true }).click();
  result.stage = 'existing evidence assessment';
  const assess = page.getByRole('button', { name: 'Assess existing evidence', exact: true });
  await expect(assess).toBeEnabled();
  await expect(page.getByText(originNote, { exact: true })).toBeVisible();
  check(
    'Unassessed gaps stay UNKNOWN',
    (await page.locator('main').innerText()).includes('UNKNOWN — not assessed'),
  );
  await assess.scrollIntoViewIfNeeded();
  await capture(desktop, 'unassessed-synthetic');
  await assess.focus();
  const assessWait = page.waitForResponse(
    (r) => r.request().method() === 'POST' && /\/contexts\/.+\/assess$/.test(r.url()),
  );
  await page.keyboard.press('Enter');
  const assessed = await (await assessWait).json();
  check(
    'Assessment establishes gaps not false verification',
    assessed.open_gaps > 0 && assessed.readiness !== 'SUFFICIENT',
  );
  await page
    .getByRole('link', { name: 'Review economics and missing commercial inputs', exact: true })
    .click();
  await expect(page.getByText(originNote, { exact: true })).toBeVisible();
  check(
    'Assessment-to-economics preserves exact scope',
    page.url().includes(op.id) && page.url().includes(supplier.id),
  );
  result.stage = 'scoped economics persistence';
  await page.getByRole('link', { name: 'Set up economic inputs', exact: true }).click();
  await page.locator('input[name=currency]').fill('INR');
  await page.locator('input[name=quantity]').fill('100');
  const saveWait = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().endsWith('/sourcing-economics/contexts'),
  );
  await page.getByRole('button', { name: 'Create context', exact: true }).click();
  const saved = await (await saveWait).json();
  check(
    'Economics persists typed canonical identities',
    saved.context.product_opportunity_id === op.id &&
      saved.context.canonical_supplier_id === supplier.id,
  );
  await page
    .getByText('Saved evaluation restored. Missing commercial inputs remain UNKNOWN.', {
      exact: true,
    })
    .waitFor();
  const savedUrl = page.url();
  await page.reload();
  await expect(page.getByText(originNote, { exact: true })).toBeVisible();
  await expect(
    page.getByText('Saved evaluation restored. Missing commercial inputs remain UNKNOWN.', {
      exact: true,
    }),
  ).toBeVisible();
  check('Saved evaluation survives fresh document reload', page.url() === savedUrl);
  await capture(desktop, 'economics-restored-synthetic');
  result.axe.push(await axe(desktop, 'scoped-economics'));
  const mobile = await start(browser, session, { width: 390, height: 844 }, 'final-mobile');
  runs.push(mobile);
  const mp = mobile.page;
  mp.setDefaultTimeout(15000);
  result.stage = 'mobile persisted scope and keyboard';
  await mp.goto(session.origin + '/login');
  await mp.locator('#email').fill(credentials.email);
  await mp.locator('#password').fill(credentials.password);
  await mp.getByRole('button', { name: 'Sign in', exact: true }).click();
  await mp.waitForURL('**/dashboard');
  await mp.goto(savedUrl);
  await expect(mp.getByText(originNote, { exact: true })).toBeVisible();
  check('Mobile deep link restores the same economics artifact', mp.url() === savedUrl);
  await mp.locator('input[name=currency]').focus();
  await mp.keyboard.press('Tab');
  check(
    'Mobile keyboard follows currency to quantity',
    (await mp.locator(':focus').getAttribute('name')) === 'quantity',
  );
  await mp.keyboard.press('Shift+Tab');
  check(
    'Mobile reverse keyboard returns to currency',
    (await mp.locator(':focus').getAttribute('name')) === 'currency',
  );
  await capture(mobile, 'economics-restored-synthetic');
  result.axe.push(await axe(mobile, 'scoped-economics'));
  await mp.goto(
    session.origin +
      `/intelligence/due-diligence?opportunity_id=${op.id}&supplier_id=${supplier.id}`,
  );
  await expect(
    mp.getByRole('button', { name: 'Reassess existing evidence', exact: true }),
  ).toBeEnabled();
  await expect(mp.getByText(originNote, { exact: true })).toBeVisible();
  check('Mobile assessed state retains synthetic provenance', true);
  await capture(mobile, 'assessed-synthetic');
  result.axe.push(await axe(mobile, 'scoped-assessment'));
  await page.goto(
    session.origin +
      `/intelligence/due-diligence?opportunity_id=${op.id}&supplier_id=${supplier.id}`,
  );
  await page.getByRole('button', { name: 'Reassess existing evidence', exact: true }).waitFor();
  result.axe.push(await axe(desktop, 'scoped-assessment'));
  check(
    'No axe violations in the four final scoped scans',
    result.axe.every((a) => a.violations.length === 0),
  );
  result.fixture = {
    opportunity_id: op.id,
    supplier_id: supplier.id,
    economic_context_id: saved.context.id,
  };
  result.status = 'PASS_BOUNDED_LOCAL_WP1';
} catch (error) {
  result.status = 'FAIL';
  result.safe_error =
    error.name === 'TimeoutError' ? 'BROWSER_TIMEOUT' : 'BROWSER_OR_ASSERTION_FAILED';
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
    path.join(session.folder, 'wp1-final-browser.json'),
    JSON.stringify(result, null, 2),
  );
  await fs.writeFile(
    path.join(session.folder, 'stop.request'),
    'Stop only this owned WP1 final session.',
  );
  console.log(
    JSON.stringify({
      status: result.status,
      stage: result.stage,
      passed: result.checks.filter((c) => c.status === 'PASS').length,
      failed: result.checks.filter((c) => c.status === 'FAIL').length,
      report: path.join(session.folder, 'wp1-final-browser.json'),
    }),
  );
  process.exitCode = result.status === 'PASS_BOUNDED_LOCAL_WP1' ? 0 : 1;
}
