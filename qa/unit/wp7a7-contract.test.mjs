import test from 'node:test';
import assert from 'node:assert/strict';
import {ids,assertions,contexts,gate} from '../wp7a7-contract.mjs';
test('A7 keeps exact seven IDs, original assertion inventory and four contexts',()=>{
 assert.equal(ids.length,7); assert.equal(contexts.length,4);
 assert.ok(ids.every(id=>assertions[id].length>=7));
 assert.equal(gate({entries:[],ads_clarification:{approved:true}}).status,'INCOMPLETE');
});
test('owner scope approval does not supply missing Ads or other browser evidence',()=>{
 const entries=[...Array.from({length:41},(_,n)=>({id:'prior-'+n,inherited_closed:true,status:'PASS'})),
  ...ids.map(id=>({id,wp7a7_target:true,status:'PASS',acceptance_review:{complete:true},evidence_integrity:true,
   attempts:contexts.map(context=>({context,status:'PASS',screenshot:'shot',trace:'trace',persisted_state_verified:true,acceptance_assertions:[]}))}))];
 const result=gate({entries,ads_clarification:{approved:true}});
 assert.equal(result.exact_scope,true); assert.equal(result.closed,41); assert.equal(result.remaining,7);
 assert.equal(result.live_provider_expiry,'UNVERIFIED');
});
test('unapproved Ads scope cannot be silently treated as complete',()=>{
 const result=gate({entries:[]}); assert.ok(result.blockers.some(b=>b.includes('L-17')));
});
