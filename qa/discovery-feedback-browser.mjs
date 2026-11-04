// Rendering/interaction regression only. Every API response is synthetic and
// intercepted; this does not certify authentication, persistence, or live research.
import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { serve } from './server.mjs';

const folder = path.resolve(
  'tmp/qa-discovery-feedback',
  new Date().toISOString().replaceAll(':', '-'),
);
await fs.mkdir(folder, { recursive: true });
const server = await serve(0, 0, '4'); // No backend exists; interception is mandatory.
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
});
const goalId = '00000000-0000-4000-8000-000000000001';
const runId = '00000000-0000-4000-8000-000000000002';
const planId = '00000000-0000-4000-8000-000000000003';
const stamp = '2026-10-29T00:00:00Z';
const goal = {
  id: goalId,
  raw_goal: '[SYNTHETIC QA] Find products in the home and kitchen organization category.',
  status: 'NEEDS_REVIEW',
  structured_goal: { category: 'home and kitchen organization', marketplace: 'AMAZON_IN' },
  provenance: {},
  assumptions: [],
  unresolved_questions: [],
  extraction_version: 'synthetic-test',
  idempotency_key: 'synthetic-test',
  created_at: stamp,
  updated_at: stamp,
};
const blocked = {
  url: 'https://example.org/product/synthetic-organizer',
  domain: 'example.org',
  status: 'BLOCKED',
  reason_code: 'SOURCE_APPROVAL_REQUIRED',
  failure: 'External source approval is required before fetching.',
};
const cachedDetails = {
  queries: [1, 2, 3].map((n) => ({
    query: `Synthetic category query ${n}`,
    status: 'COMPLETED',
    provider_mode: 'REUSED_RECENT_SEARCH',
  })),
  fetches: [
    {
      ...blocked,
      status: 'COMPLETED',
      failure: '',
      reason_code: '',
      page_type: 'PRODUCT_DETAIL',
      eligible: true,
      reused: true,
    },
  ],
  rejected_results: [
    {
      url: blocked.url,
      eligible: false,
      reason: 'Explicit category constraint was not established by fetched product evidence.',
    },
  ],
  search_budget: { stop_reason: 'CACHED_QUERY_PLAN_EXHAUSTED' },
};
const approvalProfile = [
  {
    enabled: true,
    robots_policy: 'APPROVED',
    terms_status: 'APPROVED',
    access_classification: 'APPROVED',
    blocked_domains: [],
    approved_domains: ['example.org'],
  },
];
function run(details) {
  return {
    id: runId,
    goal_id: goalId,
    plan_id: planId,
    status: 'PARTIAL',
    idempotency_key: 'synthetic-test',
    correlation_id: 'synthetic-test',
    budget: {},
    usage: {},
    result: {},
    failure: { message: 'Historical no-product failure.' },
    checkpoint: { step_key: 'opportunity' },
    approvals: [],
    artifacts: [],
    findings: [],
    tool_invocations: [],
    candidates: [],
    steps: [
      {
        id: 'synthetic-step',
        key: 'opportunity',
        capability_id: 'product_opportunity.create',
        status: 'FAILED',
        attempt_count: 1,
        result: { details },
      },
    ],
  };
}
const result = {
  status: 'RUNNING',
  synthetic: true,
  backend: 'INTERCEPTED_API_ONLY',
  checks: [],
  axe: [],
  network: [],
  unexpected: [],
  pageErrors: [],
};
const check = (name, ok = true) => {
  result.checks.push({ name, status: ok ? 'PASS' : 'FAIL' });
  if (!ok) throw Error('BROWSER_ASSERTION_FAILED');
};
try {
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 390, height: 844 },
  ]) {
    const label = String(viewport.width);
    let state = 'cached';
    let retries = 0;
    const context = await browser.newContext({ viewport, serviceWorkers: 'block' });
    await context.tracing.start({ screenshots: true, snapshots: true });
    await context.route('**/*', async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.origin !== origin) {
        result.unexpected.push('NON_LOCAL_REQUEST_BLOCKED');
        return route.abort();
      }
      if (!url.pathname.startsWith('/api/')) return route.continue();
      const key = url.pathname.replace('/api/v1/', '');
      result.network.push({ viewport: label, method: request.method(), path: url.pathname });
      const details = state === 'cached' ? cachedDetails : { queries: [], fetches: [blocked] };
      const responses = {
        'auth/setup-status': { ownerExists: true },
        'auth/me': {
          id: 'synthetic-owner',
          fullName: '[SYNTHETIC QA] Seller',
          email: 'qa@example.invalid',
          role: 'owner',
        },
        'brands/active': { id: 'synthetic-brand', name: '[SYNTHETIC QA] Brand' },
        brands: { items: [], total: 0, page: 1, page_size: 100 },
        'system/maintenance': { enabled: false },
        'commerce-journeys/active': { journey: null },
        'intelligence/business-agent/goals': [goal],
        'intelligence/business-agent/capabilities': [],
        'intelligence/external/policy': {
          mode: 'LOCAL_FIXTURE',
          provider: 'synthetic-test',
          status: 'READY',
          search_enabled: false,
          fetch_enabled: false,
        },
        'intelligence/external/source-profiles': state === 'cached' ? approvalProfile : [],
        [`intelligence/business-agent/goals/${goalId}/plan`]: {
          id: planId,
          goal_id: goalId,
          version: 1,
          status: 'READY',
          planner: 'synthetic-test',
          plan_hash: 'synthetic-test',
          steps: [],
        },
        [`intelligence/business-agent/goals/${goalId}/runs/latest`]: run(details),
      };
      if (
        key === `intelligence/business-agent/runs/${runId}/retry` &&
        request.method() === 'POST'
      ) {
        retries++;
        return route.fulfill({ json: run(details) });
      }
      if (request.method() !== 'GET' || !(key in responses)) {
        result.unexpected.push(`${request.method()} ${url.pathname}`);
        return route.fulfill({
          status: 403,
          json: { detail: 'Synthetic harness denies unexpected request.' },
        });
      }
      return route.fulfill({ json: responses[key] });
    });
    const page = await context.newPage();
    page.on('pageerror', () => result.pageErrors.push(label));
    page.setDefaultTimeout(15000);
    const url = `${origin}/intelligence/business-agent?goal_id=${goalId}`;
    await page.goto(url);
    const review = page.locator('app-product-discovery-review');
    await expect(
      review.getByText('No new provider search was made.', { exact: false }),
    ).toBeVisible();
    check(`${label}: cached exhaustion and zero new provider requests explained`);
    await expect(
      page.getByRole('button', { name: 'Retry product discovery', exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Continue product discovery', exact: true }),
    ).toHaveCount(0);
    await expect(review.getByText(/Recorded source approvals are available/)).toBeVisible();
    check(`${label}: recorded approvals do not point to a nonexistent Continue control`);
    const summary = review.locator('summary');
    await summary.focus();
    await page.keyboard.press('Enter');
    await expect(review.getByText('Not eligible', { exact: true })).toBeVisible();
    await expect(
      review.getByText(/Explicit category constraint was not established/),
    ).toBeVisible();
    await expect(review.getByText('COMPLETED', { exact: true })).toBeVisible();
    check(`${label}: successful fetch and final category rejection are both visible`);
    const region = review.getByRole('region', { name: 'Discovery page outcomes' });
    await region.focus();
    await expect(region).toBeFocused();
    check(`${label}: keyboard can focus the scrollable outcomes table`);
    await page.keyboard.press('Shift+Tab');
    await expect(summary).toBeFocused();
    check(`${label}: reverse keyboard navigation returns to the disclosure`);
    check(
      `${label}: document has no horizontal overflow`,
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    );
    await review.scrollIntoViewIfNeeded();
    await page.screenshot({
      path: path.join(folder, `cached-rejection-${label}.png`),
      fullPage: true,
    });
    await page.addScriptTag({ path: path.resolve('node_modules/axe-core/axe.min.js') });
    const scan = await review.evaluate(async (element) => {
      const data = await window.axe.run(element);
      return {
        violations: data.violations.map(({ id, impact, nodes }) => ({
          id,
          impact,
          elements: nodes.map((node) => node.target),
        })),
        incomplete: data.incomplete.map(({ id }) => id),
      };
    });
    result.axe.push({ viewport: label, ...scan });
    check(
      `${label}: changed discovery state has zero axe violations`,
      scan.violations.length === 0,
    );
    // Retain full-scan incomplete findings. Expose every table cell in its
    // actual scroll container and independently test contrast, not hidden copies.
    const cellScans = [];
    for (const cell of await review.locator('th, td').all()) {
      await cell.scrollIntoViewIfNeeded();
      const data = await cell.evaluate(async (element) => {
        const owner = element.closest('.table-wrap').getBoundingClientRect();
        const box = element.getBoundingClientRect();
        const scan = await window.axe.run(element, {
          runOnly: { type: 'rule', values: ['color-contrast'] },
        });
        return {
          text: element.textContent.trim(),
          exposed: box.left >= owner.left - 1 && box.right <= owner.right + 1,
          violations: scan.violations.map(({ id }) => id),
          incomplete: scan.incomplete.map(({ id }) => id),
          passes: scan.passes.map(({ id }) => id),
        };
      });
      cellScans.push(data);
    }
    result.axe.push({ viewport: label, exposedTableCells: cellScans });
    check(
      `${label}: every table cell exposed and independently contrast-verified`,
      cellScans.every(
        (cell) =>
          cell.exposed &&
          !cell.violations.length &&
          !cell.incomplete.length &&
          cell.passes.includes('color-contrast'),
      ),
    );
    check(
      `${label}: no unresolved non-contrast incomplete findings`,
      scan.incomplete.every((id) => id === 'color-contrast'),
    );
    await page.screenshot({
      path: path.join(folder, `exposed-table-${label}.png`),
      fullPage: true,
    });
    await page.getByRole('button', { name: 'Retry product discovery', exact: true }).click();
    await expect.poll(() => retries).toBe(1);
    check(`${label}: retry targets the original run exactly once (intercepted, no execution)`);
    await page.reload();
    await expect(
      page.getByRole('button', { name: 'Retry product discovery', exact: true }),
    ).toBeVisible();
    check(
      `${label}: deep-link reload preserves the synthetic goal and retry state`,
      new URL(page.url()).searchParams.get('goal_id') === goalId && retries === 1,
    );
    state = 'approval';
    await page.reload();
    await expect(
      page.getByRole('button', { name: 'Continue product discovery', exact: true }),
    ).toBeVisible();
    const approve = review.getByRole('button', {
      name: 'Approve selected source for read-only research',
      exact: true,
    });
    await expect(approve).toBeDisabled();
    check(`${label}: genuine approval boundary still requires explicit HUMAN confirmations`);
    await review.scrollIntoViewIfNeeded();
    await page.screenshot({
      path: path.join(folder, `approval-required-${label}.png`),
      fullPage: true,
    });
    await context.tracing.stop({ path: path.join(folder, `trace-${label}.zip`) });
    await context.close();
  }
  check('No unexpected, external, or unapproved API requests', result.unexpected.length === 0);
  check('No uncaught browser errors', result.pageErrors.length === 0);
  result.status = 'PASS';
} catch (error) {
  result.status = 'FAIL';
  // This process contains only declared synthetic fixtures, never real sessions.
  result.failure = String(error.message).slice(0, 2000);
  result.checks.push({ name: 'Browser assertion or harness execution', status: 'FAIL' });
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
  await fs.writeFile(path.join(folder, 'report.json'), JSON.stringify(result, null, 2));
  console.log(
    JSON.stringify({
      folder,
      status: result.status,
      passed: result.checks.filter((row) => row.status === 'PASS').length,
      failed: result.checks.filter((row) => row.status === 'FAIL').length,
    }),
  );
}
process.exitCode = result.status === 'PASS' ? 0 : 1;
