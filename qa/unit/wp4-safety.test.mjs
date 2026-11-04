import test from 'node:test';
import assert from 'node:assert/strict';
import { allowRequest, wp4PreparationRequest } from '../safety.mjs';
const id = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
test('WP4 permits only exact local preparation methods and routes', () => {
  for (const [method, p] of [
    ['POST', 'media'],
    ['POST', 'inventory/items'],
    ['POST', `catalog/products/${id}/variants`],
    ['POST', `catalog/products/${id}/images`],
    ['POST', `catalog/products/${id}/listing-drafts`],
    ['PATCH', `catalog/variants/${id}`],
    ['PATCH', `catalog/images/${id}`],
    ['DELETE', `catalog/images/${id}`],
    ['PATCH', `catalog/listing-drafts/${id}`],
    ['POST', `catalog/listing-drafts/${id}/review`],
    ['POST', 'intelligence/sourcing-economics/quotes'],
  ])
    assert.equal(wp4PreparationRequest('/api/v1/' + p, method), true, p);
});
test('WP4 does not allow provider execution or broaden another phase', () => {
  const o = 'http://127.0.0.1:12345';
  for (const p of [
    'marketplaces/amazon/listings/' + id + '/submit',
    'marketplaces/accounts/' + id + '/authorize',
    'marketplaces/flipkart/listings/' + id + '/execute',
    'media/' + id + '/archive',
    'inventory/' + id + '/adjust',
    'catalog/listing-drafts/' + id + '/publish',
  ])
    assert.equal(wp4PreparationRequest('/api/v1/' + p, 'POST'), false, p);
  assert.equal(allowRequest(o + '/api/v1/media', 'POST', o, '2'), false);
  assert.equal(allowRequest('https://example.com/api/v1/media', 'POST', o, '4'), false);
  assert.equal(wp4PreparationRequest('/api/v1/media', 'DELETE'), false);
});
