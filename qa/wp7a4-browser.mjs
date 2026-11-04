import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { chromium, expect as assertion } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Owner } from './wp3-fixtures.mjs';
import { responseWait } from './wp7a4-wait.mjs';
import { rollup } from './wp7a4-rollup.mjs';
import { saveEvidence } from './wp7a4-evidence.mjs';
import { sourceFingerprint } from './wp7a7-source.mjs';
const expect = assertion.configure({ timeout: 10000 });
const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const seventh = s.qa_phase === 'WP7A7';
const testedSource = seventh ? await sourceFingerprint() : null;
const sixth = seventh || s.qa_phase === 'WP7A6';
const fifth = sixth || s.qa_phase === 'WP7A5';
const packageKey = seventh ? 'wp7a7' : sixth ? 'wp7a6' : fifth ? 'wp7a5' : 'wp7a4';
const ledgerPath = 'docs/qa/seller-experience/' + packageKey + '-coverage-ledger.json';
const ledger = JSON.parse(await fs.readFile(ledgerPath, 'utf8'));
const witness = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (
  !['WP7A4', 'WP7A5', 'WP7A6', 'WP7A7'].includes(s.qa_phase) ||
  !s.synthetic ||
  witness.token !== s.token ||
  !witness.disposable ||
  ledger.entries.length !== (fifth && !sixth ? 16 : 48)
)
  throw Error('EXACT_WP7A4_REQUIRED');
const focused = process.argv.includes('--focused');
const requested = (process.env[seventh ? 'QA_WP7A7_IDS' : sixth ? 'QA_WP7A6_IDS' : fifth ? 'QA_WP7A5_IDS' : 'QA_WP7A4_IDS'] || '').split(',').filter(Boolean);
if (requested.some((id) => !ledger.entries.some((e) => e.id === id)))
  throw Error('UNKNOWN_ORIGINAL_COVERAGE_ID');
const selected = ledger.entries.filter((e) => (!sixth || e.wp7a6_target) && (!requested.length || requested.includes(e.id)));
const requiredContexts = ['chrome-1440', 'chrome-390', 'msedge-1440', 'msedge-390'].map((v) => packageKey + '-' + v);
const contexts = focused ? requiredContexts.slice(0, 1) : requiredContexts;
const report = {
  package: seventh ? 'WP7A-7' : sixth ? 'WP7A-6' : fifth ? 'WP7A-5' : 'WP7A-4',
  token: s.token,
  status: 'RUNNING',
  contexts,
  versions: {},
  checks: [],
  scans: [],
  fixtures: [],
  database: [],
  external_calls: false,
};
const runs = [],
  browsers = [];
class Blocked extends Error {}
const persist = async () => {
  for (const e of ledger.entries) {
    if (sixth && !e.wp7a6_target) continue;
    Object.assign(e, rollup(e, requiredContexts));
  }
  ledger.status = 'RUNNING';
  ledger.updated_at = new Date().toISOString();
  ledger.counts = Object.fromEntries(
    ['PASS', 'FAIL', 'BLOCKED', 'PARTIAL', 'NOT_TESTED'].map((k) => [
      k,
      ledger.entries.filter((e) => e.status === k).length,
    ]),
  );
  ledger.checkpoint = {
    token: s.token,
    session: path.join(s.folder, 'session.json'),
    completed_ids: ledger.entries
      .filter((e) => e.attempts.some((a) => a.token === s.token))
      .map((e) => e.id),
    remaining_ids: ledger.entries
      .filter((e) => !e.attempts.some((a) => a.token === s.token))
      .map((e) => e.id),
    safe_resume:
      'Never reuse a dropped database. Preserve attempts and use a new signed QA run; no deletion/recovery guard may be bypassed.',
  };
  await saveEvidence(path.join(s.folder, packageKey + '-browser.json'), report);
  await saveEvidence(ledgerPath, ledger);
};
async function check(run, e, fn) {
  const signalStart = {
    console: run.signals.console_errors.length,
    page: run.signals.page_errors.length,
    network: run.signals.network.length,
  };
  let status = 'PASS',
    reason = 'Supported local workflow, reload and canonical identity assertions passed.';
  const t = new Date().toISOString();
  let evidence = {};
  try {
    if (!(await run.page.request.get(s.origin + '/api/v1/auth/me')).ok())
      await authenticated(run.page);
    const result = await fn();
    if (result) evidence = result;
    if (result) {
      status = result.status;
      reason = result.reason;
    }
  } catch (error) {
    status = error instanceof Blocked ? 'BLOCKED' : 'FAIL';
    reason = error.message.split('\n')[0].slice(0, 250);
  }
  let shot = null;
  try {
    shot = await capture(run, e.id + '-' + status, true);
    const runtimeErrors = [
      ...run.signals.console_errors.slice(signalStart.console),
      ...run.signals.page_errors.slice(signalStart.page),
    ].filter((v) => /TypeError|ReferenceError|NG0\d+/.test(v));
    if (runtimeErrors.length) {
      status = 'FAIL';
      reason = 'APPLICATION_RENDERING_ERROR';
    }
    if (run.signals.network.slice(signalStart.network).some((v) => v.status >= 500)) {
      status = 'FAIL';
      reason = 'APPLICATION_API_5XX';
    }
    const focusable = run.page
      .locator('main a[href], main button:enabled, main input:enabled, main select:enabled')
      .filter({ visible: true });
    if (await focusable.count()) {
      await focusable.first().focus();
      await expect(focusable.first()).toBeFocused();
      if ((await focusable.count()) > 1) {
        await run.page.keyboard.press('Tab');
        await run.page.keyboard.press('Shift+Tab');
        await expect(focusable.first()).toBeFocused();
      }
    }
    const v = await axe(run, e.id);
    report.scans.push({ context: run.label, id: e.id, ...v });
    if (v.violations.length) {
      if (status === 'PASS') reason = 'AXE_VIOLATIONS';
      status = 'FAIL';
    }
  } catch {
    if (status === 'PASS') {
      status = 'FAIL';
      reason = 'BROWSER_EVIDENCE_CAPTURE_FAILED';
    }
  }
  const attempt = {
    token: s.token,
    context: run.label,
    id: e.id,
    status,
    reason,
    at: t,
    route: new URL(run.page.url()).pathname,
    screenshot: shot?.screenshot,
    trace: path.join(run.directory, 'trace.zip'),
    ...(sixth ? { acceptance_assertions: evidence.acceptance_assertions || [], persisted_state_verified: evidence.persisted_state_verified === true } : {}),
  };
  e.attempts.push(attempt);
  e.evidence.push(attempt);
  report.checks.push(attempt);
  await persist();
  console.log(JSON.stringify({ id: e.id, context: run.label, status }));
}
const waitResponse = (p, suffix, method = 'POST') =>
  responseWait(p, (r) => r.url().endsWith(suffix) && r.request().method() === method, {
    timeout: 12000,
  });
async function authenticated(p) {
  const setup = await p.request.get(s.origin + '/api/v1/auth/setup-status').then((r) => r.json());
  await p.goto(s.origin + (setup.ownerExists ? '/login' : '/setup'));
  if (!setup.ownerExists) {
    await p.locator('#full-name').fill('[QA SYNTHETIC] WP7A4 Owner');
    await p.locator('#confirmation').fill(wp3Owner.password);
  }
  await p.locator('#email').fill(wp3Owner.email);
  await p.locator('#password').fill(wp3Owner.password);
  await p
    .getByRole('button', { name: setup.ownerExists ? 'Sign in' : 'Create owner', exact: true })
    .click();
  await p.waitForURL('**/dashboard');
}
async function campaign(run) {
  const p = run.page;
  const api = async (method, url, data, accepted = [200, 201, 202]) => {
    const r = await p.request[method](s.origin + '/api/v1/' + url, {
      ...(data === undefined ? {} : { data }),
    });
    if (!accepted.includes(r.status()))
      throw new Blocked(
        'CANONICAL_FIXTURE_' +
          method.toUpperCase() +
          '_' +
          url.replace(/[a-f0-9-]{36}/g, ':id') +
          '_' +
          r.status(),
      );
    return r.status() === 204 ? null : r.json();
  };
  const memo = {};
  const once = async (k, fn) => (memo[k] ??= await fn());
  report.fixtures.push({ context: run.label, identities: memo });
  const brand = await api('post', 'brands', { name: '[QA SYNTHETIC] WP7A4 ' + run.label });
  await api('post', 'brands/' + brand.id + '/activate', {});
  const product = await api('post', 'products', {
    brand_id: brand.id,
    name: '[QA SYNTHETIC] WP7A4 ' + run.label,
    product_type: 'physical',
    description: 'Synthetic QA product, no verified market or commercial claims.',
    price_amount: '100.25',
    price_currency: 'INR',
  });
  await api('post', 'products/' + product.id + '/activate', {});
  Object.assign(
    report.fixtures.find((v) => v.context === run.label),
    { brand_id: brand.id, product_id: product.id },
  );
  await persist();
  const worker = async (fail = false) => {
    const r = await p.request.post(s.origin + '/__qa/wp7a3/control', {
      headers: { 'x-qa-token': s.token },
      data: { scenario: fail ? 'WORKER_FAIL' : 'WORKER_SUCCESS' },
    });
    expect(r.status()).toBe(200);
    return r.json();
  };
  const content = () =>
    once('content', async () => {
      const gen = await api('post', 'ai/generations', {
        product_id: product.id,
        provider_key: 'deterministic_mock_v1',
        additional_instructions: '[QA SYNTHETIC] WP7A4 ' + run.label,
      });
      if (!gen.artifact_id) throw new Blocked('DETERMINISTIC_CONTENT_NOT_CREATED');
      await p.goto(s.origin + '/ai/artifacts/' + gen.artifact_id);
      await p.getByRole('button', { name: 'Approve', exact: true }).click();
      await expect(p.locator('main')).toContainText('Status: approved');
      return api('get', 'ai/artifacts/' + gen.artifact_id);
    });
  const media = () =>
    once('media', async () => {
      const data = await p.evaluate(() => {
        const c = document.createElement('canvas');
        c.width = c.height = 64;
        c.getContext('2d').fillRect(0, 0, 64, 64);
        return c.toDataURL('image/png').split(',')[1];
      });
      const r = await p.request.post(s.origin + '/api/v1/media', {
        multipart: {
          file: {
            name: 'wp7a4-synthetic.png',
            mimeType: 'image/png',
            buffer: Buffer.from(data, 'base64'),
          },
        },
      });
      expect(r.status()).toBe(201);
      return r.json();
    });
  const image = () =>
    once('image', async () => {
      const r = await api('post', 'ai/images/generate', {
        brand_id: brand.id,
        product_id: product.id,
        operation: 'generate_product_image',
        channel: 'canonical',
        width: 64,
        height: 64,
        output_count: 1,
        provider: 'deterministic_mock_v1',
        idempotency_key: 'wp7a4-image-' + run.label,
      });
      await worker();
      return (await api('get', 'ai/images/generations/' + r.generation_id)).outputs[0];
    });
  const video = () =>
    once('video', async () => {
      await content();
      const queued = await api('post', 'ai/video/queue', {
        brand_id: brand.id,
        product_id: product.id,
        video_type: 'product_showcase',
        target_channel: 'youtube',
        resolution: '320x240',
        duration_seconds: 2,
        idempotency_key: 'wp7a4-video-' + run.label,
      });
      await worker();
      let saved = await api('get', 'ai/video/generations/' + queued.id);
      expect(saved.status).toBe('succeeded');
      await p.goto(s.origin + '/ai/video');
      await p
        .getByRole('row')
        .filter({ hasText: product.id })
        .first()
        .getByRole('button', { name: 'Open review', exact: true })
        .click();
      const approved = waitResponse(p, '/generations/' + queued.id + '/approve');
      await p.getByRole('button', { name: 'Approve', exact: true }).last().click();
      expect((await approved).status()).toBe(200);
      saved = await api('get', 'ai/video/generations/' + queued.id);
      expect(saved.output_status).toBe('approved');
      return saved;
    });
  const publishing = () =>
    once('publishing', async () => {
      const a = await content();
      const r = await p.request.post(s.origin + '/__qa/wp7a4/prepare', {
        headers: { 'x-qa-token': s.token },
        data: { artifact_id: a.id },
      });
      if (r.status() !== 200) throw new Blocked('CANONICAL_LOCAL_MOCK_PREPARATION_' + r.status());
      return r.json();
    });
  const adAccount = () =>
    once('adAccount', async () => {
      const a = await api('post', 'ads/accounts', {
        provider: 'meta',
        environment: 'local',
        display_name: '[QA SYNTHETIC] WP7A2 WP7A4 ' + run.label,
        external_account_id: 'qa-wp7a2-' + run.label,
        credentials: { token: 'QA-SYNTHETIC-NOT-A-REAL-CREDENTIAL' },
      });
      await api('post', 'ads/accounts/' + a.id + '/validate', {});
      await api('post', 'ads/accounts/' + a.id + '/enable', {});
      return a;
    });
  const c = () =>
    once('campaign', async () =>
      api('post', 'campaigns', {
        brand_id: brand.id,
        name: '[QA SYNTHETIC] WP7A3 WP7A4 ' + run.label,
        timezone_name: 'Asia/Kolkata',
        local_start_at: '2026-11-10T09:00:00',
        local_end_at: '2026-11-15T18:00:00',
      }),
    );
  const activity = () =>
    once('activity', async () => {
      const v = await c();
      return api('post', 'campaigns/' + v.id + '/activities', {
        activity_type: 'review_checkpoint',
        name: '[QA SYNTHETIC] WP7A4 checkpoint',
        sequence: 1,
        scheduled_local_date: '2026-11-11',
        scheduled_local_time: '09:00:00',
      });
    });
  const social = () =>
    once('social', async () => {
      const a = await content();
      const account = await once('socialAccount', () =>
        api('post', 'social/accounts', {
          platform: 'facebook',
          environment: 'local',
          display_name: '[QA SYNTHETIC] WP7A4 social',
          remote_account_id: 'qa-' + run.label,
          credentials: {},
        }),
      );
      return api('post', 'social/posts', {
        brand_id: brand.id,
        product_id: product.id,
        platform: 'facebook',
        account_id: account.id,
        content_type: 'facebook_post',
        content_artifact_id: a.id,
        content_artifact_version: a.version_number,
        caption: '[QA SYNTHETIC] review only',
        idempotency_key: 'wp7a4-social-' + run.label,
      });
    });
  const listing = (channel) =>
    once('listing-' + channel, async () => {
      const a = await content();
      const accounts = await api('get', 'marketplaces/accounts');
      const account =
        accounts.find((x) => x.marketplace === channel) ||
        (await api('post', 'marketplaces/accounts', {
          marketplace: channel,
          display_name: '[QA SYNTHETIC] WP7A4 ' + channel,
          seller_account_id: 'qa3-' + channel,
          environment: 'sandbox',
          credentials: {},
        }));
      expect(account.environment).toBe('sandbox');
      return api('post', 'marketplaces/listings', {
        product_id: product.id,
        brand_id: brand.id,
        account_id: account.id,
        title: '[QA SYNTHETIC] WP7A4 listing',
        marketplace_sku: 'qa-wp7a4-' + channel + '-' + run.label,
        artifact_id: a.id,
        idempotency_key: 'wp7a4-listing-' + channel + '-' + run.label,
      });
    });
  const readDetail = async (url, endpoint, label) => {
    const saved = await api('get', endpoint);
    await p.goto(s.origin + url);
    const expected = new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
    await expect(p.locator('main')).toContainText(expected);
    await p.reload();
    await expect(p.locator('main')).toContainText(expected);
    const identity = (v) => v.id ?? v.worker_id ?? v.campaign?.id;
    expect(identity(saved)).toBeTruthy();
    const again = await api('get', endpoint);
    expect(identity(again)).toBe(identity(saved));
    const anonymous = await p.context().browser().newContext();
    expect((await anonymous.request.get(s.origin + '/api/v1/' + endpoint)).status()).toBe(401);
    await anonymous.close();
  };
  const defaultResult = (reason) => ({ status: 'PARTIAL', reason });
  for (const e of selected)
    await check(run, e, async () => {
      if (seventh) {
        const { execute } = await import('./wp7a7-scenarios.mjs');
        return execute(e, { p, s, run, api, memo, once, brand, product, worker, content, media, image, video, publishing, adAccount, c, activity, social, listing, readDetail, waitResponse, expect, capture, axe });
      }
      if (sixth) {
        const { execute } = await import('./wp7a6-scenarios.mjs');
        return execute(e, { p, s, run, api, memo, once, brand, product, worker, content, media, image, video, publishing, adAccount, c, activity, social, listing, readDetail, waitResponse, expect });
      }
      if (fifth) {
        const { execute } = await import('./wp7a5-scenarios.mjs');
        return execute(e, { p, s, run, api, memo, once, brand, product, worker, content, media, image, video, publishing, adAccount, c, activity, social, listing, readDetail, waitResponse, expect });
      }
      switch (e.id) {
        case 'R-8a5edab2':
        case 'R-8d64a30d': {
          await p.goto(s.origin + (e.route === '/' ? '/' : '/wp7a4-unknown-route'));
          await expect(p).toHaveURL(/\/dashboard$/);
          await p.request.post(s.origin + '/api/v1/auth/logout');
          await p.goto(s.origin + (e.route === '/' ? '/' : '/wp7a4-unknown-route'));
          await expect(p).toHaveURL(/\/login/);
          await authenticated(p);
          return;
        }
        case 'R-7e93fba0': {
          await p.request.post(s.origin + '/api/v1/auth/logout');
          await p.goto(s.origin + '/login');
          await p.locator('#email').fill(wp3Owner.email);
          await p.locator('#password').fill('QA-SYNTHETIC-WRONG-PASSWORD');
          await p.getByRole('button', { name: 'Sign in', exact: true }).click();
          await expect(p.getByRole('alert')).toBeVisible();
          await authenticated(p);
          await p.reload();
          await expect(p).toHaveURL(/dashboard/);
          return;
        }
        case 'R-184826c3': {
          const v = await api('post', 'intelligence/trends/contexts', {
            name: '[QA SYNTHETIC] WP7A4 trend',
            subject_type: 'PRODUCT',
            product_id: product.id,
            subject_key: product.id,
            idempotency_key: 'ux-r11a-trend-' + product.id + '-wp7a4',
          });
          await readDetail(
            '/intelligence/trends/' + v.id,
            'intelligence/trends/contexts/' + v.id,
            'Trend',
          );
          const analysis = waitResponse(p, '/contexts/' + v.id + '/analyses');
          await p
            .getByRole('button', { name: 'Analyze latest immutable snapshot', exact: true })
            .click();
          expect((await analysis).status()).toBe(201);
          await p.reload();
          await expect(p.locator('main')).toContainText(/insufficient|unknown|not.available/i);
          return defaultResult(
            'Owned context/reload verified; populated observation/source analysis remains unverified.',
          );
        }
        case 'R-17b7d214': {
          const a = await adAccount();
          await readDetail('/ads/accounts/' + a.id, 'ads/accounts/' + a.id, a.display_name);
          return;
        }
        case 'R-66842e70':
        case 'L-17': {
          const a = await adAccount();
          await p.goto(s.origin + '/ads/create');
          await p.locator('select[name=account_id]').selectOption(a.id);
          await p
            .getByLabel('Campaign name', { exact: true })
            .fill('[QA SYNTHETIC] WP7A2 WP7A4 ' + run.label);
          await p.getByRole('button', { name: 'Next', exact: true }).click();
          await p.getByRole('combobox', { name: 'Product', exact: true }).selectOption(product.id);
          for (let n = 0; n < 2; n++)
            await p.getByRole('button', { name: 'Next', exact: true }).click();
          await p.getByLabel('Amount', { exact: true }).fill('25.55');
          await p.getByRole('button', { name: 'Next', exact: true }).click();
          const r = waitResponse(p, '/ads/campaigns/preview');
          await p.getByRole('button', { name: 'Run server preview', exact: true }).click();
          expect((await r).status()).toBe(200);
          for (let n = 0; n < 7; n++)
            await p.getByRole('button', { name: 'Next', exact: true }).click();
          await expect(
            p.getByRole('button', { name: 'Confirm and queue campaign', exact: true }),
          ).toBeDisabled();
          await p.locator('input[name=confirm_checked]').check();
          const confirmed = waitResponse(p, '/ads/campaigns/confirm');
          await p.getByRole('button', { name: 'Confirm and queue campaign', exact: true }).click();
          const result = await confirmed;
          expect(result.status()).toBe(200);
          const v = (await result.json()).campaign;
          memo.adCampaign = v;
          await readDetail('/ads/campaigns/' + v.id, 'ads/campaigns/' + v.id, v.name);
          return e.id === 'L-17'
            ? defaultResult(
                'Persisted fake Ads campaign, explicit HUMAN confirmation and reload checked; creative/stale/expired-authorization permutations remain.',
              )
            : undefined;
        }
        case 'R-e4940841': {
          const v = await c();
          await readDetail('/campaigns/' + v.id, 'campaigns/' + v.id, v.name);
          return;
        }
        case 'R-8522d9c2': {
          const v = await c();
          await p.goto(s.origin + '/campaigns/' + v.id + '/activities/new');
          await p
            .locator('select[formControlName=activity_type]')
            .selectOption('review_checkpoint');
          await p.getByLabel('Name', { exact: true }).fill('[QA SYNTHETIC] WP7A4 UI checkpoint');
          await p.getByLabel('Sequence', { exact: true }).fill('2');
          await p.getByLabel('Date', { exact: true }).fill('2026-11-12');
          const r = waitResponse(p, '/campaigns/' + v.id + '/activities');
          await p.getByRole('button', { name: 'Add activity', exact: true }).click();
          expect((await r).status()).toBe(201);
          await p.waitForURL('**/campaigns/' + v.id);
          await p.reload();
          await expect(p.locator('main')).toContainText('WP7A4 UI checkpoint');
          return;
        }
        case 'R-f4ba2c21': {
          const v = await c(),
            a = await activity();
          const list = await api('get', 'campaigns/' + v.id + '/activities');
          const b =
            list.find((x) => x.id !== a.id) ||
            (await api('post', 'campaigns/' + v.id + '/activities', {
              activity_type: 'approval_checkpoint',
              name: '[QA SYNTHETIC] WP7A4 approval',
              sequence: 3,
              scheduled_local_date: '2026-11-13',
              scheduled_local_time: '09:00:00',
            }));
          await p.goto(s.origin + '/campaigns/' + v.id + '/dependencies');
          await p.getByRole('combobox', { name: /^Predecessor/ }).selectOption(a.id);
          await p.getByRole('combobox', { name: /^Successor/ }).selectOption(b.id);
          const r = waitResponse(p, '/campaigns/' + v.id + '/dependencies');
          await p.getByRole('button', { name: 'Add dependency', exact: true }).click();
          expect((await r).status()).toBe(201);
          await p.reload();
          await expect(p.locator('main')).toContainText('success_required');
          const cycle = await p.request.post(
            s.origin + '/api/v1/campaigns/' + v.id + '/dependencies',
            {
              data: {
                predecessor_activity_id: b.id,
                successor_activity_id: a.id,
                dependency_type: 'success_required',
              },
            },
          );
          expect(cycle.status()).toBe(422);
          return;
        }
        case 'R-794214d7':
        case 'R-ec41ffe0': {
          const v = await c(),
            clip = await video();
          const a = await once('videoActivity', () =>
            api('post', 'campaigns/' + v.id + '/activities', {
              activity_type: 'video_campaign',
              name: '[QA SYNTHETIC] WP7A4 pinned Video',
              sequence: 15,
              scheduled_local_date: '2026-11-14',
              scheduled_local_time: '10:00:00',
              product_id: product.id,
              video_generation_id: clip.id,
              video_output_id: clip.output_id,
              video_media_id: clip.output_media_id,
              video_version: 1,
              video_channel: 'youtube',
            }),
          );
          await p.goto(
            s.origin + '/campaigns/' + v.id + '/video' + (e.id === 'R-794214d7' ? '/' + a.id : ''),
          );
          await expect(p.locator('main')).toContainText('Video');
          await p.reload();
          await expect(p.locator('main')).toContainText(a.name);
          await expect(p.locator('main')).toContainText(clip.output_id);
          expect(a.product_id).toBe(product.id);
          expect(a.video_output_id).toBe(clip.output_id);
          return e.id === 'R-794214d7'
            ? defaultResult(
                'Exact approved Video binding and reload verified; the activityId route renders an overview rather than an activity-specific detail.',
              )
            : undefined;
        }
        case 'R-3feda36d': {
          const v = await social();
          await readDetail('/social/posts/' + v.id, 'social/posts/' + v.id, 'SocialPost');
          return defaultResult(
            'Canonical social draft and persisted identity checked; image/video-specific and stale-review permutations remain.',
          );
        }
        case 'L-22': {
          await p.goto(s.origin + '/social/compose');
          await expect(p.locator('main')).toContainText('Compose');
          const v = await social();
          await p.goto(s.origin + '/social/posts/' + v.id);
          await p.reload();
          return defaultResult(
            'Supported composer and persisted text draft exercised; Video composer needs a canonical approved Video output.',
          );
        }
        case 'R-55e822d5': {
          await p.goto(s.origin + '/marketplaces/overview');
          await expect(p.locator('main')).toContainText(/Marketplace|marketplace/);
          await p.reload();
          return defaultResult(
            'Overview and reload checked; full configured-channel snapshot requires remaining account fixtures.',
          );
        }
        case 'R-551d2f8c':
        case 'R-db243c36':
        case 'R-d6a495d5': {
          const channel =
            e.id === 'R-551d2f8c' ? 'flipkart' : e.id === 'R-db243c36' ? 'meesho' : 'amazon';
          const v = await listing(channel);
          await p.goto(s.origin + '/marketplaces/listings/' + v.id + '/' + channel);
          await expect(p.locator('main')).toContainText(new RegExp(channel, 'i'));
          await p.reload();
          await expect(p.locator('main')).toContainText(
            /blocked|missing|connect|unknown|readiness/i,
          );
          return defaultResult(
            'Exact catalog-linked draft/default-deny reviewed; complete channel readiness/review authorization transitions remain.',
          );
        }
        case 'R-730f1388': {
          const v = await media();
          await readDetail('/media/' + v.id, 'media/' + v.id, '64');
          expect(
            (await p.request.get(s.origin + '/api/v1/media/' + crypto.randomUUID())).status(),
          ).toBe(404);
          return;
        }
        case 'R-8f16bd41': {
          const v = await image();
          await readDetail(
            '/ai/images/assets/' + v.id,
            'ai/images/outputs/' + v.id,
            'Image review',
          );
          await expect(p.locator('main img')).toBeVisible();
          await p.getByRole('button', { name: 'Show history', exact: true }).click();
          await expect(p.locator('main')).toContainText('History');
          return;
        }
        case 'R-5e241b88':
        case 'R-75d260b7':
        case 'R-541d7261': {
          const v = await content();
          if (e.id === 'R-5e241b88') {
            const next = await api('post', 'ai/artifacts/' + v.id + '/regenerate', {});
            await p.goto(s.origin + '/ai/studio/artifacts/' + next.artifact_id + '/compare');
            await p
              .getByRole('combobox', { name: 'Previous version', exact: true })
              .selectOption(v.id);
            await p
              .getByRole('combobox', { name: 'Current version', exact: true })
              .selectOption(next.artifact_id);
            await expect(
              p.getByRole('group', { name: 'Artifact version comparison', exact: true }),
            ).toBeVisible();
            await p.reload();
            await expect(
              p.getByRole('combobox', { name: 'Current version', exact: true }),
            ).toHaveValue(next.artifact_id);
            expect((await api('get', 'ai/artifacts/' + v.id)).status).toBe('approved');
            expect((await api('get', 'ai/artifacts/' + next.artifact_id)).status).toBe(
              'pending_review',
            );
            return;
          }
          const route =
            e.id === 'R-5e241b88'
              ? '/ai/studio/artifacts/' + v.id + '/compare'
              : e.id === 'R-541d7261'
                ? '/approvals/' + v.id
                : '/ai/artifacts/' + v.id;
          await readDetail(route, 'ai/artifacts/' + v.id, 'Content review');
          await expect(p.locator('main')).toContainText(product.name);
          return;
        }
        case 'R-2e8db403': {
          await p.goto(s.origin + '/settings/publishing/connectors');
          await expect(p.locator('main')).toContainText(/WordPress|Shopify/);
          await p.reload();
          await expect(p.locator('main')).toContainText(/not configured|not_configured|disabled/i);
          return;
        }
        case 'R-756ae8b2':
        case 'R-af04ee8c': {
          await p.goto(s.origin + e.route);
          await expect(p).toHaveURL(/publishing\/destinations\/new/);
          await expect(p.getByLabel('Destination name', { exact: true })).toBeVisible();
          await p.reload();
          await expect(p.getByLabel('Destination name', { exact: true })).toBeVisible();
          return;
        }
        case 'R-a8d8b217': {
          const v = await publishing();
          await p.goto(s.origin + '/publishing/destinations/' + v.destination_id + '/edit');
          const field = p.getByLabel('Destination name', { exact: true });
          await field.fill('[QA SYNTHETIC] WP7A4 edited ' + run.label);
          expect(
            await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
          ).toBe(true);
          const r = waitResponse(p, '/destinations/' + v.destination_id, 'PATCH');
          await p.getByRole('button', { name: 'Save destination', exact: true }).click();
          expect((await r).status()).toBe(200);
          await p.reload();
          return;
        }
        case 'R-9b0fb4bc':
        case 'R-68adcdc8':
        case 'R-2b4d90d2':
        case 'R-30072869':
        case 'R-e309647e': {
          const v = await publishing();
          const type =
            e.id === 'R-9b0fb4bc'
              ? 'destinations'
              : e.id === 'R-68adcdc8'
                ? 'executions'
                : e.id === 'R-2b4d90d2'
                  ? 'schedules'
                  : e.id === 'R-30072869'
                    ? 'jobs'
                    : 'workers';
          const id =
            v[
              type === 'destinations'
                ? 'destination_id'
                : type === 'executions'
                  ? 'execution_id'
                  : type === 'schedules'
                    ? 'schedule_id'
                    : type === 'jobs'
                      ? 'job_id'
                      : 'worker_id'
            ];
          if (!id) throw new Blocked('CANONICAL_' + type.toUpperCase() + '_IDENTITY_NOT_AVAILABLE');
          await readDetail(
            (type === 'workers' ? '/operations/' : '/publishing/') + type + '/' + id,
            (type === 'workers' ? 'operations/' : 'publishing/') + type + '/' + id,
            type === 'workers'
              ? 'Worker'
              : type === 'executions'
                ? 'Publishing execution'
                : type === 'schedules'
                  ? 'Schedule'
                  : type === 'jobs'
                    ? 'Job'
                    : 'Destination',
          );
          return;
        }
        case 'R-9dc8a702': {
          const d = await publishing();
          const v = await api('post', 'workflows', {
            product_id: product.id,
            destination_id: d.destination_id,
          });
          await readDetail('/workflows/' + v.id, 'workflows/' + v.id, 'Workflow');
          const started = waitResponse(p, '/workflows/' + v.id + '/start');
          await p.getByRole('button', { name: 'Start', exact: true }).click();
          expect((await started).status()).toBe(200);
          await expect(p.locator('main')).toContainText('Human approval required');
          await p.reload();
          const waiting = await api('get', 'workflows/' + v.id);
          expect(waiting.status).toBe('waiting_for_approval');
          expect(waiting.artifact_status).toBe('pending_review');
          expect(waiting.publishing_execution_id).toBeNull();
          const cancelled = waitResponse(p, '/workflows/' + v.id + '/cancel');
          await p.getByRole('button', { name: 'Cancel Workflow', exact: true }).click();
          expect((await cancelled).status()).toBe(200);
          await p.reload();
          expect((await api('get', 'workflows/' + v.id)).status).toBe('cancelled');
          return;
        }
        case 'R-eb4987ba': {
          const v = await api('post', 'intelligence/supplier-portfolios', {
            name: '[QA SYNTHETIC] WP7A4 portfolio',
            scope_type: 'product',
            scope_reference: product.id,
            idempotency_key: 'wp7a4-' + run.label,
          });
          const id = v.id || v.portfolio?.id;
          if (!id) throw new Blocked('PORTFOLIO_RESPONSE_IDENTITY_UNRESOLVED');
          await p.goto(s.origin + '/intelligence/supplier-portfolios/' + id);
          await expect(p.locator('main')).toContainText(/Portfolio|portfolio/);
          await p.reload();
          const assessment = await api(
            'post',
            'intelligence/supplier-portfolios/' + id + '/assess',
            { idempotency_key: 'wp7a4-assess-' + run.label },
          );
          const replay = await api('post', 'intelligence/supplier-portfolios/' + id + '/assess', {
            idempotency_key: 'wp7a4-assess-' + run.label,
          });
          expect(replay.id ?? replay.assessment_version_id).toBe(
            assessment.id ?? assessment.assessment_version_id,
          );
          expect(assessment.id).toBeTruthy();
          const supplier = await api('post', 'intelligence/suppliers/manual', {
            display_name: '[QA SYNTHETIC] WP7A4 ' + run.label,
            country_code: 'IN',
            country: 'India',
            source_type: 'manual_entry',
            supplier_type: 'unknown',
            provenance: 'Explicit synthetic QA fixture, not verified supplier evidence or contact.',
          });
          const reconciled = await api(
            'post',
            'intelligence/cross-marketplace/suppliers/reconcile',
            { supplier_ids: [supplier.id] },
          );
          expect(reconciled.length).toBe(1);
          const membership = await api(
            'post',
            'intelligence/supplier-portfolios/' + id + '/members',
            {
              supplier_id: reconciled[0].id,
              associated_products: [product.id],
              evidence_freshness: 'unknown',
            },
          );
          expect(membership.supplier_id).toBe(reconciled[0].id);
          expect(membership.allocation_percent).toBeNull();
          await api('post', 'intelligence/supplier-portfolios/' + id + '/assess', {
            idempotency_key: 'wp7a4-assess-member-' + run.label,
          });
          await p.reload();
          await expect(p.locator('main')).toContainText(/unknown|insufficient|missing/i);
          await expect(p.locator('main')).toContainText(reconciled[0].id);
          await readDetail(
            '/intelligence/supplier-portfolios/' + id,
            'intelligence/supplier-portfolios/' + id,
            'Portfolio',
          );
          return;
        }
        case 'L-09': {
          const a = await content();
          await p.goto(s.origin + '/ai/artifacts/' + a.id);
          await p.getByRole('button', { name: 'Edit structured content', exact: true }).click();
          await p.getByRole('button', { name: 'Save as new version', exact: true }).click();
          await expect(p.locator('main')).toContainText(/approved|regenerate/i);
          await p.goto(s.origin + '/ai/history');
          await expect(p.locator('main')).toContainText(product.name);
          await p.reload();
          await p.goto(s.origin + '/ai/artifacts/' + a.id);
          // The existing legacy regeneration authority records an audit event, not a fabricated
          // Studio parent. Assert the contract it actually exposes and retain the approved source.
          const regenerated = await api('post', 'ai/artifacts/' + a.id + '/regenerate', {});
          expect(regenerated.artifact_id).toBeTruthy();
          await p.goto(s.origin + '/ai/artifacts/' + regenerated.artifact_id);
          await expect(p.locator('main')).toContainText('pending_review');
          await expect(p.getByRole('button', { name: 'Reject', exact: true })).toBeDisabled();
          await p
            .getByLabel('Rejection reason', { exact: true })
            .fill('Synthetic QA review rejects this candidate.');
          await p.getByRole('button', { name: 'Reject', exact: true }).click();
          await expect(p.locator('main')).toContainText('Status: rejected');
          await p.reload();
          expect((await api('get', 'ai/artifacts/' + regenerated.artifact_id)).status).toBe(
            'rejected',
          );
          expect((await api('get', 'ai/artifacts/' + a.id)).status).toBe('approved');
          return;
        }
        case 'L-10': {
          const staleProduct = await api('post', 'products', {
            brand_id: brand.id,
            name: '[QA SYNTHETIC] WP7A4 isolated freshness ' + run.label,
            product_type: 'physical',
            description: 'Original synthetic input',
            price_amount: '10.25',
            price_currency: 'INR',
          });
          await api('post', 'products/' + staleProduct.id + '/activate', {});
          await p.goto(s.origin + '/ai/studio');
          await p
            .getByRole('combobox', { name: 'Product', exact: true })
            .selectOption(staleProduct.id);
          const r = waitResponse(p, '/studio/generate');
          await p
            .getByRole('button', { name: 'Generate deterministic draft', exact: true })
            .click();
          const v = await (await r).json();
          await worker();
          await p.reload();
          await expect(p.locator('main')).toContainText(/completed|Generation status/);
          await api('patch', 'products/' + staleProduct.id, {
            description: 'Changed synthetic description; prior results must remain versioned.',
          });
          await p.getByRole('button', { name: 'Refresh artifacts', exact: true }).click();
          const pending = await api('post', 'ai/studio/generate', {
            product_ids: [staleProduct.id],
            channels: ['canonical'],
            content_types: ['product_title'],
            provider_key: 'deterministic_mock_v1',
            idempotency_key: 'wp7a4-stale-' + run.label,
          });
          await api('patch', 'products/' + staleProduct.id, {
            description: 'Second legitimate input revision.',
          });
          await worker();
          const stale = await api('get', 'ai/studio/generations/' + pending.id);
          expect(stale.outputs.every((o) => o.status === 'stale')).toBe(true);
          await p.goto(s.origin + '/ai/studio?generation=' + pending.id);
          await expect(p.locator('main')).toContainText(/stale|changed/i);
          await p.reload();
          return defaultResult(
            'Completed snapshot retained; queued old-context work rejects as stale after a Product change. Provider retry/supersession permutations remain.',
          );
        }
        case 'L-12': {
          const v = await image();
          await p.goto(s.origin + '/ai/images/assets/' + v.id);
          await expect(p.locator('main img')).toBeVisible();
          await p.getByRole('button', { name: 'Approve exact output', exact: true }).click();
          await p.reload();
          await expect(p.locator('main')).toContainText('approved');
          const regenerated = waitResponse(p, '/outputs/' + v.id + '/regenerate');
          await p.getByRole('button', { name: 'Regenerate', exact: true }).click();
          const next = (await (await regenerated).json()).outputs[0];
          expect(next.id).not.toBe(v.id);
          await p.waitForURL('**/ai/images/assets/' + next.id);
          await worker();
          await p.reload();
          await expect(p.locator('main img')).toBeVisible();
          const saved = await api('get', 'ai/images/outputs/' + next.id);
          expect(saved.status).not.toBe('approved');
          expect((await api('get', 'ai/images/outputs/' + v.id)).status).toBe('approved');
          await p.getByRole('button', { name: 'Show history', exact: true }).click();
          await expect(p.locator('main')).toContainText('History');
          return defaultResult(
            'Image regeneration/reload/source approval retained; injected provider failure/recovery still requires exact child controls.',
          );
        }
        case 'L-13': {
          await p.goto(s.origin + '/ai/studio/bulk');
          await p
            .getByRole('checkbox', {
              name: new RegExp(product.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')),
            })
            .check();
          await p.getByRole('button', { name: 'Review plan', exact: true }).click();
          const r = waitResponse(p, '/studio/bulk');
          const history = responseWait(
            p,
            (x) => x.url().endsWith('/studio/bulk') && x.request().method() === 'GET',
            { timeout: 12000 },
          );
          await p.getByRole('button', { name: /^Queue \d+ outputs$/ }).click();
          const v = await (await r).json();
          expect((await history).status()).toBe(200);
          await expect(p.getByRole('button', { name: 'Review plan', exact: true })).toBeEnabled();
          const cancelled = waitResponse(p, '/studio/bulk/' + v.id + '/cancel');
          await p.getByRole('button', { name: 'Cancel remaining', exact: true }).first().click();
          expect((await cancelled).status()).toBe(200);
          await p.reload();
          const saved = await api('get', 'ai/studio/bulk/' + v.id);
          expect(saved.status).toMatch(/cancel/);
          return defaultResult(
            'Canonical cancellation/reload exercised; partial success/provider retry combinations remain.',
          );
        }
        case 'L-14': {
          await p.goto(s.origin + '/ai/images/bulk');
          await p.getByRole('checkbox', { name: product.name, exact: true }).check();
          await p.getByRole('combobox', { name: /operation/i }).selectOption('resize');
          const missingSource = waitResponse(p, '/images/bulk/preview');
          await p.getByRole('button', { name: 'Review plan', exact: true }).click();
          expect((await missingSource).status()).toBe(200);
          await expect(p.locator('main')).toContainText(/source Media|source media|validation/i);
          await expect(
            p.getByRole('button', { name: 'Queue bulk generation', exact: true }),
          ).toBeDisabled();
          await p
            .getByRole('combobox', { name: /operation/i })
            .selectOption('marketplace_main_image');
          await p.getByLabel('7. Width', { exact: true }).fill('64');
          await p.getByLabel('Height', { exact: true }).fill('64');
          for (const channel of ['flipkart', 'meesho'])
            await p.getByRole('checkbox', { name: channel, exact: true }).uncheck();
          await p.getByRole('button', { name: 'Review plan', exact: true }).click();
          await expect(
            p.getByRole('button', { name: 'Queue bulk generation', exact: true }),
          ).toBeEnabled();
          const created = waitResponse(p, '/ai/images/bulk');
          await p.getByRole('button', { name: 'Queue bulk generation', exact: true }).click();
          const result = await created;
          expect(result.status()).toBe(202);
          const op = await result.json();
          memo.imageBulk = op;
          for (let n = 0; n < 4; n++) await worker(true);
          await p.getByRole('button', { name: 'Refresh operation status', exact: true }).click();
          await expect(p.getByRole('button', { name: 'Retry', exact: true }).first()).toBeVisible();
          const retried = waitResponse(p, '/images/bulk/' + op.id + '/retry-failed');
          await p.getByRole('button', { name: 'Retry', exact: true }).first().click();
          expect((await retried).status()).toBe(200);
          await worker();
          await p.getByRole('button', { name: 'Refresh operation status', exact: true }).click();
          await expect(p.getByRole('link', { name: 'Review', exact: true }).first()).toBeVisible();
          await p.reload();
          await expect(p.locator('main')).toContainText('Bulk operation');
          const saved = await api('get', 'ai/images/bulk/' + op.id);
          expect(saved.outputs.length).toBe(1);
          expect(saved.outputs[0].image_output_id).toBeTruthy();
          expect(saved.outputs[0].media_id).toBeTruthy();
          expect(saved.outputs[0].status).not.toBe('approved');
          return;
        }
        case 'L-15': {
          await p.goto(s.origin + '/ai/studio/seo');
          await p.getByRole('button', { name: 'Keywords', exact: true }).click();
          await p
            .getByLabel('Name', { exact: true })
            .fill('[QA SYNTHETIC] WP7A4 keywords ' + run.label);
          await p
            .getByLabel('Paste keywords', { exact: true })
            .fill('synthetic product\nlocal fixture');
          let r = waitResponse(p, '/ai/seo/keywords');
          await p.getByRole('button', { name: 'Save Keyword Set', exact: true }).click();
          expect((await r).status()).toBe(201);
          await p.getByRole('button', { name: 'Tags', exact: true }).click();
          await p
            .getByLabel('Tag set name', { exact: true })
            .fill('[QA SYNTHETIC] WP7A4 tags ' + run.label);
          await p.getByLabel('Tags', { exact: true }).fill('synthetic\nlocal');
          r = waitResponse(p, '/ai/seo/tags');
          await p.getByRole('button', { name: 'Save tags', exact: true }).click();
          expect((await r).status()).toBe(201);
          await p.reload();
          await p.getByRole('button', { name: 'Tags', exact: true }).click();
          const tags = await api('get', 'ai/seo/tags');
          expect(JSON.stringify(tags)).toContain('WP7A4 tags ' + run.label);
          return defaultResult(
            'Keyword/tag creation and tag reload executed; analysis history/reanalysis/context permutations remain.',
          );
        }
        case 'L-16': {
          const d = await publishing(),
            a = await content(),
            v = await c();
          const bound = await api('post', 'campaigns/' + v.id + '/activities', {
            activity_type: 'mock_publish',
            name: '[QA SYNTHETIC] WP7A4 content binding',
            sequence: 10,
            scheduled_local_date: '2026-11-14',
            scheduled_local_time: '09:00:00',
            product_id: product.id,
            artifact_id: a.id,
            destination_id: d.destination_id,
          });
          expect(bound.product_id).toBe(product.id);
          expect(bound.artifact_version).toBe(a.version_number);
          await p.goto(s.origin + '/campaigns/' + v.id);
          await p.reload();
          await expect(p.locator('main')).toContainText('content binding');
          return defaultResult(
            'Canonical product/approved-content activity binding persisted; full recovery/stale binding permutations remain.',
          );
        }
        case 'L-18':
        case 'L-19': {
          const voice = e.id === 'L-18',
            route = voice ? 'brand-voices' : 'presets';
          await p.goto(s.origin + '/ai/' + route);
          await p
            .getByLabel('Name', { exact: true })
            .fill('[QA SYNTHETIC] WP7A4 ' + route + ' ' + run.label);
          const r = waitResponse(p, '/studio/' + route);
          await p
            .getByRole('button', {
              name: voice ? 'Create Brand Voice' : 'Create preset',
              exact: true,
            })
            .click();
          const response = await r;
          expect(response.status()).toBe(201);
          const v = await response.json();
          const row = p.getByRole('listitem').filter({ hasText: v.name });
          let action = waitResponse(p, '/studio/' + route + '/' + v.id + '/default');
          await row.getByRole('button', { name: 'Set default', exact: true }).click();
          expect((await action).status()).toBe(200);
          await p.reload();
          await expect(p.locator('main')).toContainText(v.name);
          const saved = await api('get', 'ai/studio/' + route + '/' + v.id);
          expect(saved.is_default).toBe(true);
          action = waitResponse(p, '/studio/' + route + '/' + v.id + '/duplicate');
          await row.getByRole('button', { name: 'Duplicate', exact: true }).click();
          const duplicate = await (await action).json();
          expect(duplicate.id).not.toBe(v.id);
          await expect(p.locator('main')).toContainText(v.name);
          let selected = v;
          if (voice) {
            await row
              .filter({ hasText: 'v1' })
              .first()
              .getByRole('button', { name: 'Edit', exact: true })
              .click();
            await p.getByLabel('Tone', { exact: true }).fill('friendly');
            action = waitResponse(p, '/studio/brand-voices/' + v.id, 'PATCH');
            await p.getByRole('button', { name: 'Save new version', exact: true }).click();
            selected = await (await action).json();
            expect(selected.version).toBe(v.version + 1);
            expect(selected.id).not.toBe(v.id);
          }
          const payload = {
            product_ids: [product.id],
            channels: ['amazon'],
            content_types: ['marketplace_listing'],
            provider_key: 'deterministic_mock_v1',
            idempotency_key: 'wp7a4-context-' + route + '-' + run.label,
            [voice ? 'brand_voice_id' : 'preset_id']: selected.id,
          };
          const generated = await api('post', 'ai/studio/generate', payload);
          await worker();
          const done = await api('get', 'ai/studio/generations/' + generated.id);
          const artifact = await api('get', 'ai/studio/artifacts/' + done.outputs[0].artifact_id);
          expect(voice ? artifact.brand_voice_version : String(artifact.preset_version)).toBe(
            voice ? selected.version : String(selected.version),
          );
          await p.goto(s.origin + '/ai/artifacts/' + artifact.id);
          await p.reload();
          await expect(p.locator('main')).toContainText('pending_review');
          await p.goto(s.origin + '/ai/' + route);
          const exact = p
            .getByRole('listitem')
            .filter({ has: p.getByText(selected.name, { exact: true }) })
            .filter({ hasText: 'v' + selected.version })
            .first();
          action = waitResponse(p, '/studio/' + route + '/' + selected.id + '/archive');
          await exact.getByRole('button', { name: 'Archive', exact: true }).click();
          expect((await action).status()).toBe(200);
          await p.reload();
          expect((await api('get', 'ai/studio/' + route + '/' + selected.id)).archived).toBe(true);
          const denied = await p.request.post(s.origin + '/api/v1/ai/studio/generate', {
            data: { ...payload, idempotency_key: payload.idempotency_key + '-archived' },
          });
          expect(denied.status()).toBe(409);
          expect((await api('get', 'ai/studio/artifacts/' + artifact.id)).status).toBe(
            'pending_review',
          );
          return;
        }
        case 'L-20': {
          await content();
          await p.goto(s.origin + '/ai/usage');
          await expect(p.locator('main')).toContainText(/Usage|usage/);
          await p
            .getByRole('combobox', { name: 'Provider', exact: true })
            .selectOption('deterministic_mock_v1');
          await expect(p.locator('main')).toContainText('deterministic_mock_v1');
          const rows = await api('get', 'ai/usage/history?provider_key=deterministic_mock_v1');
          expect(rows.items.length).toBeGreaterThan(0);
          expect(rows.items.every((x) => x.provider_key === 'deterministic_mock_v1')).toBe(true);
          await expect(p.locator('main')).toContainText('Cost unavailable');
          await p.reload();
          const csv = await p.request.get(s.origin + '/api/v1/ai/usage/export');
          expect(csv.status()).toBe(200);
          expect(await csv.text()).toContain('deterministic_mock_v1');
          return;
        }
        case 'L-21': {
          await p.goto(s.origin + '/ai/video/bulk');
          await p.getByRole('checkbox', { name: product.name, exact: true }).check();
          await p.getByLabel('Duration', { exact: true }).fill('2');
          const preview = waitResponse(p, '/ai/video/bulk/preview');
          await p.getByRole('button', { name: 'Preview plan', exact: true }).click();
          expect((await preview).status()).toBe(200);
          const r = waitResponse(p, '/ai/video/bulk');
          await p.getByRole('button', { name: 'Confirm and queue', exact: true }).click();
          const response = await r;
          expect(response.status()).toBe(202);
          const op = await response.json();
          memo.videoBulk = op;
          await worker();
          await p.getByRole('button', { name: 'Refresh status', exact: true }).click();
          await expect(p.locator('main')).toContainText('complete');
          const saved = await api('get', 'ai/video/bulk/' + op.id);
          expect(saved.children.length).toBe(1);
          return defaultResult(
            'Actual local deterministic bulk Video preview, fingerprint, queued child and worker completion executed; cancel/retry/partial and browser reload identity remain.',
          );
        }
        case 'L-23': {
          await p.goto(s.origin + '/ads/marketing');
          await p.getByRole('button', { name: 'Create plan', exact: true }).click();
          await p.getByRole('combobox', { name: 'Brand', exact: true }).selectOption(brand.id);
          await p.getByRole('combobox', { name: 'Product', exact: true }).selectOption(product.id);
          for (let n = 0; n < 6; n++)
            await p.getByRole('button', { name: 'Next', exact: true }).click();
          await p.getByLabel('Total budget', { exact: true }).fill('250.50');
          await p.getByRole('button', { name: 'Next', exact: true }).click();
          await p.getByLabel('social allocation', { exact: true }).fill('125.25');
          await p.getByLabel('campaign allocation', { exact: true }).fill('125.25');
          for (let n = 0; n < 4; n++)
            await p.getByRole('button', { name: 'Next', exact: true }).click();
          const r = waitResponse(p, '/ads/marketing/plans/confirm');
          await p.getByRole('button', { name: 'Preview and confirm', exact: true }).click();
          const confirmation = await r;
          expect(confirmation.status()).toBe(201);
          const plan = await confirmation.json();
          memo.marketingPlan = plan;
          await p.reload();
          await expect(p.locator('main')).toContainText(/250\.5/);
          expect(plan.product_ids).toContain(product.id);
          expect(plan.automation_mode).toBe('manual');
          expect(plan.budget_envelope.allocations).toEqual({
            social: '125.25',
            campaign: '125.25',
          });
          return defaultResult(
            'Manual persisted plan preview/confirmation/reload exercised; recommendation/version/change permutations remain.',
          );
        }
        case 'L-24': {
          await p.goto(s.origin + '/settings/ai/providers');
          await expect(p.locator('main')).toContainText(/OpenAI|provider/);
          await p.reload();
          await expect(p.locator('main')).toContainText(
            /not configured|Not configured|disabled|Not tested/i,
          );
          const before = await api('get', 'ai/providers/openai_compatible/configuration');
          const url = p.getByLabel('Base URL', { exact: true });
          await url.fill('');
          await p.getByRole('button', { name: 'Save configuration', exact: true }).click();
          expect(await url.evaluate((e) => e.validity.valueMissing)).toBe(true);
          const after = await api('get', 'ai/providers/openai_compatible/configuration');
          expect(after.enabled).toBe(before.enabled);
          expect(after.configured).toBe(before.configured);
          await p.reload();
          return;
        }
        case 'L-25': {
          const legacy = await content();
          await p.goto(s.origin + '/ai/artifacts/' + legacy.id);
          await expect(
            p.getByRole('button', { name: 'Translate exact Artifact', exact: true }),
          ).toBeDisabled();
          const gen = await api('post', 'ai/studio/generate', {
            product_ids: [product.id],
            channels: ['canonical'],
            content_types: ['marketplace_listing'],
            provider_key: 'deterministic_mock_v1',
            idempotency_key: 'wp7a4-translation-source-' + run.label,
          });
          await worker();
          const generated = await api('get', 'ai/studio/generations/' + gen.id);
          let a = await api('get', 'ai/studio/artifacts/' + generated.outputs[0].artifact_id);
          await p.goto(s.origin + '/ai/artifacts/' + a.id);
          await p.getByRole('button', { name: 'Approve', exact: true }).click();
          await expect(p.locator('main')).toContainText('Status: approved');
          a = await api('get', 'ai/studio/artifacts/' + a.id);
          await p
            .getByRole('combobox', { name: 'Translation target locale', exact: true })
            .selectOption('hi-IN');
          const r = waitResponse(p, '/studio/generate');
          await p.getByRole('button', { name: 'Translate exact Artifact', exact: true }).click();
          expect((await r).status()).toBe(202);
          await worker();
          const rows = await api('get', 'ai/studio/artifacts?product_id=' + product.id);
          const translated = rows.find((x) => x.locale === 'hi-IN');
          expect(translated).toBeTruthy();
          expect(translated.status).toBe('pending_review');
          expect(translated.parent_artifact_id).toBe(a.id);
          await p.goto(s.origin + '/ai/artifacts/' + translated.id);
          await p.reload();
          await expect(p.locator('main')).toContainText('pending_review');
          const regen = await api('post', 'ai/studio/artifacts/' + a.id + '/regenerate', {});
          await worker();
          const regenerated = await api('get', 'ai/studio/generations/' + regen.id);
          const child = await api(
            'get',
            'ai/studio/artifacts/' + regenerated.outputs[0].artifact_id,
          );
          expect(child.parent_artifact_id).toBe(a.id);
          expect(child.status).toBe('pending_review');
          expect((await api('get', 'ai/studio/artifacts/' + a.id)).status).toBe('approved');
          const stale = await p.request.post(s.origin + '/api/v1/ai/studio/generate', {
            data: {
              product_ids: [product.id],
              channels: ['canonical'],
              content_types: ['marketplace_listing'],
              locale: 'hi-IN',
              operation: 'translation',
              generation_reason: 'translation',
              source_artifact_id: a.id,
              source_artifact_version: a.version_number + 100,
            },
          });
          expect(stale.status()).toBe(409);
          const localized = await api('post', 'ai/studio/generate', {
            product_ids: [product.id],
            channels: ['canonical'],
            content_types: ['product_title'],
            locale: 'te-IN',
            operation: 'localized_generation',
            generation_reason: 'localized_generation',
            idempotency_key: 'wp7a4-localize-' + run.label,
          });
          await worker();
          const localizedResult = await api('get', 'ai/studio/generations/' + localized.id);
          const localizedArtifact = await api(
            'get',
            'ai/studio/artifacts/' + localizedResult.outputs[0].artifact_id,
          );
          expect(localizedArtifact.parent_artifact_id).toBeNull();
          expect(localizedArtifact.status).toBe('pending_review');
          await p.goto(s.origin + '/ai/artifacts/' + child.id);
          await p.reload();
          await expect(p.locator('main')).toContainText('pending_review');
          return;
        }
        default:
          throw Error('UNMAPPED_ORIGINAL_COVERAGE_ID');
      }
    });
  Object.assign(
    report.fixtures.find((v) => v.context === run.label),
    { brand_id: brand.id, product_id: product.id },
  );
  const db = await p.request.get(s.origin + '/__qa/wp7a4/state', {
    headers: { 'x-qa-token': s.token },
  });
  if (db.ok()) report.database.push({ context: run.label, ...(await db.json()) });
}
try {
  for (const channel of focused ? ['chrome'] : ['chrome', 'msedge']) {
    const browser = await chromium.launch({ channel, headless: true });
    browsers.push(browser);
    report.versions[channel] = browser.version();
    for (const width of focused ? [1440] : [1440, 390]) {
      const run = await start(browser, s, { width, height: 900 }, packageKey + '-' + channel + '-' + width);
      runs.push(run);
      run.page.setDefaultTimeout(10000);
      run.page.on('dialog', (d) => d.accept());
      await authenticated(run.page);
      await campaign(run);
    }
  }
} catch (error) {
  report.setup_failure = {
    classification: 'OWNED_CAMPAIGN_SETUP_FAILED',
    safe_error: error.message.split('\n')[0].slice(0, 150),
  };
} finally {
  for (const run of runs) {
    try {
      await finish(run);
    } catch {
      report.trace_failure = true;
    }
  }
  for (const browser of browsers) await browser.close();
  if (seventh) {
    report.source_unchanged = JSON.stringify(testedSource) === JSON.stringify(await sourceFingerprint());
    await saveEvidence(path.join(s.folder, 'wp7a7-tested-source.json'), testedSource);
  }
  report.selected_ids = selected.map((e) => e.id);
  report.status =
    report.checks.length === contexts.length * selected.length
      ? selected.length === ledger.entries.length
        ? 'EXECUTED_ALL_ENTRIES'
        : 'EXECUTED_SELECTED_ENTRIES'
      : 'INTERRUPTED';
  await persist();
  ledger.status = 'INCOMPLETE';
  await saveEvidence(ledgerPath, ledger);
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP7A4 complete');
  console.log(
    JSON.stringify({
      token: s.token,
      status: report.status,
      checks: report.checks.length,
      counts: ledger.counts,
    }),
  );
}
process.exitCode = ['EXECUTED_ALL_ENTRIES', 'EXECUTED_SELECTED_ENTRIES'].includes(report.status)
  && (!seventh || report.source_unchanged)
  ? 0
  : 1;
