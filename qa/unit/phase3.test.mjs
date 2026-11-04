import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import { setImmediate } from 'node:timers';
import Ajv2020 from 'ajv/dist/2020.js';
import { allowRequest, phase3ApiComplete, certificationStatus } from '../safety.mjs';
import { serve } from '../server.mjs';

test('Phase 3 denies real connector/credential/worker mutations', () => {
  const origin = 'http://127.0.0.1:49123';
  for (const path of [
    '/api/v1/marketplaces/accounts/abc/validate',
    '/api/v1/amazon/execute',
    '/api/v1/operations/action-center/policy',
    '/api/v1/publishing/jobs/execute',
    '/api/v1/marketplaces/sync',
  ])
    assert.equal(allowRequest(origin + path, 'POST', origin, '3'), false, path);
  assert.equal(
    allowRequest('https://example.com/api/v1/inventory/items', 'POST', origin, '3'),
    false,
  );
});

test('Phase 3 explicit local-only writes do not leak into Phase 1/2', () => {
  const origin = 'http://127.0.0.1:49123';
  for (const path of [
    '/api/v1/inventory/items',
    '/api/v1/orders/fake/events',
    '/api/v1/financial/events',
    '/api/v1/operations/action-center/signals/1234-5678/action',
  ]) {
    assert.equal(allowRequest(origin + path, 'POST', origin, '3'), true, path);
    for (const phase of ['1', '2'])
      assert.equal(allowRequest(origin + path, 'POST', origin, phase), false);
  }
});

test('Phase 3 certification fails with missing, skipped, errored, nonzero or short API results', () => {
  const valid = {
    process_exit_code: 0,
    tests: Array.from({ length: 18 }, () => ({ status: 'PASS' })),
    passed: 18,
    failed: 0,
    errors: 0,
    skipped: 0,
  };
  assert.equal(phase3ApiComplete(valid), true);
  for (const bad of [
    undefined,
    {},
    { ...valid, skipped: 1 },
    { ...valid, process_exit_code: 1 },
    { ...valid, tests: [] },
    { ...valid, errors: 1 },
    { ...valid, tests: [{ status: 'FAIL' }] },
  ])
    assert.equal(phase3ApiComplete(bad), false);
  assert.equal(certificationStatus([], [], 6), 'INCOMPLETE');
});

test('Phase 3 generated finding schema and inherited backlog stay explicit', (t) => {
  if (!fs.existsSync('docs/qa/phase-3-report.json')) {
    t.skip('Report not generated yet; schema validation is not executed.');
    return;
  }
  const ajv = new Ajv2020({ allErrors: true });
  ajv.addSchema(JSON.parse(fs.readFileSync('qa/finding.schema.json')), 'finding.schema.json');
  const validate = ajv.compile(JSON.parse(fs.readFileSync('qa/finding-v2.schema.json')));
  const report = JSON.parse(fs.readFileSync('docs/qa/phase-3-report.json'));
  for (const f of [
    ...report.findings,
    ...report.confirmed_bugs,
    ...report.reviewed_findings,
    ...report.inherited_open_findings,
  ])
    assert.equal(validate(f), true, JSON.stringify(validate.errors));
  assert.equal(report.executive_summary.full_application_coverage, false);
});

test('QA proxy survives upstream disconnection after response headers', async () => {
  const upstream = http.createServer((_req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.write('{');
    setImmediate(() => res.destroy());
  });
  await new Promise((resolve) => upstream.listen(0, '127.0.0.1', resolve));
  const proxy = await serve(0, upstream.address().port, '3');
  try {
    const origin = `http://127.0.0.1:${proxy.address().port}`;
    await assert.rejects(async () => {
      const response = await fetch(origin + '/api/v1/financial/summary');
      await response.text();
    });
    assert.equal((await fetch(origin + '/login')).status, 200);
  } finally {
    await new Promise((resolve) => proxy.close(resolve));
    await new Promise((resolve) => upstream.close(resolve));
  }
});

test('QA restart and account fixture controls deny invalid identity and credentials', async () => {
  let restarts = 0;
  const proxy = await serve(0, 1, '3', {
    token: '0123456789abcdef',
    restart: async () => {
      restarts++;
    },
  });
  try {
    const origin = `http://127.0.0.1:${proxy.address().port}`;
    assert.equal((await fetch(origin + '/__qa/restart', { method: 'POST' })).status, 403);
    for (const data of [
      { environment: 'production', credentials: {} },
      { environment: 'sandbox', credentials: { token: 'never-forward' } },
    ]) {
      assert.equal(
        (
          await fetch(origin + '/api/v1/marketplaces/accounts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
          })
        ).status,
        403,
      );
    }
    assert.equal(restarts, 0);
  } finally {
    await new Promise((resolve) => proxy.close(resolve));
  }
});
