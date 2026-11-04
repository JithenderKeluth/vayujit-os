import test from 'node:test';
import assert from 'node:assert/strict';
import {wp7a7Path,safeWp7a7Payload} from '../wp7a7-safety.mjs';
const id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
test('A7 preparation never admits remote channel writes',()=>{
 for(const channel of ['amazon','flipkart','meesho']) for(const action of ['submit','execute','dispatch','schedule','publish','pricing'])
  assert.equal(wp7a7Path(`/api/v1/marketplaces/${channel}/listings/${id}/${action}`,'POST'),false);
 assert.equal(wp7a7Path(`/api/v1/marketplaces/amazon/listings/${id}/pricing`,'PUT'),true);
 assert.equal(wp7a7Path(`/api/v1/marketplaces/amazon/listings/${id}/media`,'PUT'),false);
});
test('A7 clock fixture has exact synthetic metadata payload and no Ads expiry fiction',()=>{
 const path='/__qa/wp7a7/expire-authorization';
 assert.equal(wp7a7Path(path,'POST'),true);
 assert.equal(safeWp7a7Payload(path,{channel:'amazon',authorization_id:id}),true);
 for(const body of [{channel:'ads',authorization_id:id},{channel:'amazon',authorization_id:id,execute:true},{channel:'amazon',authorization_id:'bad'}]) assert.equal(safeWp7a7Payload(path,body),false);
});
test('A7 does not accept credentials or arbitrary listing creation payloads',()=>{
 assert.equal(safeWp7a7Payload('/api/v1/marketplaces/flipkart/listings',{title:'real',credentials:{token:'real'}}),false);
 assert.equal(safeWp7a7Payload('/api/v1/marketplaces/flipkart/listings',{title:'[QA SYNTHETIC] draft',product_id:id,brand_id:id,artifact_id:id,account_id:id}),true);
 const path='/__qa/wp7a7/interrupted-activity';
 assert.equal(safeWp7a7Payload(path,{activity_id:id}),true);
 assert.equal(safeWp7a7Payload(path,{activity_id:id,status:'succeeded'}),false);
 assert.equal(safeWp7a7Payload('/api/v1/campaigns/recovery/actions',{action:'release',confirm:true}),false);
 assert.equal(wp7a7Path(`/api/v1/campaigns/${id}/release`,'POST'),false);
});
