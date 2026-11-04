import test from 'node:test';
import assert from 'node:assert/strict';
import {
  routePlan,
  classifyCoverage,
  runApprovedAction,
  surfaceId,
  canonicalRoute,
} from '../phase4-surface.mjs';
import { phase4Status, expectedPhase4Ids } from '../phase4-report.mjs';
import { allowRequest } from '../safety.mjs';

const routes = [
  { route: '/products/:id', kind: 'PAGE' },
  { route: '/campaigns/:id/video/:activityId', kind: 'PAGE' },
  { route: '/settings', kind: 'PAGE' },
  { route: '/login', kind: 'PAGE' },
  { route: '/**', kind: 'REDIRECT' },
];
test('Phase 4 never invents populated identifiers or counts redirects as pages', () => {
  const plan = routePlan(routes, { phase2: { product_id: 'canonical-fixture-id' } });
  assert.equal(plan[0].target, '/products/canonical-fixture-id');
  assert.equal(plan[1].target, null);
  assert.equal(plan[1].disposition, 'REQUIRES_UNAVAILABLE_CANONICAL_CONTEXT');
  assert.equal(plan[3].disposition, 'GUEST_FLOW_SEPARATE_SCENARIO');
  assert.equal(plan[4].disposition, 'REDIRECT_NOT_PAGE');
});
test('Phase 4 coverage labels visits separately from feature execution and blocked context', () => {
  const coverage = classifyCoverage(routePlan(routes), [
    {
      declaration: '/settings',
      route: '/settings',
      route_match: true,
      controls: [],
      project: 'desktop',
    },
  ]);
  assert.equal(coverage[2].status, 'VISITED_NOT_FULLY_TESTED');
  assert.equal(coverage[0].status, 'REQUIRES_UNAVAILABLE_CANONICAL_CONTEXT');
  assert.equal(surfaceId('route/control'), surfaceId('route/control'));
  assert.notEqual(surfaceId('route/control'), surfaceId('route/other'));
});
test('Phase 4 finding identity normalizes disposable UUIDs without conflating routes', () => {
  assert.equal(
    canonicalRoute('/products/11111111-1111-1111-1111-111111111111'),
    canonicalRoute('/products/22222222-2222-2222-2222-222222222222'),
  );
  assert.notEqual(
    canonicalRoute('/products/11111111-1111-1111-1111-111111111111'),
    canonicalRoute('/brands/11111111-1111-1111-1111-111111111111'),
  );
});
test('Phase 4 action registry rejects unknown verbs and wrong routes before clicking', async () => {
  let clicked = false;
  const page = {
    url: () => 'http://127.0.0.1/products',
    getByRole: () => ({
      click: async () => {
        clicked = true;
      },
    }),
  };
  await assert.rejects(runApprovedAction(page, 'publish'), /QA_UNAPPROVED_INTERACTION/);
  await assert.rejects(runApprovedAction(page, 'product.save'), /QA_UNAPPROVED_INTERACTION/);
  assert.equal(clicked, false);
});
test('Phase 4 keeps real execution and worker/backup mutations default-denied', () => {
  const origin = 'http://127.0.0.1:49123';
  for (const p of [
    '/api/v1/amazon/execute',
    '/api/v1/marketplaces/accounts/abc/validate',
    '/api/v1/publishing/jobs/execute',
    '/api/v1/operations/backups/restore',
    '/__qa/restart',
  ])
    assert.equal(allowRequest(origin + p, 'POST', origin, '4'), false, p);
  assert.equal(allowRequest('https://example.com/api/v1/products', 'POST', origin, '4'), false);
  assert.equal(allowRequest(origin + '/api/v1/products/abcd', 'PATCH', origin, '4'), true);
});
const passing = () => {
  const ids = expectedPhase4Ids(routes);
  return {
    reports: ['desktop', 'mobile'].map(() => ({
      status: 'passed',
      process_exit_code: 0,
      tests: ids.map((id) => ({ id, status: 'passed' })),
      api_results: {
        process_exit_code: 0,
        tests: Array.from({ length: 18 }, () => ({ status: 'PASS' })),
        passed: 18,
        failed: 0,
        errors: 0,
        skipped: 0,
      },
    })),
    cleanup: ['desktop', 'mobile'].map((project, index) => ({
      project,
      database: 'vayujit_qa' + String(index).repeat(16) + '_test',
      status: 'PASS',
      child_exit: 0,
      proof: {
        database_absent: true,
        marker_verified: true,
        database: 'vayujit_qa' + String(index).repeat(16) + '_test',
      },
    })),
  };
};
test('Phase 4 classification requires expected unique IDs, prior API assertions and normal cleanup', () => {
  assert.equal(phase4Status(passing(), routes), 'PASS_BOUNDED_EXPLORATION');
  let r = passing();
  r.reports[0].tests[0].id = r.reports[0].tests[1].id;
  assert.equal(phase4Status(r, routes), 'INCOMPLETE');
  r = passing();
  r.reports[0].api_results.skipped = 1;
  assert.equal(phase4Status(r, routes), 'INCOMPLETE');
  r = passing();
  r.cleanup[0].child_exit = 'TIMEOUT';
  assert.equal(phase4Status(r, routes), 'INCOMPLETE');
  r = passing();
  r.reports[0].tests[0].status = 'skipped';
  assert.equal(phase4Status(r, routes), 'INCOMPLETE');
  r = passing();
  r.cleanup[1] = { ...r.cleanup[0], project: 'mobile' };
  assert.equal(phase4Status(r, routes), 'INCOMPLETE');
});
