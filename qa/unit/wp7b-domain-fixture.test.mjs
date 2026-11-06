import test from 'node:test';
import assert from 'node:assert/strict';
import {prepareReadOnlyRecommendation} from '../wp7b-domain-fixture.mjs';
test('WP7B domain fixture refuses malformed database token and resource identity before process launch',()=>{
 for(const [token,id]of [['bad','aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'],['0123456789abcdef','-'.repeat(36)],['vayujit','aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa']])
  assert.throws(()=>prepareReadOnlyRecommendation(token,id),/EXACT_QA_IDENTITY_REQUIRED/);
});
