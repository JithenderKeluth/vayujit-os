import { test } from 'node:test';
import assert from 'node:assert/strict';
import { allowRequest } from '../safety.mjs';
import { openingStockComplete, stockIds, stockStates } from '../phase4b-status.mjs';

function complete() {
  return {
    reports: ['desktop', 'mobile'].map((project) => ({
      status: 'passed',
      process_exit_code: 0,
      tests: stockIds.map((id, index) => ({
        id,
        project,
        status: 'passed',
        axe:
          index === 0
            ? stockStates.map((state) => ({ state: 'axe-' + state, violations: [], passes: 20 }))
            : [],
      })),
    })),
    cleanup: ['desktop', 'mobile'].map((project, i) => {
      const database = `vayujit_qa${String(i + 1).repeat(16)}_test`;
      return {
        project,
        database,
        status: 'PASS',
        child_exit: 0,
        proof: { database, marker_verified: true, database_absent: true },
      };
    }),
  };
}
test('Opening-stock certification requires unique scenarios, axe states and independent normal cleanup', () => {
  assert.equal(openingStockComplete(complete()), true);
  for (const change of [
    (r) => {
      r.reports[0].tests[0].status = 'skipped';
    },
    (r) => {
      r.reports[0].tests[0].id = r.reports[0].tests[1].id;
    },
    (r) => {
      r.reports[0].tests[0].axe.pop();
    },
    (r) => {
      r.reports[0].tests[0].axe[0].violations.push({ id: 'label' });
    },
    (r) => {
      r.reports[0].process_exit_code = 1;
    },
    (r) => {
      r.cleanup[0].child_exit = 1;
    },
    (r) => {
      r.cleanup[1] = r.cleanup[0];
    },
  ]) {
    const r = complete();
    change(r);
    assert.equal(openingStockComplete(r), false);
  }
});

test('Opening stock QA allows only bounded local canonical preparation', () => {
  const origin = 'http://127.0.0.1:43123';
  const id = '00000000-0000-0000-0000-000000000001';
  for (const route of [
    '/api/v1/auth/setup-owner',
    '/api/v1/auth/login',
    '/api/v1/inventory/items',
    `/api/v1/catalog/products/${id}/variants`,
    `/api/v1/products/${id}/archive`,
  ])
    assert.equal(allowRequest(origin + route, 'POST', origin, '4B'), true);
  for (const route of [
    '/api/v1/marketplaces/accounts',
    '/api/v1/orders/fake/events',
    '/api/v1/financial/events',
    '/__qa/restart',
    '/api/v1/marketplaces/amazon/execute',
    '/api/v1/intelligence/suppliers/research',
    `/api/v1/inventory/${id}/reserve`,
    `/api/v1/inventory/${id}/adjust`,
  ])
    assert.equal(allowRequest(origin + route, 'POST', origin, '4B'), false);
  assert.equal(allowRequest('https://example.com', 'GET', origin, '4B'), false);
  assert.equal(allowRequest(origin + '/api/v1/inventory/items', 'DELETE', origin, '4B'), false);
});
