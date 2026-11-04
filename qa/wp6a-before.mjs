import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { start, capture, finish } from './seller-browser-explore.mjs';
import { wp3Owner } from './wp3-fixtures.mjs';
const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const witness = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (!s.synthetic || !witness.disposable || witness.token !== s.token || s.status !== 'READY')
  throw Error('APPROVED_QA_REQUIRED');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const run = await start(browser, s, { width: 1440, height: 900 }, 'wp6a-before');
const report = { token: s.token, status: 'RUNNING', observed: [] };
try {
  const p = run.page;
  await p.goto(s.origin + '/setup');
  await p.locator('#full-name').fill('[QA SYNTHETIC] WP6A Owner');
  await p.locator('#email').fill(wp3Owner.email);
  await p.locator('#password').fill(wp3Owner.password);
  await p.locator('#confirmation').fill(wp3Owner.password);
  await p.getByRole('button', { name: 'Create owner', exact: true }).click();
  await p.waitForURL('**/dashboard');
  for (const route of ['/ai/video', '/social', '/ads', '/ads/optimization']) {
    await p.goto(s.origin + route);
    await expect(p.locator('main [role="alert"]').first()).toBeVisible();
    await capture(run, route.replaceAll('/', '-'), true);
    report.observed.push({
      route,
      errors: await p.locator('main [role="alert"]').allTextContents(),
    });
  }
  report.status = 'COMPLETE';
} catch (e) {
  report.status = 'FAILED';
  report.error = e.message.slice(0, 1000);
} finally {
  await finish(run);
  await browser.close();
  await fs.writeFile(path.join(s.folder, 'wp6a-before.json'), JSON.stringify(report, null, 2));
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP6A before complete');
  console.log(JSON.stringify(report));
}
process.exitCode = report.status === 'COMPLETE' ? 0 : 1;
