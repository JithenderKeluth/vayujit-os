// Reuse canonical fixture mechanisms. No dispatch, publication, worker or provider calls.
export async function prepareReviews(run,s,f){
 const {api,brand}=f,product=f.ops.product,artifact=f.artifact;
 const data=await run.page.evaluate(()=>{const c=document.createElement('canvas');c.width=c.height=64;c.getContext('2d').fillRect(0,0,64,64);return c.toDataURL('image/png').split(',')[1];});
 const response=await run.page.request.post(s.origin+'/api/v1/media',{multipart:{file:{name:'wp7a4-synthetic.png',mimeType:'image/png',buffer:Buffer.from(data,'base64')}}});
 if(response.status()!==201)throw Error('R1_CANONICAL_MEDIA_FIXTURE_FAILED');const media=await response.json();
 const account=await api('post','social/accounts',{platform:'facebook',environment:'local',display_name:'[QA SYNTHETIC] R1 image review',remote_account_id:'qa-r1-social',credentials:{}});
 const social=await api('post','social/posts',{brand_id:brand.id,product_id:product.id,account_id:account.id,platform:'facebook',content_type:'facebook_post',content_artifact_id:artifact.id,content_artifact_version:artifact.version_number,media_ids:[media.id],caption:'[QA SYNTHETIC] R1 image review only',idempotency_key:'wp7a4-r1-social'});
 const flipAccount=await api('post','marketplaces/accounts',{marketplace:'flipkart',environment:'sandbox',display_name:'[QA SYNTHETIC] WP7A4 R1 Flipkart',seller_account_id:'qa3-r1-flipkart',credentials:{}});
 const flip=await api('post','marketplaces/flipkart/listings',{account_id:flipAccount.id,brand_id:brand.id,product_id:product.id,artifact_id:artifact.id,title:'[QA SYNTHETIC] QA7 R1 Flipkart',category:'Kids',marketplace_sku:'QA7-R1',idempotency_key:'wp7a7-r1-flipkart'});
 const campaign=await api('post','campaigns',{brand_id:brand.id,name:'[QA SYNTHETIC] WP7A3 WP7A4 R1',timezone_name:'Asia/Kolkata',local_start_at:'2026-11-10T09:00:00',local_end_at:'2026-11-15T18:00:00'});
 const activity=await api('post',`campaigns/${campaign.id}/activities`,{activity_type:'review_checkpoint',name:'[QA SYNTHETIC] WP7A4 R1 checkpoint',sequence:1,scheduled_local_date:'2026-11-11',scheduled_local_time:'09:00:00'});
 return{social,flip,campaign,activity,media};
}
