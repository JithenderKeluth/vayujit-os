import { test } from 'node:test';
import assert from 'node:assert/strict';
import { allowRequest } from '../safety.mjs';
import { wp3UnexpectedSignals } from '../wp3-reporting.mjs';

test('WP3 permits only local requirement/RFQ-draft/quote preparation, never dispatch', () => {
  const origin = 'http://127.0.0.1:4200';
  for (const path of ['requirements', 'rfqs', 'quotes'])
    assert.equal(
      allowRequest(`${origin}/api/v1/intelligence/sourcing/${path}`, 'POST', origin, '2'),
      true,
    );
  for (const path of [
    'rfqs/a/dispatch',
    'rfqs/a/approve',
    'decisions',
    'workers',
    'samples',
    'payments',
  ])
    assert.equal(
      allowRequest(`${origin}/api/v1/intelligence/sourcing/${path}`, 'POST', origin, '2'),
      false,
    );
  assert.equal(allowRequest('https://supplier.example', 'GET', origin, '2'), false);
});

const signals = () => ({
  console_errors: [],
  page_errors: [],
  failed_requests: [],
  denied_requests: [],
  network: [],
});
test('WP3 catches Angular console rendering errors even when pageerror is empty', () => {
  const result = wp3UnexpectedSignals({
    ...signals(),
    console_errors: ['ERROR TypeError: undefined length'],
  });
  assert.equal(result.console_errors.length, 1);
});
test('WP3 permits only the recorded synthetic outage, not arbitrary console or server errors', () => {
  const source = {
    ...signals(),
    expected_http_errors: [{ path: '/brief', status: 503 }],
    network: [{ path: '/brief', status: 503 }],
    console_errors: [
      'Failed to load resource: the server responded with a status of 503 (Service Unavailable)',
    ],
  };
  assert.equal(wp3UnexpectedSignals(source).console_errors.length, 0);
  source.console_errors.push('ERROR TypeError: real renderer failure');
  assert.equal(wp3UnexpectedSignals(source).console_errors.length, 1);
  source.network[0].path = '/another';
  assert.equal(wp3UnexpectedSignals(source).server_errors.length, 1);
  assert.equal(wp3UnexpectedSignals(source).console_errors.length, 2);
});
test('WP3 distinguishes an anonymous login session probe from protected-page authorization failures', () => {
  const source = {
    ...signals(),
    network: [{ screen: '/login', method: 'GET', path: '/api/v1/auth/me', status: 401 }],
    console_errors: [
      'Failed to load resource: the server responded with a status of 401 (Unauthorized)',
    ],
  };
  assert.equal(wp3UnexpectedSignals(source).console_errors.length, 0);
  source.network[0].screen = '/intelligence/sourcing-economics';
  assert.equal(wp3UnexpectedSignals(source).console_errors.length, 1);
  source.network[0].screen = '/login';
  source.network[0].path = '/api/v1/products';
  assert.equal(wp3UnexpectedSignals(source).console_errors.length, 1);
});
