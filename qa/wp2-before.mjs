import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { start, capture, finish } from './seller-browser-explore.mjs';
import { wp2Fixtures, wp2Owner } from './wp2-fixtures.mjs';
const session = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const witness = await fetch(session.origin + '/__qa/witness').then((r) => r.json());
if (
  !session.synthetic ||
  session.schema !== 'ALEMBIC_HEAD' ||
  witness.token !== session.token ||
  !witness.disposable
)
  throw Error('OWNED_QA_REQUIRED');
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
});
const run = await start(browser, session, { width: 1440, height: 900 }, 'wp2-before');
const page = run.page;
page.setDefaultTimeout(15000);
const report = { stage: 'setup', observations: [], status: 'RUNNING' };
try {
  await page.goto(session.origin + '/setup');
  await page.locator('#full-name').fill('[QA SYNTHETIC] WP2 Seller');
  await page.locator('#email').fill(wp2Owner.email);
  await page.locator('#password').fill(wp2Owner.password);
  await page.locator('#confirmation').fill(wp2Owner.password);
  await page.getByRole('button', { name: 'Create owner', exact: true }).click();
  await page.waitForURL('**/dashboard');
  await page.goto(session.origin + '/intelligence/business-agent');
  await expect(page.locator('textarea[name=goal]')).toBeVisible();
  await capture(run, 'empty-goals');
  await page.goto(session.origin + '/intelligence/product-opportunities');
  await page.getByRole('heading', { name: 'Your product research results', exact: true }).waitFor();
  report.observations.push({
    id: 'SE-BROWSER-008',
    reproduced: (await page.locator('main').innerText()).includes('Research complete'),
  });
  await capture(run, 'unexecuted-opportunities');
  const { items, api } = await wp2Fixtures(page, session.origin);
  const op = items[0];
  report.stage = 'research-and-selection';
  await page.goto(session.origin + '/intelligence/product-opportunities/' + op.id);
  await page.getByRole('button', { name: 'Load Trend evidence', exact: true }).click();
  await capture(run, 'absent-trend-projection');
  report.observations.push({
    id: 'SE-BROWSER-005',
    missing_feedback: !(await page.locator('main').innerText()).includes('No saved Trend'),
  });
  report.observations.push({
    id: 'SE-BROWSER-011',
    conversion_controls: await page.getByRole('button', { name: /catalog/i }).count(),
  });
  const base = `intelligence/product-opportunities/${op.id}/assessments/${op.assessment_id}/decision`;
  await api('post', base, { action: 'shortlist', rationale: 'Synthetic HUMAN selection test' });
  await api('post', base, { action: 'reject', rationale: 'Synthetic HUMAN rejection test' });
  const results = await api('get', 'intelligence/product-opportunities/research-results');
  report.observations.push({
    boundary: 'decision-current-state',
    selected_after_rejection: results.selected_candidate_ids.includes(op.id),
  });
  await page.reload();
  await capture(run, 'rejected-selection-projection');
  report.fixture = items;
  report.status = 'REPRODUCTION_COMPLETE';
} catch (error) {
  report.status = 'BLOCKED';
  report.safe_error = error.name;
} finally {
  await finish(run);
  await browser.close();
  await fs.writeFile(path.join(session.folder, 'wp2-before.json'), JSON.stringify(report, null, 2));
  await fs.writeFile(path.join(session.folder, 'stop.request'), 'Stop owned WP2 before session');
  console.log(JSON.stringify(report));
}
