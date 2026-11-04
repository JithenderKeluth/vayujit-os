import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Owner, wp3Api } from './wp3-fixtures.mjs';
const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const witness = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (
  !s.synthetic ||
  s.status !== 'READY' ||
  s.schema !== 'ALEMBIC_HEAD' ||
  witness.token !== s.token ||
  !witness.disposable
)
  throw Error('APPROVED_QA_REQUIRED');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const runs = [],
  report = { token: s.token, status: 'RUNNING', observations: [] };
try {
  const d = await start(browser, s, { width: 1440, height: 900 }, 'wp6-before-desktop');
  runs.push(d);
  const p = d.page;
  p.setDefaultTimeout(20000);
  await p.goto(s.origin + '/setup');
  await p.locator('#full-name').fill('[QA SYNTHETIC] WP6 Owner');
  await p.locator('#email').fill(wp3Owner.email);
  await p.locator('#password').fill(wp3Owner.password);
  await p.locator('#confirmation').fill(wp3Owner.password);
  await p.getByRole('button', { name: 'Create owner', exact: true }).click();
  await p.waitForURL('**/dashboard');
  const api = wp3Api(p, s.origin);
  const brand = await api('post', 'brands', { name: '[QA SYNTHETIC] WP6 Brand' });
  const product = await api('post', 'products', {
    brand_id: brand.id,
    name: '[QA SYNTHETIC] WP6 Draft',
    sku: 'QA-WP6-DRAFT',
    product_type: 'physical',
  });
  report.product = product.id;
  const m = await start(browser, s, { width: 390, height: 844 }, 'wp6-before-mobile');
  runs.push(m);
  await m.context.addCookies(await d.context.cookies());
  for (const route of ['/ai/studio/seo', '/ai/images', '/ai/video']) {
    await m.page.goto(s.origin + route);
    await expect(m.page.locator('app-business-entity-selectors').first()).toBeVisible();
    await capture(m, route.split('/').at(-1) + '-draft-prerequisite', true);
    report.observations.push({
      route,
      body: await m.page.locator('app-business-entity-selectors').first().innerText(),
      width: await m.page.evaluate(() => ({
        document: document.documentElement.scrollWidth,
        viewport: innerWidth,
      })),
    });
    if (route === '/ai/video') {
      await m.page.locator('#diagnostics').scrollIntoViewIfNeeded();
      await capture(m, 'video-diagnostics-overflow');
      await axe(m, 'video-before');
    }
  }
  const a = await start(browser, s, { width: 1440, height: 900 }, 'wp6-before-auth');
  runs.push(a);
  await a.page.goto(s.origin + `/catalog/${product.id}?wp6=return#product-details`);
  await a.page.waitForURL('**/login**');
  await capture(a, 'login-loses-return');
  await a.page.locator('#email').fill(wp3Owner.email);
  await a.page.locator('#password').fill(wp3Owner.password);
  await a.page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await a.page.waitForURL('**/dashboard');
  report.observations.push({ id: 'SE-BROWSER-020', destination: new URL(a.page.url()).pathname });
  await capture(a, 'after-sign-in');
  report.status = 'COMPLETE';
} catch (e) {
  report.status = 'BLOCKED';
  report.error = e.message.slice(0, 1200);
  for (const r of runs) await capture(r, 'blocker').catch(() => {});
} finally {
  for (const r of runs) await finish(r);
  await browser.close();
  await fs.writeFile(path.join(s.folder, 'wp6-before.json'), JSON.stringify(report, null, 2));
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP6 before complete');
  console.log(JSON.stringify(report));
}
process.exitCode = report.status === 'COMPLETE' ? 0 : 1;
