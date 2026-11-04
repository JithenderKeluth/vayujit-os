import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  allowRequest,
  finding,
  safeRoute,
  certificationStatus,
  unexpectedServerErrors,
} from '../safety.mjs';
import QaReporter from '../reporter.mjs';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { markdown } from '../report.mjs';
import { registeredOperations } from '../runtime-inventory.mjs';
import Ajv2020 from 'ajv/dist/2020.js';
import { componentPathForRoute } from '../audit.mjs';

const origin = 'http://127.0.0.1:43219';
test('Phase 2 permits bounded local assessments but never dispatch or worker execution', () => {
  const id = '11111111-1111-1111-1111-111111111111';
  assert.equal(
    allowRequest(
      origin + `/api/v1/intelligence/product-opportunities/${id}/assessments/${id}/landed-cost`,
      'POST',
      origin,
      '2',
    ),
    true,
  );
  assert.equal(
    allowRequest(origin + '/api/v1/intelligence/suppliers/research', 'POST', origin),
    false,
  );
  for (const route of [
    '/api/v1/intelligence/engagements/send',
    '/api/v1/marketplaces/amazon/execute',
    '/api/v1/intelligence/business-agent/runs/123/start',
    '/api/v1/financial/events',
  ]) {
    assert.equal(allowRequest(origin + route, 'POST', origin, '2'), false);
  }
});
test('route inventory resolves both lazy-loaded and directly imported components', () => {
  const imports = new Map([['AdsWorkspaceComponent', './ads/ads-workspace.component']]);
  assert.equal(
    componentPathForRoute('', 'AdsWorkspaceComponent', imports, 'src'),
    path.join('src', 'ads/ads-workspace.component.ts'),
  );
  assert.equal(
    componentPathForRoute(
      "import('./catalog/catalog-workspace.component')",
      undefined,
      imports,
      'src',
    ),
    path.join('src', 'catalog/catalog-workspace.component.ts'),
  );
  assert.equal(componentPathForRoute('', undefined, imports, 'src'), null);
});
test('503 is permitted only for an explicitly injected route/status pair', () => {
  const signals = {
    expected_http_errors: [],
    http_errors: [{ path: '/api/v1/products', status: 503 }],
  };
  assert.equal(unexpectedServerErrors(signals).length, 1);
  signals.expected_http_errors.push({ path: '/api/v1/products', status: 503 });
  assert.equal(unexpectedServerErrors(signals).length, 0);
  signals.http_errors.push({ path: '/api/v1/financials', status: 503 });
  assert.equal(unexpectedServerErrors(signals).length, 1);
});
test('finding schema accepts actual findings and rejects missing fields and unknown severity', () => {
  const schema = JSON.parse(fs.readFileSync(new URL('../finding.schema.json', import.meta.url)));
  const validate = new Ajv2020({ allErrors: true }).compile(schema);
  assert.equal(validate({ id: 'QA-INCOMPLETE' }), false);
  const reportPath = path.resolve('docs/qa/initial-report.json');
  const examples = JSON.parse(fs.readFileSync(reportPath));
  const findings = [
    ...examples.findings,
    ...examples.confirmed_bugs,
    ...examples.usability_findings,
  ];
  assert.ok(findings.length > 0);
  for (const item of findings) assert.equal(validate(item), true, JSON.stringify(validate.errors));
  assert.equal(validate({ ...findings[0], severity: 'GREEN' }), false);
});
test('classification denies zero tests, nonzero child exit, skipped scenarios and unverified cleanup', () => {
  assert.equal(certificationStatus([], []), 'INCOMPLETE');
  const reports = Array.from({ length: 2 }, () => ({
    status: 'passed',
    process_exit_code: 0,
    tests: Array.from({ length: 4 }, () => ({ status: 'passed' })),
  }));
  const cleanup = Array.from({ length: 2 }, () => ({
    status: 'PASS',
    child_exit: 0,
    proof: { database_absent: true },
  }));
  assert.equal(certificationStatus(reports, cleanup), 'PASS_BOUNDED_SMOKE');
  assert.equal(
    certificationStatus([{ ...reports[0], process_exit_code: 1 }, reports[1]], cleanup),
    'INCOMPLETE',
  );
  assert.equal(certificationStatus(reports, cleanup.slice(0, 1)), 'INCOMPLETE');
  const skipped = JSON.parse(JSON.stringify(reports));
  skipped[0].tests[0].status = 'skipped';
  assert.equal(certificationStatus(skipped, cleanup), 'INCOMPLETE');
});
test('QA denies other origins, ports and protocol-relative external execution', () => {
  for (const url of [
    'https://api.amazon.com/orders',
    'http://127.0.0.1:8000/api/v1/products',
    'http://localhost:43219/catalog',
  ])
    assert.equal(allowRequest(url, 'GET', origin), false);
});
test('QA allows canonical synthetic onboarding and product preparation', () => {
  for (const url of [
    '/api/v1/auth/setup-owner',
    '/api/v1/brands',
    '/api/v1/products',
    '/api/v1/intelligence/business-agent/goals',
  ])
    assert.equal(allowRequest(origin + url, 'POST', origin), true);
});
test('QA denies execution even when same-origin or using provider lookalike paths', () => {
  for (const url of [
    '/api/v1/marketplaces/amazon/execute',
    '/api/v1/intelligence/business-agent/runs/123/start',
    '/api/v1/orders',
    '/api/v1/auth/setup-owner/execute',
    '/api/v1/providers/validate',
  ])
    assert.equal(allowRequest(origin + url, 'POST', origin), false);
});
test('QA report network references remove queries and fragments', () =>
  assert.equal(safeRoute(origin + '/api/v1/products?token=secret#secret'), '/api/v1/products'));
test('findings require schema fields, IDs and explicit evidence confidence', () => {
  assert.throws(() => finding('bad', {}), /INVALID_QA_FINDING/);
  const values = {
    feature: 'Catalog',
    route: '/catalog',
    type: 'USABILITY',
    severity: 'MINOR',
    priority: 'P2',
    expected: 'clear CTA',
    actual: 'ambiguous CTA',
    reproduction_steps: ['Open page'],
    evidence: [],
    confidence: 'RECOMMENDATION',
    suggested_fix: 'Review wording',
    retest_status: 'NOT_RETESTED',
  };
  assert.equal(finding('QA-UX-001', values).confidence, 'RECOMMENDATION');
  assert.throws(
    () => finding('QA-UX-001', { ...values, confidence: 'PASSED' }),
    /INVALID_QA_CONFIDENCE/,
  );
});

test('runtime inventory includes generated operations without inventing frontend coverage', () => {
  const registered = registeredOperations(
    { paths: { '/generated': { post: { operationId: 'generated_post' }, parameters: [] } } },
    [],
  );
  assert.equal(registered.length, 1);
  assert.equal(registered[0].method, 'POST');
  assert.deepEqual(registered[0].static_sources, []);
  assert.equal(registered[0].ui_coverage, 'NOT_INFERRED_FROM_REGISTRATION');
});

test('Markdown report retains failed classification, blocked scope and cleanup status', () => {
  const rendered = markdown({
    generated_at: '2026-10-24T19:30:00Z',
    status: 'INCOMPLETE',
    executive_summary: { passed: 0, failed: 0 },
    confirmed_bugs: [],
    findings: [],
    usability_findings: [],
    reports: [{ tests: [], blocker: 'QA_FIXTURE_START_FAILED' }],
    cleanup: [
      {
        project: 'desktop',
        database: 'vayujit_qa0123456789abcdef_test',
        status: 'BLOCKED',
        child_exit: 1,
      },
    ],
    coverage: {
      inventoried_routes: 1,
      api_declarations: 1,
      models: 1,
      existing_backend_test_files: 1,
      existing_angular_spec_files: 1,
      runtime_api_operations: [],
    },
    next_phase: 'P0 journeys',
  });
  assert.match(rendered, /\*\*INCOMPLETE\*\*/);
  assert.match(rendered, /QA_FIXTURE_START_FAILED/);
  assert.match(rendered, /verified absent=false/);
  assert.match(rendered, /25\/10\/2026/);
  assert.match(rendered, /No rules were disabled/);
});
test('reporter reports a failed assertion as suspected, never as confirmed defect or pass', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'vayujit-qa-report-'));
  const previous = process.env.QA_REPORT_PATH;
  process.env.QA_REPORT_PATH = path.join(dir, 'report.json');
  try {
    const reporter = new QaReporter();
    reporter.onTestEnd(
      { title: 'QA-TEST failure', parent: { project: () => ({ name: 'desktop' }) } },
      {
        status: 'failed',
        duration: 10,
        steps: [],
        errors: [{ message: 'Expected 200, got 500' }],
        attachments: [],
      },
    );
    reporter.onEnd({ status: 'failed' });
    const report = JSON.parse(fs.readFileSync(process.env.QA_REPORT_PATH));
    assert.equal(report.executive_summary.failed, 1);
    assert.equal(report.findings[0].confidence, 'SUSPECTED');
    assert.deepEqual(report.confirmed_bugs, []);
    assert.equal(report.executive_summary.complete_application_coverage, false);
  } finally {
    if (previous) process.env.QA_REPORT_PATH = previous;
    else delete process.env.QA_REPORT_PATH;
    // Exact files created by this test only; no recursive cleanup.
    fs.unlinkSync(path.join(dir, 'report.json'));
    fs.rmdirSync(dir);
  }
});
