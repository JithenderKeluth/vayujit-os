import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect as e } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Api, wp3Owner } from './wp3-fixtures.mjs';
const expect = e.configure({ timeout: 15000 });
const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const witness = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (s.qa_phase !== 'WP7A3' || !s.synthetic || witness.token !== s.token || !witness.disposable)
  throw Error('OWNED_WP7A3_REQUIRED');
const report = {
  token: s.token,
  status: 'RUNNING',
  checks: [],
  scans: [],
  database: [],
  versions: {},
  historical_ads_502: 'UNREPRODUCED_CAUSE_UNCLASSIFIED',
  external_calls: false,
};
const runs = [],
  browsers = [];
const persist = () =>
  fs.writeFile(path.join(s.folder, 'wp7a3-browser.json'), JSON.stringify(report, null, 2));
async function check(run, id, fn) {
  try {
    await fn();
    report.checks.push({ context: run.label, id, status: 'PASS' });
  } catch (error) {
    report.checks.push({
      context: run.label,
      id,
      status: 'FAIL',
      safe_error: error.message.split('\n')[0].slice(0, 300),
    });
    await capture(run, 'FAILED-' + id, true).catch(() => {});
  }
  await persist();
}
const response = (p, suffix, method = 'POST') =>
  p.waitForResponse((r) => r.url().endsWith(suffix) && r.request().method() === method, {
    timeout: 20000,
  });
async function scan(run, label) {
  await capture(run, label, true);
  const v = await axe(run, label);
  report.scans.push({ context: run.label, ...v });
  await persist();
  expect(v.violations).toEqual([]);
  expect(run.signals.page_errors).toEqual([]);
  expect(
    run.signals.console_errors.filter((message) => /TypeError|ReferenceError/.test(message)),
  ).toEqual([]);
}
async function state(run, label) {
  const r = await run.page.request.get(s.origin + '/__qa/wp7a3/state', {
    headers: { 'x-qa-token': s.token },
  });
  expect(r.status()).toBe(200);
  const v = await r.json();
  report.database.push({ context: run.label, label, ...v });
  await persist();
  return v;
}
async function worker(run, fail = false) {
  const r = await run.page.request.post(s.origin + '/__qa/wp7a3/control', {
    headers: { 'x-qa-token': s.token },
    data: { scenario: fail ? 'WORKER_FAIL' : 'WORKER_SUCCESS' },
  });
  expect(r.status()).toBe(200);
  return r.json();
}
async function legacy(run, api, product) {
  const p = run.page;
  let artifact;
  await check(run, 'L-09', async () => {
    await p.goto(s.origin + '/ai/generate');
    await expect(
      p.getByRole('button', { name: 'Generate review draft', exact: true }),
    ).toBeDisabled();
    await p.getByRole('combobox', { name: 'Product', exact: true }).selectOption(product.id);
    await p
      .getByLabel('Additional instructions', { exact: true })
      .fill('[QA SYNTHETIC] WP7A3 original ' + run.label);
    const generated = response(p, '/ai/generations');
    await p.getByRole('button', { name: 'Generate review draft', exact: true }).click();
    const r = await generated;
    expect(r.status()).toBe(201);
    artifact = (await r.json()).artifact_id;
    await p.waitForURL('**/ai/artifacts/' + artifact);
    await expect(p.getByRole('heading', { name: 'Content review', exact: true })).toBeVisible();
    const approved = response(p, '/artifacts/' + artifact + '/approve');
    await p.getByRole('button', { name: 'Approve', exact: true }).press('Enter');
    expect((await approved).status()).toBe(200);
    await p.reload();
    await expect(p.locator('main')).toContainText('Status: approved');
    const rows = await state(run, 'legacy-approved');
    expect(rows.generated_artifacts.find((a) => a.id === artifact).status).toBe('approved');
    await scan(run, 'L09-approved-synthetic-content');
  });
  await check(run, 'L-11', async () => {
    const gen = await api('post', 'ai/generations', {
      product_id: product.id,
      provider_key: 'deterministic_mock_v1',
      additional_instructions: '[QA SYNTHETIC] WP7A3 draft edit ' + run.label,
    });
    await p.goto(s.origin + '/ai/artifacts/' + gen.artifact_id);
    await p.getByRole('button', { name: 'Edit structured content', exact: true }).click();
    await p
      .getByRole('textbox', { name: 'Title', exact: true })
      .fill('[QA SYNTHETIC] WP7A3 revised ' + run.label);
    const saved = response(p, '/studio/artifacts/' + gen.artifact_id, 'PATCH');
    await p.getByRole('button', { name: 'Save as new version', exact: true }).click();
    const r = await saved;
    expect(r.status()).toBe(200);
    const revision = await r.json();
    expect(revision.id).not.toBe(gen.artifact_id);
    expect(revision.status).toBe('pending_review');
    await expect(p).toHaveURL(new RegExp('/ai/artifacts/' + revision.id + '$'));
    await p.reload();
    await expect(
      p.getByRole('heading', { name: '[QA SYNTHETIC] WP7A3 revised ' + run.label, exact: true }),
    ).toBeVisible();
    const old = await api('get', 'ai/artifacts/' + gen.artifact_id);
    expect(old.content.product_title).not.toBe(revision.content.product_title);
    const stale = await p.request.patch(
      s.origin + '/api/v1/ai/studio/artifacts/' + gen.artifact_id,
      { data: { content: revision.content, expected_source_version: 9999 } },
    );
    expect(stale.status()).toBe(409);
    await scan(run, 'L11-versioned-draft-edit');
  });
  return artifact;
}
async function studio(run, api, product) {
  const p = run.page;
  await check(run, 'L-10', async () => {
    await p.goto(s.origin + '/ai/studio');
    await p.getByRole('combobox', { name: 'Product', exact: true }).selectOption(product.id);
    const queued = response(p, '/studio/generate');
    await p.getByRole('button', { name: 'Generate deterministic draft', exact: true }).click();
    const r = await queued;
    expect(r.status()).toBe(202);
    const gen = await r.json();
    const duplicate = await p.request.post(s.origin + '/api/v1/ai/studio/generate', {
      data: r.request().postDataJSON(),
    });
    expect(duplicate.status()).toBe(202);
    expect((await duplicate.json()).id).toBe(gen.id);
    for (let n = 0; n < 3; n++) await worker(run, true);
    const failed = await api('get', 'ai/studio/generations/' + gen.id);
    expect(failed.status).toBe('failed');
    await p.reload();
    await expect(p.locator('main')).toContainText('provider_unavailable');
    const retry = response(p, '/studio/recovery/actions');
    await p.getByRole('button', { name: 'Retry failed content', exact: true }).first().click();
    expect((await retry).status()).toBe(200);
    await expect(
      p.getByRole('button', { name: 'Generate deterministic draft', exact: true }),
    ).toBeEnabled();
    await worker(run);
    await p.getByRole('button', { name: 'Refresh artifacts', exact: true }).click();
    const success = await api('get', 'ai/studio/generations/' + gen.id);
    expect(success.status).toBe('completed');
    expect(success.outputs.every((o) => o.artifact_id)).toBe(true);
    await p.reload();
    await expect(p.locator('#artifacts')).toContainText(product.name);
    await state(run, 'studio-recovered');
    await scan(run, 'L10-studio-failure-retry-persisted');
  });
}
async function images(run, api, brand, product) {
  const p = run.page;
  let media;
  await check(run, 'L-12', async () => {
    await p.goto(s.origin + '/media/upload');
    await p.locator('input[type=file]').setInputFiles({
      name: 'qa-wp7a3-invalid.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('QA synthetic invalid'),
    });
    await expect(p.getByRole('alert')).toContainText('Choose a JPEG');
    const png = await p.evaluate(() => {
      const c = document.createElement('canvas');
      c.width = 64;
      c.height = 64;
      const x = c.getContext('2d');
      x.fillStyle = '#14617a';
      x.fillRect(0, 0, 64, 64);
      return c.toDataURL('image/png').split(',')[1];
    });
    await p.locator('input[type=file]').setInputFiles({
      name: 'qa-wp7a3-synthetic.png',
      mimeType: 'image/png',
      buffer: Buffer.from(png, 'base64'),
    });
    const uploaded = response(p, '/api/v1/media');
    await p.getByRole('button', { name: 'Upload securely', exact: true }).click();
    const upload = await uploaded;
    expect(upload.status()).toBe(201);
    media = await upload.json();
    await p.waitForURL('**/media/' + media.id);
    await p.reload();
    await expect(p.locator('main')).toContainText('64');
    const anonymous = await p.context().browser().newContext();
    expect(
      (await anonymous.request.get(s.origin + '/api/v1/media/' + media.id + '/preview')).status(),
    ).toBe(401);
    await anonymous.close();
    await p.goto(s.origin + '/ai/images');
    await p.getByRole('combobox', { name: 'Brand', exact: true }).selectOption(brand.id);
    await p.getByRole('combobox', { name: 'Product', exact: true }).selectOption(product.id);
    const queued = response(p, '/images/generate');
    await p.getByRole('button', { name: 'Queue deterministic image', exact: true }).click();
    const r = await queued;
    expect(r.status()).toBe(202);
    const gen = await r.json();
    await worker(run);
    const output = (await api('get', 'ai/images/generations/' + gen.generation_id)).outputs[0];
    await p.goto(s.origin + '/ai/images/assets/' + output.id);
    await expect(p.getByRole('heading', { name: 'Image review', exact: true })).toBeVisible();
    await expect(p.locator('main img')).toBeVisible();
    const approved = response(p, '/outputs/' + output.id + '/approve');
    await p.getByRole('button', { name: 'Approve exact output', exact: true }).click();
    expect((await approved).status()).toBe(200);
    await p.reload();
    await expect(p.locator('main')).toContainText('approved');
    expect(
      run.signals.console_errors.filter((message) =>
        /TypeError|ReferenceError|ERROR Error/.test(message),
      ),
    ).toEqual([]);
    const regen = response(p, '/outputs/' + output.id + '/regenerate');
    await p.getByRole('button', { name: 'Regenerate', exact: true }).click();
    const child = await (await regen).json();
    await worker(run);
    await p.goto(s.origin + '/ai/images/assets/' + child.outputs[0].id);
    await expect(p.locator('main')).not.toContainText('Status: approved');
    const rows = await state(run, 'image-lineage');
    expect(rows.ai_image_outputs.find((o) => o.id === output.id).status).toBe('approved');
    expect(rows.ai_image_outputs.find((o) => o.id === child.outputs[0].id).parent_output_id).toBe(
      output.id,
    );
    await scan(run, 'L12-private-image-output-review');
  });
  return media;
}
async function bulk(run, api, product) {
  const p = run.page;
  await check(run, 'L-13', async () => {
    await p.goto(s.origin + '/ai/studio/bulk');
    await p
      .getByRole('checkbox', {
        name: new RegExp(product.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')),
      })
      .check();
    const preview = response(p, '/studio/bulk/preview');
    await p.getByRole('button', { name: 'Review plan', exact: true }).click();
    expect((await preview).status()).toBe(200);
    const queued = response(p, '/studio/bulk');
    await p.getByRole('button', { name: /^Queue \d+ outputs$/ }).click();
    const r = await queued;
    expect(r.status()).toBe(202);
    const op = await r.json();
    await worker(run);
    await p.getByRole('button', { name: 'Refresh history', exact: true }).click();
    await p.getByRole('button', { name: 'Open details', exact: true }).first().click();
    await expect(p.locator('main')).toContainText('completed');
    await p.reload();
    await p.getByRole('button', { name: 'Open details', exact: true }).first().click();
    const persisted = await api('get', 'ai/studio/bulk/' + op.id);
    expect(persisted.total_outputs).toBeGreaterThan(0);
    await state(run, 'bulk-text');
    await scan(run, 'L13-bulk-text-persistence');
  });
  await check(run, 'L-14', async () => {
    await p.goto(s.origin + '/ai/images/bulk');
    await p.getByRole('checkbox', { name: product.name, exact: true }).check();
    const preview = response(p, '/images/bulk/preview');
    await p.getByRole('button', { name: 'Review plan', exact: true }).click();
    const plan = await (await preview).json();
    expect(plan.total_outputs).toBeGreaterThan(0);
    await expect(p.locator('main')).toContainText('unavailable');
    // Source-dependent plans must truthfully block; do not fabricate a primary image.
    if (plan.blockers.length) {
      await expect(p.locator('main')).toContainText(plan.blockers[0]);
      await scan(run, 'L14-missing-image-prerequisite');
      return;
    }
    const queued = response(p, '/images/bulk');
    await p.getByRole('button', { name: 'Queue bulk generation', exact: true }).click();
    const queuedResponse = await queued;
    expect(queuedResponse.status()).toBe(202);
    const op = await queuedResponse.json();
    await expect(p).toHaveURL(new RegExp('operation=' + op.id));
    await worker(run);
    expect((await api('get', 'ai/images/bulk/' + op.id)).status).toBe('completed');
    await p.getByRole('button', { name: 'Refresh operation status', exact: true }).click();
    await expect(
      p.getByRole('heading', { name: 'Bulk operation: completed', exact: true }),
    ).toBeVisible();
    await p.reload();
    await expect(
      p.getByRole('heading', { name: 'Bulk operation: completed', exact: true }),
    ).toBeVisible();
    await scan(run, 'L14-bulk-image-persisted');
  });
}
async function seo(run, api, product) {
  const p = run.page;
  await check(run, 'L-15', async () => {
    await p.goto(s.origin + '/ai/studio/seo');
    await p.getByRole('combobox', { name: 'Product', exact: true }).selectOption(product.id);
    await p.getByLabel('Primary keyword', { exact: true }).fill('synthetic organizer');
    const analyzed = p.waitForResponse(
      (r) => r.url().includes('/ai/seo/') && r.request().method() === 'POST',
    );
    await p.getByRole('button', { name: 'Analyze', exact: true }).click();
    const r = await analyzed;
    expect(r.status()).toBe(201);
    await expect(p.locator('main')).toContainText('Findings');
    const analysis = await r.json();
    await p.getByRole('button', { name: 'Analysis History', exact: true }).click();
    await p.getByRole('button', { name: 'Refresh history', exact: true }).click();
    await expect(p.locator('main')).toContainText(analysis.locale);
    const history = await api('get', 'ai/seo/analyses');
    expect(history.some((item) => item.id === analysis.id && item.product_id === product.id)).toBe(
      true,
    );
    await scan(run, 'L15-persisted-scoped-seo');
  });
}
async function campaign(run, api, brand, product, artifact) {
  const p = run.page;
  await check(run, 'L-16', async () => {
    await p.goto(s.origin + '/campaigns/new');
    await expect(p.getByRole('button', { name: 'Create Campaign', exact: true })).toBeDisabled();
    await p.locator('select[formControlName=brand_id]').selectOption(brand.id);
    await p.getByLabel('Name', { exact: true }).fill('[QA SYNTHETIC] WP7A3 ' + run.label);
    await p.getByLabel('Timezone', { exact: true }).fill('Asia/Kolkata');
    await p.getByLabel('Starts', { exact: true }).fill('2026-11-10T09:00');
    await p.getByLabel('Ends', { exact: true }).fill('2026-11-15T18:00');
    const created = response(p, '/api/v1/campaigns');
    await p.getByRole('button', { name: 'Create Campaign', exact: true }).click();
    const r = await created;
    expect(r.status()).toBe(201);
    const c = await r.json();
    await p.waitForURL('**/campaigns/' + c.id);
    await p.getByRole('link', { name: 'Add activity', exact: true }).click();
    await p.locator('select[formControlName=activity_type]').selectOption('review_checkpoint');
    await p.getByLabel('Name', { exact: true }).fill('[QA SYNTHETIC] WP7A3 review');
    await p.getByLabel('Date', { exact: true }).fill('2026-11-11');
    const added = response(p, '/campaigns/' + c.id + '/activities');
    await p.getByRole('button', { name: 'Add activity', exact: true }).click();
    const addedResponse = await added;
    expect(addedResponse.status()).toBe(201);
    const first = await addedResponse.json();
    await p.waitForURL('**/campaigns/' + c.id);
    await p.reload();
    await expect(p.locator('main')).toContainText('[QA SYNTHETIC] WP7A3 review');
    await p.getByRole('link', { name: 'Add activity', exact: true }).click();
    await p.locator('select[formControlName=activity_type]').selectOption('approval_checkpoint');
    await p.getByLabel('Name', { exact: true }).fill('[QA SYNTHETIC] WP7A3 approval');
    await p.getByLabel('Date', { exact: true }).fill('2026-11-12');
    await p.getByLabel('Sequence', { exact: true }).fill('2');
    const secondAdded = response(p, '/campaigns/' + c.id + '/activities');
    await p.getByRole('button', { name: 'Add activity', exact: true }).click();
    const secondResponse = await secondAdded;
    expect(secondResponse.status()).toBe(201);
    const second = await secondResponse.json();
    await p.waitForURL('**/campaigns/' + c.id);
    const ready = response(p, '/campaigns/' + c.id + '/validate');
    await p.getByRole('button', { name: 'Review readiness', exact: true }).click();
    expect((await ready).status()).toBe(200);
    await p.getByRole('link', { name: 'Dependencies', exact: true }).click();
    await expect(
      p.getByRole('heading', { name: 'Activity dependencies', exact: true }),
    ).toBeVisible();
    await p.getByRole('combobox', { name: /^Predecessor/ }).selectOption(first.id);
    await p.getByRole('combobox', { name: /^Successor/ }).selectOption(second.id);
    const dependency = response(p, '/campaigns/' + c.id + '/dependencies');
    await p.getByRole('button', { name: 'Add dependency', exact: true }).click();
    expect((await dependency).status()).toBe(201);
    await p.reload();
    await expect(
      p.getByRole('heading', { name: 'Dependency order', exact: true }).locator('..'),
    ).toContainText('success_required');
    await state(run, 'campaign-preparation');
    await scan(run, 'L16-campaign-context-and-readiness');
    if (artifact) {
      const handoff = await api(
        'post',
        'ai/studio/artifacts/' + artifact + '/campaign-handoff',
        {},
      );
      expect(handoff.status).not.toBe('completed');
    }
  });
  await check(run, 'L-17', async () => {
    await p.goto(s.origin + '/ads/create');
    await p
      .getByLabel('Campaign name', { exact: true })
      .fill('[QA SYNTHETIC] WP7A2 WP7A3 ' + run.label);
    await p.getByRole('button', { name: 'Next', exact: true }).click();
    await p.getByRole('combobox', { name: 'Product', exact: true }).selectOption(product.id);
    for (let n = 0; n < 3; n++) await p.getByRole('button', { name: 'Next', exact: true }).click();
    const preview = response(p, '/ads/campaigns/preview');
    await p.getByRole('button', { name: 'Run server preview', exact: true }).click();
    expect((await preview).status()).toBe(422);
    await expect(p.locator('main')).toContainText(/required|invalid|account/i);
    await scan(run, 'L17-ads-missing-authorization');
    for (const route of ['ads/overview', 'ads/comparison'])
      expect((await p.request.get(s.origin + '/api/v1/' + route)).status()).toBe(200);
  });
}
try {
  let brand;
  for (const channel of process.argv.includes('--focused') ? ['chrome'] : ['chrome', 'msedge']) {
    const browser = await chromium.launch({ channel, headless: true });
    browsers.push(browser);
    report.versions[channel] = browser.version();
    for (const width of process.argv.includes('--focused') ? [1440] : [1440, 390]) {
      const run = await start(browser, s, { width, height: 900 }, 'wp7a3-' + channel + '-' + width);
      runs.push(run);
      const p = run.page;
      p.setDefaultTimeout(15000);
      p.on('dialog', (d) => d.accept());
      const setup = await p.request
        .get(s.origin + '/api/v1/auth/setup-status')
        .then((r) => r.json());
      await p.goto(s.origin + (setup.ownerExists ? '/login' : '/setup'));
      if (!setup.ownerExists) {
        await p.locator('#full-name').fill('[QA SYNTHETIC] WP7A3 Owner');
        await p.locator('#confirmation').fill(wp3Owner.password);
      }
      await p.locator('#email').fill(wp3Owner.email);
      await p.locator('#password').fill(wp3Owner.password);
      await p
        .getByRole('button', { name: setup.ownerExists ? 'Sign in' : 'Create owner', exact: true })
        .click();
      await p.waitForURL('**/dashboard');
      const api = wp3Api(p, s.origin);
      if (!brand) brand = await api('post', 'brands', { name: '[QA SYNTHETIC] WP7A3 Brand' });
      const product = await api('post', 'products', {
        brand_id: brand.id,
        name: '[QA SYNTHETIC] WP7A3 ' + run.label,
        sku: 'QA-' + run.label,
        product_type: 'physical',
        description: 'Disposable synthetic organizer, no verified commercial claims.',
        price_amount: '100.25',
        price_currency: 'INR',
      });
      await api('post', 'products/' + product.id + '/activate', {});
      const artifact = await legacy(run, api, product);
      await studio(run, api, product);
      await images(run, api, brand, product);
      await bulk(run, api, product);
      await seo(run, api, product);
      await campaign(run, api, brand, product, artifact);
    }
  }
} catch (error) {
  report.startup_failure = {
    code: error.message.startsWith('WP3_FIXTURE_') ? error.message : 'WP7A3_SETUP_FAILED',
    raw_output_persisted: false,
  };
} finally {
  for (const run of runs) await finish(run);
  for (const browser of browsers) await browser.close();
  report.status =
    report.checks.length === (process.argv.includes('--focused') ? 9 : 36) &&
    report.checks.every((c) => c.status === 'PASS')
      ? 'PASS'
      : 'INCOMPLETE';
  await persist();
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP7A3 complete');
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
