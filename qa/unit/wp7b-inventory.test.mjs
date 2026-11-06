import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeRoute,observationKey,stableId} from '../wp7b-inventory.mjs';
test('WP7B normalizes owned IDs but retains route/component/rule/target/context distinctions',()=>{
 const o={route:'/catalog/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa?q=private',component:'catalog',rule:'color-contrast',target:'textarea',browser:'Chrome',viewport:'390',cause:'unknown'};
 assert.equal(normalizeRoute(o.route),'/catalog/:id');
 assert.equal(observationKey(o),observationKey({...o,route:'/catalog/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'}));
 for(const key of ['component','rule','target','browser','viewport','cause']) assert.notEqual(observationKey(o),observationKey({...o,[key]:'different'}));
 assert.equal(stableId(observationKey(o)),stableId(observationKey(o)));
});
