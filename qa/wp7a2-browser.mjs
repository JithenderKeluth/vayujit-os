import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { clearTimeout } from 'node:timers';
import { chromium, expect as baseExpect } from '@playwright/test';
import { start, capture, axe, finish } from './seller-browser-explore.mjs';
import { wp3Api, wp3Owner } from './wp3-fixtures.mjs';
const expect = baseExpect.configure({ timeout: 15000 });
const s = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const witness = await fetch(s.origin + '/__qa/witness').then((r) => r.json());
if (s.qa_phase !== 'WP7A2' || !s.synthetic || !witness.disposable || witness.token !== s.token)
  throw Error('EXACT_WP7A2_REQUIRED');
const report = {
  token: s.token,
  status: 'RUNNING',
  checks: [],
  scans: [],
  database: [],
  injected: [],
  versions: {},
  external_calls: false,
  historical_ads_502: 'UNREPRODUCED_CAUSE_UNCLASSIFIED',
};
const runs = [],
  browsers = [];
const persist = () =>
  fs.writeFile(path.join(s.folder, 'wp7a2-browser.json'), JSON.stringify(report, null, 2));
const responseFor = (p, fn) => p.waitForResponse(fn).catch(() => null);
async function check(run, id, fn) {
  try {
    await fn();
    report.checks.push({
      context: run.label,
      id,
      matrix_id: id === 'A' ? 'B' : 'L',
      status: 'PASS',
    });
  } catch (e) {
    report.checks.push({
      context: run.label,
      id,
      matrix_id: id === 'A' ? 'B' : 'L',
      status: 'FAIL',
      safe_error: e.message.split('\n')[0].slice(0, 300),
    });
    await capture(run, 'FAILED-' + id).catch(() => {});
  }
  await persist();
}
async function scan(run, label) {
  await capture(run, label, true);
  const result = await axe(run, label);
  report.scans.push({ context: run.label, ...result });
  expect(result.violations).toEqual([]);
}
async function state(run, label) {
  const r = await run.page.request.get(s.origin + '/__qa/wp7a2/state', {
    headers: { 'x-qa-token': s.token },
  });
  expect(r.status()).toBe(200);
  const v = await r.json();
  report.database.push({ context: run.label, label, ...v });
  await persist();
  return v;
}
async function control(run, scenario, id) {
  if (scenario === 'RECONSTRUCT') {
    const owner = report.database.find((d) => d.owner_id)?.owner_id;
    if (!owner) throw Error('AUTHENTICATED_OWNER_WITNESS_REQUIRED');
    const cookie = (await run.context.cookies(s.origin))
      .filter((c) => c.name === 'vayujit_session')
      .map((c) => c.name + '=' + c.value)
      .join('; ');
    const child = spawn(
      path.resolve('apps/api/.venv/Scripts/python.exe'),
      ['-m', 'qa.wp7a2_reconstruct', s.token, owner],
      {
        cwd: process.cwd(),
        env: {
          ...process.env,
          PYTHONPATH: [process.cwd(), path.resolve('apps/api')].join(path.delimiter),
        },
        windowsHide: true,
        stdio: ['pipe', 'pipe', 'pipe'],
      },
    );
    child.stdin.end(JSON.stringify({ cookie, campaign_id: id }));
    let stdout = '';
    child.stdout.on('data', (d) => (stdout += d));
    child.stderr.on('data', () => {}); // never persist arbitrary child diagnostics
    const code = await new Promise((resolve) => {
      const timer = setTimeout(() => child.kill(), 45000);
      child.once('error', () => {
        clearTimeout(timer);
        resolve(-1);
      });
      child.once('exit', (code) => {
        clearTimeout(timer);
        resolve(code);
      });
    });
    if (code !== 0) throw Error('FRESH_PROCESS_RECONSTRUCTION_FAILED');
    // The canonical app may log safe request telemetry to stdout. Select only
    // the one scoped reconstruction envelope; never persist other output.
    const envelopes = stdout.split(/\r?\n/).flatMap((line) => {
      try {
        const value = JSON.parse(line);
        return value.token === s.token && value.fresh_process === true ? [value] : [];
      } catch {
        return [];
      }
    });
    if (envelopes.length !== 1) throw Error('RECONSTRUCTION_ENVELOPE_INVALID');
    const value = envelopes[0];
    if (value.token !== s.token || !value.fresh_process)
      throw Error('RECONSTRUCTION_SCOPE_MISMATCH');
    expect(value.authenticated_api_process).toBe(true);
    expect(value.api_campaign_ids).toContain(id);
    report.database.push({ context: run.label, label: scenario, ...value });
    await persist();
    return value;
  }
  const r = await run.page.request.post(s.origin + '/__qa/wp7a2/control', {
    headers: { 'x-qa-token': s.token },
    data: { scenario, id },
    timeout: scenario === 'RECONSTRUCT' ? 65000 : 30000,
  });
  expect(r.status()).toBe(200);
  const v = await r.json();
  report.database.push({ context: run.label, label: scenario, ...v });
  await persist();
  return v;
}
async function startResearch(p, goal) {
  await p.goto(s.origin + '/intelligence/business-agent?goal_id=' + goal.id);
  const started = responseFor(
    p,
    (r) => /\/runs\/[^/]+\/start$/.test(r.url()) && r.request().method() === 'POST',
  );
  await p
    .locator('.goal-card.selected')
    .getByRole('button', { name: 'Start run', exact: true })
    .click();
  const r = await started;
  expect(r.status()).toBe(200);
  return r.json();
}
async function research(run, api, label) {
  const p = run.page;
  await check(run, 'A', async () => {
    const goal = await api('post', 'intelligence/business-agent/goals', {
      raw_goal: `[QA SYNTHETIC] WP7A2 ${label}. Find products in Home & Kitchen category for Amazon India with INR 300000.`,
      idempotency_key: 'wp7a-' + label + '-original',
    });
    await api('post', `intelligence/business-agent/goals/${goal.id}/plan`, {});
    const old = await startResearch(p, goal);
    expect(old.candidates.length).toBeGreaterThan(0);
    const before = await state(run, 'A-original');
    await p
      .locator('.goal-card.selected')
      .getByRole('button', { name: 'Prepare a revised goal', exact: true })
      .click();
    await p
      .locator('textarea[name=goal]')
      .fill(
        `[QA SYNTHETIC] WP7A2 ${label}. Find products in Travel Accessories category for Amazon India with INR 150000.`,
      );
    const created = responseFor(
      p,
      (r) =>
        r.url().endsWith('/business-agent/goals') &&
        r.request().method() === 'POST' &&
        r.status() === 201,
    );
    await p.getByRole('button', { name: 'Create research goal', exact: true }).click();
    const revised = await (await created).json();
    await p
      .locator('.goal-card.selected')
      .getByRole('button', { name: 'Create versioned research plan', exact: true })
      .click();
    const next = await startResearch(p, revised);
    expect(next.id).not.toBe(old.id);
    expect(next.candidates.length).toBeGreaterThan(0);
    const after = await state(run, 'A-revised');
    expect(after.goals.find((g) => g.id === goal.id).inputs_sha256).toBe(
      before.goals.find((g) => g.id === goal.id).inputs_sha256,
    );
    expect(after.goals.find((g) => g.id === revised.id).inputs_sha256).not.toBe(
      before.goals.find((g) => g.id === goal.id).inputs_sha256,
    );
    for (const c of next.candidates) expect(c.category).toBe('Travel Accessories');
    const current = await api(
      'get',
      `intelligence/product-opportunities/research-results?goal_id=${revised.id}`,
    );
    expect(current.active_goal_id).toBe(revised.id);
    expect(current.active_run_ids).not.toContain(old.id);
    const retries = await Promise.all(
      [1, 2].map(() => api('post', `intelligence/business-agent/runs/${next.id}/retry`, {})),
    );
    expect(retries.every((r) => r.id === next.id)).toBe(true);
    // Deliver an older run response after navigation to the revised context.
    let release;
    const held = new Promise((r) => (release = r));
    let observed;
    const seen = new Promise((r) => (observed = r));
    const pattern = '**/api/v1/intelligence/business-agent/goals/' + goal.id + '/runs/latest*';
    await p.route(
      pattern,
      async (route) => {
        const r = await route.fetch();
        observed();
        await held;
        await route.fulfill({ response: r }).catch(() => {});
      },
      { times: 1 },
    );
    try {
      await p.goto(s.origin + '/intelligence/business-agent?goal_id=' + goal.id);
      await Promise.race([
        seen,
        new Promise((_, reject) =>
          setTimeout(() => reject(Error('OLD_RESPONSE_NOT_OBSERVED')), 15000),
        ),
      ]);
      await p.goto(s.origin + '/intelligence/business-agent?goal_id=' + revised.id);
    } finally {
      release();
      await p.unroute(pattern);
    }
    await expect(p.locator('.goal-card.selected')).toContainText('Travel Accessories');
    await p.reload();
    await expect(p.locator('.goal-card.selected')).toContainText('Travel Accessories');
    const original = await api('get', `intelligence/business-agent/runs/${old.id}`);
    expect(original.candidates.map((c) => c.id)).toEqual(old.candidates.map((c) => c.id));
    await p.goto(
      s.origin +
        `/intelligence/product-opportunities/${old.candidates[0].id}?goal_id=${revised.id}`,
    );
    await expect(p.locator('main')).toContainText('Outside the active research goal');
    await expect(
      p.getByRole('button', { name: 'Select this product for supplier research', exact: true }),
    ).toHaveCount(0);
    await scan(run, 'A-stale-context-reference-only');
    const final = await state(run, 'A-persisted');
    expect(final.runs.filter((r) => r.goal_id === revised.id)).toHaveLength(1);
    expect(
      final.candidates.every(
        (c) =>
          c.tags.includes('LOCAL_DETERMINISTIC_RESEARCH_FIXTURE') &&
          c.evidence_state !== 'verified',
      ),
    ).toBe(true);
  });
}
async function creative(run, api, brand, product, label) {
  const p = run.page;
  await check(run, 'B', async () => {
    await p.goto(s.origin + '/ai/video');
    await p.getByRole('combobox', { name: 'Brand', exact: true }).selectOption(brand.id);
    await p.getByRole('combobox', { name: 'Product', exact: true }).selectOption(product.id);
    const queued = responseFor(
      p,
      (r) => r.url().endsWith('/ai/video/queue') && r.request().method() === 'POST',
    );
    await p.getByRole('button', { name: 'Queue Video', exact: true }).click();
    const r = await queued;
    expect(r.status()).toBe(202);
    const gen = await r.json();
    const failed = await control(run, 'VIDEO_FAILURE', gen.id);
    const job = failed.creative_jobs.find(
      (j) => j.correlation === failed.videos.find((v) => v.id === gen.id).correlation,
    );
    expect(job.state).toBe('failed');
    await p.reload();
    await p
      .locator('#videos tr')
      .filter({ has: p.getByText(product.id, { exact: true }) })
      .getByRole('button', { name: 'Open review', exact: true })
      .click();
    await p.getByRole('button', { name: 'Recovery', exact: true }).click();
    await expect(p.locator('#history')).toContainText('ai.video.provider_unavailable');
    await scan(run, 'B-failed-local-job');
    const retried = responseFor(
      p,
      (r) =>
        r.url().endsWith('/generations/' + gen.id + '/recovery') && r.request().method() === 'POST',
    );
    const retryButton = p.getByRole('button', { name: 'Retry failed Video', exact: true });
    await retryButton.focus();
    await expect(retryButton).toBeFocused();
    await retryButton.press('Enter');
    const response = await retried;
    expect(response.status()).toBe(200);
    const request = response.request().postDataJSON();
    const repeats = await Promise.all(
      [1, 2].map(() =>
        p.request.post(s.origin + `/api/v1/ai/video/generations/${gen.id}/recovery`, {
          data: request,
        }),
      ),
    );
    expect(repeats.every((r) => r.status() === 200)).toBe(true);
    const retryState = await state(run, 'B-queued-retry');
    expect(retryState.creative_jobs.find((j) => j.id === job.id).state).toBe('queued');
    expect(retryState.creative_jobs.find((j) => j.id === job.id).error).toBeNull();
    await p.reload();
    await expect(
      p.locator('#videos tr').filter({ has: p.getByText(product.id, { exact: true }) }),
    ).toContainText('queued');
    const second = await control(run, 'VIDEO_FAILURE', gen.id);
    expect(second.creative_jobs.find((j) => j.id === job.id).attempts).toBe(job.attempts + 1);
    expect(second.videos.find((v) => v.id === gen.id).status).toBe('failed');
    expect(second.videos.find((v) => v.id === gen.id).output_count).toBe(0);
    await p.reload();
    await expect(
      p.locator('#videos tr').filter({ has: p.getByText(product.id, { exact: true }) }),
    ).toContainText('failed');
    await scan(run, 'B-second-failure-persisted');
  });
  await check(run, 'C', async () => {
    const board = await api('post', 'ai/video/storyboards', {
      brand_id: brand.id,
      product_id: product.id,
      scenes: [
        {
          stable_key: 'one',
          scene_order: 1,
          duration_seconds: 2,
          scene_text: '[QA SYNTHETIC] approved original ' + label,
        },
      ],
    });
    await p.goto(s.origin + '/ai/video');
    await p
      .locator('#storyboards .card')
      .filter({ has: p.getByText(board.id, { exact: false }) })
      .getByRole('button', { name: 'Open editor', exact: true })
      .click();
    const editor = p.locator('.editor');
    const approved = responseFor(
      p,
      (r) =>
        r.url().endsWith('/storyboards/' + board.id + '/approve') &&
        r.request().method() === 'POST',
    );
    const approveButton = editor.getByRole('button', { name: 'Approve', exact: true });
    await approveButton.focus();
    await expect(approveButton).toBeFocused();
    await approveButton.press('Enter');
    expect((await approved).status()).toBe(200);
    const original = await api('get', 'ai/video/storyboards/' + board.id);
    expect(original.state).toBe('approved');
    const before = await state(run, 'C-approved');
    expect(before.boards.find((b) => b.id === board.id).approved_by).toBe(before.owner_id);
    await editor
      .getByLabel('On-screen text', { exact: true })
      .fill('[QA SYNTHETIC] cloned edit ' + label);
    const saved = responseFor(
      p,
      (r) => r.url().endsWith('/storyboards/' + board.id) && r.request().method() === 'PUT',
    );
    await editor.getByRole('button', { name: 'Save', exact: true }).click();
    const response = await saved;
    expect(response.status()).toBe(200);
    const clone = await response.json();
    const body = response.request().postDataJSON();
    expect(clone.id).not.toBe(board.id);
    expect(clone.version).toBe(original.version + 1);
    expect(clone.state).toBe('draft');
    expect(clone.source_artifact_id).toBe(original.source_artifact_id);
    const duplicate = await Promise.all(
      [1, 2].map(() =>
        p.request.put(s.origin + '/api/v1/ai/video/storyboards/' + board.id, { data: body }),
      ),
    );
    for (const r of duplicate) {
      expect(r.status()).toBe(200);
      expect((await r.json()).id).toBe(clone.id);
    }
    expect(await api('get', 'ai/video/storyboards/' + board.id)).toEqual(original);
    const rows = await state(run, 'C-clone-lineage');
    expect(rows.boards.filter((b) => b.product_id === product.id)).toHaveLength(2);
    expect(rows.boards.find((b) => b.id === clone.id).approved_by).toBeNull();
    expect(
      rows.audit.some(
        (e) =>
          e.entity_id === clone.id &&
          e.metadata.source_storyboard_id === board.id &&
          e.metadata.approval_inherited === false,
      ),
    ).toBe(true);
    await p.reload();
    await p
      .locator('#storyboards .card')
      .filter({ has: p.getByText(clone.id, { exact: false }) })
      .getByRole('button', { name: 'Open editor', exact: true })
      .click();
    await expect(p.locator('.editor')).toContainText('Storyboard v2 editor');
    await expect(p.locator('.editor').getByLabel('On-screen text', { exact: true })).toHaveValue(
      '[QA SYNTHETIC] cloned edit ' + label,
    );
    await p
      .locator('.editor')
      .getByLabel('On-screen text', { exact: true })
      .fill('[QA SYNTHETIC] draft revision ' + label);
    await p.keyboard.press('Tab');
    await p.keyboard.press('Shift+Tab');
    await expect(p.locator('.editor').getByLabel('On-screen text', { exact: true })).toBeFocused();
    const draftSave = responseFor(
      p,
      (r) => r.url().endsWith('/storyboards/' + clone.id) && r.request().method() === 'PUT',
    );
    await p.locator('.editor').getByRole('button', { name: 'Save', exact: true }).press('Space');
    const updated = await (await draftSave).json();
    expect(updated.id).toBe(clone.id);
    expect(updated.row_version).toBe(clone.row_version + 1);
    expect(updated.state).toBe('draft');
    await p.reload();
    await p
      .locator('#storyboards .card')
      .filter({ has: p.getByText(clone.id, { exact: false }) })
      .getByRole('button', { name: 'Open editor', exact: true })
      .click();
    await expect(p.locator('.editor').getByLabel('On-screen text', { exact: true })).toHaveValue(
      '[QA SYNTHETIC] draft revision ' + label,
    );
    expect(await api('get', 'ai/video/storyboards/' + board.id)).toEqual(original);
    await scan(run, 'C-immutable-original-draft-clone');
  });
}
async function ads(run, api, product, label) {
  const p = run.page;
  await check(run, 'D', async () => {
    await p.goto(s.origin + '/ads/accounts');
    await p.getByRole('button', { name: 'Add account', exact: true }).click();
    const form = p.locator('form');
    const name = '[QA SYNTHETIC] WP7A2 account ' + label;
    await form.getByLabel('Display name', { exact: true }).fill(name);
    await form.getByLabel('External account ID', { exact: true }).fill('qa-wp7a2-' + label);
    await form
      .getByLabel('Credential (write only)', { exact: true })
      .fill('QA-SYNTHETIC-NOT-A-REAL-CREDENTIAL');
    await form.getByRole('button', { name: 'Save account', exact: true }).click();
    const row = p.getByRole('row').filter({ has: p.getByText(name, { exact: true }) });
    await row.getByRole('button', { name: 'Validate', exact: true }).click();
    await expect(row).toContainText('Validated');
    await row.getByRole('button', { name: 'Enable', exact: true }).click();
    await expect(row).toContainText('Enabled');
    const account = (await api('get', 'ads/accounts')).find((a) => a.display_name === name);
    expect(account.environment).toBe('local');
    await p.goto(s.origin + '/ads/create');
    await p.locator('select[name=account_id]').selectOption(account.id);
    await p
      .getByLabel('Campaign name', { exact: true })
      .fill('[QA SYNTHETIC] WP7A2 campaign ' + label);
    await p.getByRole('button', { name: 'Next', exact: true }).click();
    await p.getByRole('combobox', { name: 'Product', exact: true }).selectOption(product.id);
    await p.getByRole('button', { name: 'Next', exact: true }).click();
    await p.getByRole('button', { name: 'Next', exact: true }).click();
    await p.getByLabel('Amount', { exact: true }).fill('25.55');
    await p.getByRole('button', { name: 'Next', exact: true }).click();
    const previewed = responseFor(
      p,
      (r) => r.url().endsWith('/ads/campaigns/preview') && r.request().method() === 'POST',
    );
    await p.getByRole('button', { name: 'Run server preview', exact: true }).click();
    expect((await previewed).status()).toBe(200);
    for (let n = 0; n < 7; n++) await p.getByRole('button', { name: 'Next', exact: true }).click();
    await expect(
      p.getByRole('button', { name: 'Confirm and queue campaign', exact: true }),
    ).toBeDisabled();
    await p.locator('input[name=confirm_checked]').check();
    const confirmed = responseFor(
      p,
      (r) => r.url().endsWith('/ads/campaigns/confirm') && r.request().method() === 'POST',
    );
    await p.getByRole('button', { name: 'Confirm and queue campaign', exact: true }).click();
    const response = await confirmed;
    expect(response.status()).toBe(200);
    const campaign = (await response.json()).campaign;
    await p.reload();
    const before = await state(run, 'D-prepared');
    const reconstructed = await control(run, 'RECONSTRUCT', campaign.id);
    expect(reconstructed.fresh_process).toBe(true);
    expect(reconstructed.ads_campaigns).toEqual(before.ads_campaigns);
    await control(run, 'ADS_FAILURE', campaign.id);
    await p.goto(s.origin + '/ads/recovery');
    const failureRow = p
      .getByRole('row')
      .filter({ has: p.getByRole('cell', { name: 'ads.connector_unavailable', exact: true }) });
    await expect(failureRow).toContainText('Observed');
    await scan(run, 'D-observed-recoverable-failure');
    const recovery = responseFor(
      p,
      (r) => r.url().endsWith('/ads/recovery') && r.request().method() === 'POST',
    );
    await failureRow.getByRole('button', { name: 'retry', exact: true }).click();
    const recovered = await recovery;
    expect(recovered.status()).toBe(200);
    const body = recovered.request().postDataJSON();
    const result = await recovered.json();
    const repeated = await Promise.all(
      [1, 2].map(() => p.request.post(s.origin + '/api/v1/ads/recovery', { data: body })),
    );
    for (const r of repeated) {
      expect(r.status()).toBe(200);
      expect((await r.json()).job_id).toBe(result.job_id);
    }
    await p.reload();
    const final = await state(run, 'D-recovered');
    expect(final.ads_recoveries.filter((r) => r.entity_id === campaign.id)).toHaveLength(1);
    expect(final.ads_campaigns.find((c) => c.id === campaign.id).remote).toBe(false);
    const fresh = await control(run, 'RECONSTRUCT', campaign.id);
    expect(fresh.ads_recoveries).toEqual(final.ads_recoveries);
    expect(fresh.ads_jobs).toEqual(final.ads_jobs);
    const stale = await p.request.post(s.origin + '/api/v1/ads/recovery', {
      data: { ...body, idempotency_key: body.idempotency_key + '-stale' },
    });
    expect(stale.status()).toBe(409);
    await control(run, 'ADS_FAILURE', campaign.id);
    await p.reload();
    const secondRecovery = responseFor(
      p,
      (r) => r.url().endsWith('/ads/recovery') && r.request().method() === 'POST',
    );
    await failureRow.getByRole('button', { name: 'retry', exact: true }).click();
    const secondResponse = await secondRecovery;
    expect(secondResponse.status()).toBe(200);
    expect(secondResponse.request().postDataJSON().idempotency_key).not.toBe(body.idempotency_key);
    const twice = await state(run, 'D-second-failure-new-recovery');
    expect(twice.ads_recoveries.filter((r) => r.entity_id === campaign.id)).toHaveLength(2);
    expect(twice.ads_campaigns.find((c) => c.id === campaign.id).remote).toBe(false);
    for (const route of ['ads/overview', 'ads/comparison', 'ads/campaigns'])
      expect((await p.request.get(s.origin + '/api/v1/' + route)).status()).toBe(200);
    await scan(run, 'D-recovery-persisted-no-external-execution');
  });
}
try {
  let brand;
  for (const channel of process.argv.includes('--focused') ? ['chrome'] : ['chrome', 'msedge']) {
    const browser = await chromium.launch({ channel, headless: true });
    browsers.push(browser);
    report.versions[channel] = browser.version();
    for (const width of process.argv.includes('--focused') ? [1440] : [1440, 390]) {
      const label = `wp7a2-${channel}-${width}`;
      const run = await start(browser, s, { width, height: 900 }, label);
      runs.push(run);
      const p = run.page;
      p.setDefaultTimeout(15000);
      p.on('dialog', (d) => d.accept());
      const setup = await p.request
        .get(s.origin + '/api/v1/auth/setup-status')
        .then((r) => r.json());
      await p.goto(s.origin + (setup.ownerExists ? '/login' : '/setup'));
      if (!setup.ownerExists) {
        await p.locator('#full-name').fill('[QA SYNTHETIC] WP7A2 Owner');
        await p.locator('#confirmation').fill(wp3Owner.password);
      }
      await p.locator('#email').fill(wp3Owner.email);
      await p.locator('#password').fill(wp3Owner.password);
      await p
        .getByRole('button', { name: setup.ownerExists ? 'Sign in' : 'Create owner', exact: true })
        .click();
      await p.waitForURL('**/dashboard');
      const api = wp3Api(p, s.origin);
      if (!brand) brand = await api('post', 'brands', { name: '[QA SYNTHETIC] WP7A2 Brand' });
      const product = await api('post', 'products', {
        brand_id: brand.id,
        name: '[QA SYNTHETIC] WP7A2 ' + label,
        sku: 'QA-' + label,
        product_type: 'physical',
        description: 'Disposable synthetic test context, not real evidence.',
        price_amount: '100.25',
        price_currency: 'INR',
      });
      await api('post', `products/${product.id}/activate`, {});
      await research(run, api, label);
      await creative(run, api, brand, product, label);
      await ads(run, api, product, label);
    }
  }
} catch (e) {
  report.startup_failure = {
    code: /^WP3_FIXTURE_\d+_[a-z-]+$/.test(e.message) ? e.message : 'WP7A2_SETUP_FAILED',
    raw_output_persisted: false,
  };
} finally {
  for (const run of runs) await finish(run);
  for (const b of browsers) await b.close();
  report.status =
    report.checks.length === (process.argv.includes('--focused') ? 4 : 16) &&
    report.checks.every((c) => c.status === 'PASS')
      ? 'PASS'
      : 'INCOMPLETE';
  await persist();
  await fs.writeFile(path.join(s.folder, 'stop.request'), 'WP7A2 complete');
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
