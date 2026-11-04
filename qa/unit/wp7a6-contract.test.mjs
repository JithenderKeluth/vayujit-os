import test from 'node:test';
import assert from 'node:assert/strict';
import { ids, assertions, gate, contexts } from '../wp7a6-contract.mjs';
import { wp7a6Path, safeWp7a6Payload } from '../wp7a6-safety.mjs';
test('exact seven stable IDs and four installed-browser contexts are mandatory', () => {
  assert.equal(ids.length, 7);
  assert.equal(new Set(ids).size, 7);
  assert.equal(contexts.length, 4);
  assert.equal(gate({ entries: [] }).status, 'INCOMPLETE');
  assert.equal(gate({ entries: ids.map((id) => ({ id, wp7a6_target: true })) }).exact_scope, false);
  assert.ok(ids.every((id) => assertions[id].length >= 7));
});
test('scope cannot close from scenario status or API-only evidence', () => {
  const entries = [
    ...Array.from({ length: 41 }, (_, i) => ({
      id: 'inherited-' + i,
      status: 'PASS',
      inherited_closed: true,
    })),
    ...ids.map((id) => ({
      id,
      wp7a6_target: true,
      status: 'PASS',
      acceptance_review: { complete: true },
      evidence_integrity: true,
      attempts: contexts.map((context) => ({
        context,
        status: 'PASS',
        screenshot: 'shot',
        trace: 'trace',
      })),
    })),
  ];
  const result = gate({ entries });
  assert.equal(result.exact_scope, true);
  assert.equal(result.closed, 41);
  assert.equal(result.remaining, 7);
});
test('new safety surface never admits external execution endpoints', () => {
  for (const action of ['submit', 'execute', 'publish', 'schedule', 'release', 'imports'])
    assert.equal(
      wp7a6Path('/api/v1/marketplaces/amazon/listings/' + 'a'.repeat(36) + '/' + action, 'POST'),
      false,
    );
  assert.equal(wp7a6Path('/api/v1/ads/campaigns/' + 'a'.repeat(36) + '/execute', 'POST'), false);
});
test('only the synthetic account sentinel can be supplied', () => {
  const data = {
    environment: 'local',
    display_name: '[QA SYNTHETIC] A6',
    seller_account_id: 'qa6-account',
    credentials: { token: 'QA-SYNTHETIC-NOT-A-REAL-CREDENTIAL' },
  };
  assert.equal(safeWp7a6Payload('/api/v1/marketplaces/amazon/accounts', data), true);
  assert.equal(
    safeWp7a6Payload('/api/v1/marketplaces/amazon/accounts', {
      ...data,
      environment: 'production',
    }),
    false,
  );
  assert.equal(
    safeWp7a6Payload('/api/v1/marketplaces/amazon/accounts', {
      ...data,
      credentials: { token: 'real' },
    }),
    false,
  );
});
test('unknown QA state controls and injected fields fail closed', () => {
  assert.equal(
    safeWp7a6Payload('/__qa/wp7a6/control', { scenario: 'DROP', id: 'a'.repeat(36) }),
    false,
  );
  assert.equal(
    safeWp7a6Payload('/__qa/wp7a6/control', {
      scenario: 'EXPIRE_AUTHORIZATION',
      id: 'a'.repeat(36),
      execute: true,
    }),
    false,
  );
});
test('DELETE is restricted to local dependency or fake-account credential removal', () => {
  const id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
  assert.equal(wp7a6Path(`/api/v1/marketplaces/amazon/accounts/${id}`, 'DELETE'), false);
  assert.equal(wp7a6Path(`/api/v1/ads/accounts/${id}/credentials`, 'DELETE'), true);
  assert.equal(wp7a6Path('/__qa/wp7a6/control', 'POST'), false);
});
test('authorization requires explicit confirmation, exact review, bounded expiry and scoped key', () => {
  const id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
  const path = `/api/v1/marketplaces/amazon/listings/${id}/execution-authorizations`;
  const data = {
    confirm: true,
    review_id: id,
    idempotency_key: 'amazon-ui-submit-' + id,
    expires_seconds: 600,
  };
  assert.equal(safeWp7a6Payload(path, data), true);
  for (const override of [
    { confirm: false },
    { expires_seconds: 30 },
    { expires_seconds: 3601 },
    { review_id: null },
    { idempotency_key: 'unscoped' },
  ])
    assert.equal(safeWp7a6Payload(path, { ...data, ...override }), false);
  assert.equal(safeWp7a6Payload(path + '/' + id + '/revoke', { confirm: true }), true);
  assert.equal(safeWp7a6Payload(path + '/' + id + '/revoke', {}), false);
});
test('complete browser assertions cannot override failed cleanup or a blocking defect', () => {
  const entries = [
    ...Array.from({ length: 41 }, (_, i) => ({
      id: 'old-' + i,
      status: 'PASS',
      inherited_closed: true,
    })),
    ...ids.map((id) => ({
      id,
      wp7a6_target: true,
      status: 'PASS',
      acceptance_review: { complete: true },
      evidence_integrity: true,
      attempts: contexts.map((context) => ({
        context,
        status: 'PASS',
        screenshot: 'shot',
        trace: 'trace',
        acceptance_assertions: assertions[id],
        persisted_state_verified: true,
      })),
    })),
  ];
  const quality = {
    checks: [
      'node_qa',
      'python_qa',
      'angular',
      'build',
      'lint',
      'typescript_app',
      'typescript_spec',
      'mypy',
      'ruff',
      'black_backend',
      'black_qa',
      'compile',
      'parser',
      'diff',
    ].map((id) => ({ id, status: 'PASS' })),
  };
  const backend = { complete: true, tests: 1, failures: 0, errors: 0, skipped: 0 };
  const audit = {
    database_absence_status: 'PASS',
    historical_baseline_unchanged: true,
    databases: [{ absent: true, state: 'DROPPED' }],
  };
  assert.equal(gate({ entries, quality, backend, audit }).status, 'PASS');
  assert.equal(gate({ entries, quality, backend, audit, blockers: ['P1'] }).status, 'INCOMPLETE');
  assert.equal(
    gate({ entries, quality, backend, audit: { ...audit, database_absence_status: 'FAIL' } })
      .status,
    'INCOMPLETE',
  );
  entries[41].attempts[3].acceptance_assertions = [];
  assert.equal(gate({ entries, quality, backend, audit }).closed, 47);
});
