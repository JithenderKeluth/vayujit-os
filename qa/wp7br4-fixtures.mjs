// Reuse canonical synthetic API/domain mechanisms; no remote acquisition or workers.
import {wp3Owner,wp3Product,wp3Economics} from './wp3-fixtures.mjs';
import {wp5Operations} from './wp5-fixtures.mjs';
import {prepareReviews} from './wp7br1-review-fixtures.mjs';
import {prepareReadOnlyRecommendation} from './wp7b-domain-fixture.mjs';
export async function fixtures(run,s){
 const p=run.page;
 const response=await p.request.post(s.origin+'/api/v1/auth/setup-owner',{data:{full_name:'[QA SYNTHETIC] R4 Owner',email:wp3Owner.email,password:wp3Owner.password,password_confirmation:wp3Owner.password}});
 if(response.status()!==201)throw Error('R4_OWNER_PREPARATION_FAILED');
 await p.goto(s.origin+'/intelligence/business-agent');
 const f=await wp3Product(p,s.origin),{api,brand,op,assessment}=f;
 await api('post','brands/'+brand.id+'/activate',{});f.ops=await wp5Operations(api,brand);
 await api('post',`intelligence/product-opportunities/${op.id}/assessments/${assessment.id}/decision`,{action:'shortlist',rationale:'[QA SYNTHETIC] R4 owner fixture review only; not real evidence or procurement approval',idempotency_key:'wp7b-r4-local-selection'});
 const discovery=await api('post','intelligence/suppliers/research',{product_opportunity_id:op.id,product_query:op.product_concept,category:op.category,mode:'LOCAL_FIXTURE',max_candidates:3,idempotency_key:'wp7b-r4-local-supplier'});
 if((discovery.result||discovery).external_calls!==false)throw Error('R4_NO_EXTERNAL_CALL_PROOF_REQUIRED');
 f.economics=await wp3Economics(api,op,assessment);
 const generation=await api('post','ai/generations',{product_id:f.ops.product.id,provider_key:'deterministic_mock_v1',additional_instructions:'[QA SYNTHETIC] WP7A4 R4 accessibility fixture'});
 f.artifact=await api('get','ai/artifacts/'+generation.artifact_id);await api('post','ai/artifacts/'+f.artifact.id+'/approve',{});
 const account=await api('post','marketplaces/accounts',{marketplace:'meesho',environment:'sandbox',display_name:'[QA SYNTHETIC] WP7A4 R4',seller_account_id:'qa3-r4-meesho',credentials:{}});
 f.meesho=await api('post','marketplaces/meesho/listings',{account_id:account.id,brand_id:brand.id,product_id:f.ops.product.id,artifact_id:f.artifact.id,title:'[QA SYNTHETIC] QA7 R4',category:'Kids',marketplace_sku:'QA7-R4',idempotency_key:'wp7b-r4-meesho'});
 const adAccount=await api('post','ads/accounts',{provider:'meta',environment:'local',display_name:'[QA SYNTHETIC] WP7A2 R4',external_account_id:'qa-wp7a2-r4',credentials:{token:'QA-SYNTHETIC-NOT-A-REAL-CREDENTIAL'}});
 await api('post',`ads/accounts/${adAccount.id}/validate`,{});await api('post',`ads/accounts/${adAccount.id}/enable`,{});
 const campaign={provider:'meta',account_id:adAccount.id,product_id:f.ops.product.id,name:'[QA SYNTHETIC] WP7A2 WP7B R4',objective:'awareness',budget:{daily_amount:'100',currency:'INR'},idempotency_key:'wp7b-r4-ad'};
 const preview=await api('post','ads/campaigns/preview',campaign);
 f.adCampaign=(await api('post','ads/campaigns/confirm',{campaign,preview_fingerprint:preview.fingerprint,confirm:true,idempotency_key:'wp7b-r4-ad-confirm'})).campaign;
 f.recommendation=prepareReadOnlyRecommendation(s.token,f.adCampaign.id);f.reviews=await prepareReviews(run,s,f);
 // Existing exact-token QA fixture creates a recorded synthetic missed *intent*.
 // It requires canonical approved artifact + local mock destination, no job/schedule,
 // and writes its synthetic audit event. No claimed worker execution or fake approval.
 try{
  const campaign=await api('post','campaigns',{brand_id:brand.id,name:'[QA SYNTHETIC] WP7A3 WP7A4 QA7 R4 reschedule',timezone_name:'Asia/Kolkata',local_start_at:'2026-11-01T09:00:00',local_end_at:'2026-11-15T18:00:00'});
  const destination=await api('post','publishing/destinations',{name:'[QA SYNTHETIC] WP7A7 R4 local metadata',connector_key:'mock_publisher_v1',configuration:{channel_name:'QA-R4-LOCAL-NO-PUBLISH'}});
  const activity=await api('post',`campaigns/${campaign.id}/activities`,{activity_type:'mock_publish',name:'[QA SYNTHETIC] QA7 R4 missed local intent',sequence:1,product_id:f.ops.product.id,artifact_id:f.artifact.id,destination_id:destination.id,scheduled_local_date:'2026-11-02',scheduled_local_time:'09:00:00'});
  const changed=await p.request.post(s.origin+'/__qa/wp7a7/interrupted-activity',{headers:{'x-qa-token':s.token},data:{activity_id:activity.id}});
  if(changed.status()!==200||!(await changed.json()).synthetic)throw Error('R4_ELIGIBLE_FIXTURE_NOT_ESTABLISHED');
  f.reschedule={campaign_id:campaign.id,activity_id:activity.id,provenance:'Existing guarded synthetic interruption fixture; worker_executed false; no raw row injection'};
 }catch{f.reschedule={status:'NOT_VERIFIED',safe_code:'R4_ELIGIBLE_CAMPAIGN_PREPARATION_INCOMPLETE'};}
 return f;
}
