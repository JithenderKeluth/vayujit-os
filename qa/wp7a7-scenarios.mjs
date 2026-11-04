// Every assertion key is earned by an actual assertion. Missing work stays PARTIAL.
import crypto from 'node:crypto';
import { execute as previous } from './wp7a6-scenarios.mjs';
import { assertions as required } from './wp7a6-contract.mjs';

export async function execute(entry, h) {
  const { p, s, api, expect, run, product, brand, content, waitResponse } = h;
  const proved = new Set();
  let persisted = false;
  const mark = (...keys) => keys.forEach(k => proved.add(k));
  const state = async () => {
    const response = await p.request.get(s.origin + '/__qa/wp7a4/state', {headers:{'x-qa-token':s.token}});
    expect(response.status()).toBe(200);
    const snapshot = await response.json();
    expect(snapshot.token).toBe(s.token);
    persisted = true;
    return snapshot;
  };
  const isolation = async endpoint => {
    const anonymous = await p.context().browser().newContext();
    try { expect((await anonymous.request.get(s.origin+'/api/v1/'+endpoint)).status()).toBe(401); }
    finally { await anonymous.close(); }
    const invalid = endpoint.replace(/[a-f0-9-]{36}/, crypto.randomUUID());
    expect([404,422]).toContain((await p.request.get(s.origin+'/api/v1/'+invalid)).status());
  };
  const finish = reason => {
    const missing = required[entry.id].filter(k => !proved.has(k));
    return {status:missing.length ? 'PARTIAL':'PASS', reason:missing.length ? reason+' Missing: '+missing.join(', ') : reason,
      acceptance_assertions:[...proved], persisted_state_verified:persisted,
      remaining_assertions:missing};
  };
  if (entry.id === 'R-3feda36d') {
    const earlier = await previous(entry,h);
    earlier.acceptance_assertions.forEach(k => proved.add(k));
    const posts = await api('get','social/posts');
    const post = posts.find(v => v.product_id === product.id && !v.video_output_id);
    expect(post).toBeTruthy();
    const endpoint = 'social/posts/'+post.id;
    const payload = {brand_id:post.brand_id,product_id:post.product_id,account_id:post.account_id,
      platform:post.platform,content_type:post.content_type,content_artifact_id:post.content_artifact_id,
      content_artifact_version:post.content_artifact_version,media_ids:post.media_ids,
      caption:post.caption,idempotency_key:post.idempotency_key};
    const duplicates = await Promise.all([api('post','social/posts',payload),api('post','social/posts',payload)]);
    expect(new Set(duplicates.map(v=>v.id))).toEqual(new Set([post.id]));
    expect((await api('get','social/posts')).filter(v=>v.idempotency_key===post.idempotency_key)).toHaveLength(1);
    mark('duplicate_concurrent');
    await p.getByLabel('Draft caption',{exact:true}).fill('[QA SYNTHETIC] recovery caption');
    let interrupted = false;
    const failSave = async route => {
      if(route.request().method()==='PATCH' && !interrupted) {
        interrupted = true; await route.abort('failed');
      } else await route.fallback();
    };
    await p.route('**/api/v1/'+endpoint, failSave);
    await p.getByRole('button',{name:'Save draft caption',exact:true}).click();
    await expect(p.getByRole('alert')).toContainText('Draft update rejected');
    await p.unroute('**/api/v1/'+endpoint, failSave);
    expect((await api('get',endpoint)).caption).toBe(post.caption);
    await h.capture(run,entry.id+'-save-failure',true);
    const saved = waitResponse(p,'/'+endpoint,'PATCH');
    await p.getByRole('button',{name:'Save draft caption',exact:true}).click();
    expect((await saved).status()).toBe(200);
    mark('failure_recovery');
    await p.getByRole('button',{name:'Preview image draft',exact:true}).click();
    await expect(p.locator('.preview')).toContainText('Ready for review');
    expect((await h.axe(run,entry.id+'-exact-image-review')).violations).toHaveLength(0);
    const approval = p.getByRole('button',{name:'Approve image draft — do not publish',exact:true});
    await expect(approval).toBeDisabled();
    await p.getByRole('checkbox',{name:'I reviewed this exact image, caption, content version and destination account.'}).check();
    const approvedResponse = waitResponse(p,'/'+endpoint+'/approve');
    await approval.click();
    expect((await approvedResponse).status()).toBe(200);
    await p.reload();
    await expect(p.locator('main')).toContainText('approved');
    const approved = await api('get',endpoint);
    expect(approved.lifecycle_status).toBe('approved');
    expect(approved.schedule_id).toBeNull();
    expect(approved.remote_publication_id).toBeNull();
    expect(approved.media_ids).toEqual(post.media_ids);
    expect(approved.content_artifact_id).toBe(post.content_artifact_id);
    const persistedPost = (await state()).social_posts.find(v=>v.id===post.id);
    expect(persistedPost.lifecycle_status).toBe('approved');
    expect(persistedPost.schedule_id).toBeNull();
    mark('approval_no_publish');
    await isolation(endpoint); mark('owner_isolation');
    return finish('Image-only exact HUMAN approval, replay, interrupted save recovery and persisted no-publication verified. Inherited Video evidence remains separate.');
  }
  if (entry.id === 'R-55e822d5') {
    const accounts=[];
    for(const channel of ['amazon','flipkart','meesho']) {
      accounts.push(await api('post','marketplaces/accounts',{marketplace:channel,environment:'sandbox',
        display_name:'[QA SYNTHETIC] WP7A7 '+channel+' '+run.label,
        seller_account_id:'qa3-wp7a-'+channel+'-'+run.label,credentials:{}}));
    }
    await p.goto(s.origin+'/marketplaces/overview');
    await expect(p).toHaveURL(/\/marketplaces$/);
    await expect(p.getByRole('heading',{name:'Marketplace overview',exact:true})).toBeVisible();
    mark('configured_not_connected');
    await p.getByRole('link',{name:/^Accounts Connected accounts/}).click();
    for (const account of accounts) {
      const row=p.getByRole('row').filter({hasText:account.display_name});
      await expect(row).toContainText(/missing|AUTHORIZATION_REQUIRED/);
    }
    mark('missing_credentials');
    for (const account of accounts.filter(v=>v.marketplace!=='meesho')) {
      for(const scenario of ['INVALID','EXPIRED','REVOKED']) {
        const response=await p.request.post(s.origin+'/__qa/wp7a/control',{headers:{'x-qa-token':s.token},data:{scenario,account_id:account.id}});
        expect(response.status()).toBe(200);
        await p.reload();
        const row=p.getByRole('row').filter({hasText:account.display_name});
        await expect(row).toContainText(scenario==='INVALID'?'DEGRADED':scenario==='EXPIRED'?'EXPIRED':'AUTHORIZATION_REQUIRED');
        const connectivity=await api('get',`marketplaces/accounts/${account.id}/connectivity`);
        expect(connectivity.external_writes).toBe(false);
        expect(connectivity.provider_contract).toBe('UNVERIFIED');
        expect(connectivity.transport_mode || connectivity.transport).not.toBe('LIVE');
      }
    }
    mark('invalid_expired_revoked','default_deny');
    const account=accounts[0];
    await api('post','marketplaces/amazon/accounts/'+account.id+'/credentials',{credentials:{token:'QA-SYNTHETIC-NOT-A-REAL-CREDENTIAL'}});
    await api('post','marketplaces/amazon/accounts/'+account.id+'/validate',{});
    await api('post','marketplaces/amazon/accounts/'+account.id+'/enable',{confirm:true});
    await p.reload();
    const row=p.getByRole('row').filter({hasText:account.display_name});
    await expect(row).toContainText('UNVERIFIED'); await expect(row).toContainText('SYNTHETIC');
    mark('fake_validated_label','reload_recovery');
    expect((await p.request.get(s.origin+'/api/v1/marketplaces/accounts/'+crypto.randomUUID()+'/connectivity')).status()).toBe(404);
    expect((await p.request.get(s.origin+'/api/v1/marketplaces/accounts/'+accounts[2].id+'/connectivity')).status()).toBe(422);
    mark('account_mismatch'); await state();
    return finish('Overview, linked exact account states, recovery, unsupported Meesho connectivity and default-deny verified. No real connectivity certified.');
  }
  if (['R-551d2f8c','R-db243c36','R-d6a495d5'].includes(entry.id)) {
    const channel={'R-551d2f8c':'flipkart','R-db243c36':'meesho','R-d6a495d5':'amazon'}[entry.id];
    const artifact=await content();
    const account=await api('post',`marketplaces/${channel}/accounts`,{display_name:'[QA SYNTHETIC] QA7 '+channel+' '+run.label,
      seller_account_id:'qa6-'+channel+'-'+run.label,environment:'sandbox',credentials:{token:'QA-SYNTHETIC-NOT-A-REAL-CREDENTIAL'}});
    await api('post',`marketplaces/${channel}/accounts/${account.id}/validate`,{});
    await api('post',`marketplaces/${channel}/accounts/${account.id}/enable`,{confirm:true});
    const body={account_id:account.id,brand_id:brand.id,product_id:product.id,artifact_id:artifact.id,
      title:'[QA SYNTHETIC] QA7 '+channel,marketplace_sku:'QA7-'+run.label+'-'+channel,category:channel==='amazon'?'HOME':'home'};
    let draft;
    if(channel==='amazon') {
      await p.goto(s.origin+'/marketplaces/amazon');
      await p.getByLabel('Brand',{exact:true}).selectOption(brand.id);
      await p.getByLabel('Product',{exact:true}).selectOption(product.id);
      await p.getByLabel('Approved content',{exact:true}).selectOption(artifact.id);
      await p.getByLabel('Draft title',{exact:true}).fill(body.title);
      await p.getByLabel('Draft seller SKU',{exact:true}).fill(body.marketplace_sku);
      await p.getByLabel('Draft category',{exact:true}).fill(body.category);
      const created=waitResponse(p,'/marketplaces/listings');
      await p.getByRole('button',{name:'Prepare local Amazon draft',exact:true}).click();
      const response=await created; expect(response.status()).toBe(201); draft=await response.json();
    } else draft=await api('post',`marketplaces/${channel}/listings`,body);
    expect(draft.remote_listing_id).toBeNull(); expect(draft.status).toBe('draft');
    const endpoint=`marketplaces/${channel}/listings/${draft.id}`;
    await p.goto(s.origin+`/marketplaces/listings/${draft.id}/${channel}`);
    await p.reload();
    const readiness=await api('get',endpoint+'/readiness'); expect(readiness.ready).toBe(false);
    mark(channel==='meesho'?'missing_readiness':'missing_prerequisite');
    await h.capture(run,entry.id+'-missing-prerequisites',true);
    // Actual supported local writers, not fabricated ready flags or remote IDs.
    if(channel==='amazon') {
      await p.getByRole('button',{name:'Add variant',exact:true}).click();
      await p.locator('#variant-sku-0').fill(body.marketplace_sku);
      await p.locator('#variant-theme-0').fill('Size');
      await p.locator('#variant-price-0').fill('100.25');
      const variants=waitResponse(p,'/'+endpoint+'/variants','PUT');
      await p.getByRole('button',{name:'Save variants',exact:true}).click(); expect((await variants).status()).toBe(200);
      await p.locator('#amazon-list-price').fill('150');
      await p.locator('#amazon-selling-price').fill('100.25');
      const price=waitResponse(p,'/'+endpoint+'/pricing','PUT');
      await p.getByRole('button',{name:/Confirm price|Update price|Save price/}).click(); expect((await price).status()).toBe(200);
    } else {
      // Existing channel preparation APIs populate the real inputs; the price
      // correction is subsequently exercised from the actual editor below.
      await api('put',endpoint+'/variants',{variants:[{stable_variant_key:'default',sku:body.marketplace_sku,options:{Size:'M'},price:'100.25',currency:'INR'}],idempotency_key:'wp7a7-variants-'+draft.id});
    }
    const image=await h.once('wp7a7-large-image',async()=>{
      const request=await api('post','ai/images/generate',{brand_id:brand.id,product_id:product.id,
        operation:'generate_product_image',channel:'canonical',width:1024,height:1024,output_count:1,
        provider:'deterministic_mock_v1',idempotency_key:'wp7a4-image-'+run.label+'-large'});
      await h.worker();
      const output=(await api('get','ai/images/generations/'+request.generation_id)).outputs[0];
      await p.goto(s.origin+'/ai/images/assets/'+output.id);
      const approved=waitResponse(p,'/outputs/'+output.id+'/approve');
      await p.getByRole('button',{name:'Approve exact output',exact:true}).click();
      expect((await approved).status()).toBe(200);
      return api('get','ai/images/outputs/'+output.id);
    });
    await p.goto(s.origin+`/marketplaces/listings/${draft.id}/${channel}`);
    if(channel==='amazon') {
      await p.getByLabel('Approved image Output ID',{exact:true}).fill(image.id);
      await p.getByRole('button',{name:'Preview local main image',exact:true}).click();
      await expect(p.locator('main')).toContainText('Ready for local image review');
      const mapping=waitResponse(p,'/outputs/'+image.id+'/handoff');
      await p.getByRole('button',{name:'Confirm exact local main image',exact:true}).click();
      expect((await mapping).status()).toBe(200);
    } else {
      await api('put',endpoint+'/media',{media:[{media_id:image.media_id,position:0,alt_text:'[QA SYNTHETIC] exact main image'}],idempotency_key:'wp7a7-media-'+draft.id});
      await p.locator('[aria-label="Listing editor sections"]').getByText('Pricing',{exact:true}).click();
      await p.getByLabel('MRP/list price',{exact:true}).fill('150');
      await p.getByLabel('Selling price',{exact:true}).fill('100.25');
      const price=waitResponse(p,'/'+endpoint+'/pricing','PUT');
      await p.getByRole('button',{name:'Review and confirm price',exact:true}).click();
      expect((await price).status()).toBe(200);
    }
    expect((await api('get',endpoint+'/readiness')).ready).toBe(true);
    const snapshot=await state();
    const row=snapshot.marketplace_listings.find(v=>v.id===draft.id);
    expect(row.product_id).toBe(product.id); expect(row.account_id).toBe(account.id);
    expect(snapshot.marketplace_prices.filter(v=>v.listing_id===draft.id)).toHaveLength(1);
    mark(channel==='meesho'?'manual_resolution':'legitimate_resolution');
    await isolation(endpoint+'/readiness'); mark('owner_isolation');
    if(channel==='meesho') {
      await p.locator('[aria-label="Listing editor sections"]').getByText('Readiness',{exact:true}).click();
      const preview=waitResponse(p,'/'+endpoint+'/preview');
      await p.getByRole('button',{name:'Refresh readiness',exact:true}).click(); expect((await preview).status()).toBe(200);
      await expect(p.locator('main')).toContainText('Live Meesho validation is not performed.');
      expect((await api('get',endpoint+'/readiness')).live_validation).toBe('NOT LIVE-VALIDATED');
      mark('unsupported_live_truthful');
      expect((await p.request.post(s.origin+'/api/v1/'+endpoint+'/review',{data:{confirm:true}})).status()).toBe(404);
      expect((await api('get','marketplaces/listings/'+draft.id)).remote_listing_id).toBeNull();
      mark('review_boundaries','no_dispatch');
      const repeat={selling_price:'100.25',list_price:'150',currency:'INR',confirm:true,idempotency_key:'wp7a7-price-'+draft.id};
      await api('put',endpoint+'/pricing',repeat); await api('put',endpoint+'/pricing',repeat);
      expect((await state()).marketplace_prices.filter(v=>v.listing_id===draft.id)).toHaveLength(1);
      const invalid=await p.request.put(s.origin+'/api/v1/'+endpoint+'/pricing',{data:{...repeat,selling_price:'200'}});
      expect(invalid.status()).toBe(422); mark('stale_duplicate');
      await p.reload(); await expect(p.locator('main')).toContainText(body.title);
      mark('reload_failure_recovery');
    } else {
      if(channel==='flipkart') await p.locator('[aria-label="Listing editor sections"]').getByText('Readiness',{exact:true}).click();
      expect((await api('get',endpoint+'/execution-authorizations/latest')).status).toBe('authorization_required');
      const missingReview=await p.request.post(s.origin+'/api/v1/'+endpoint+'/execution-authorizations',{data:{confirm:true,review_id:crypto.randomUUID(),idempotency_key:'wp7a6-no-review-'+draft.id,expires_seconds:600}});
      expect(missingReview.status()).toBe(409);
      const reviewResponse=waitResponse(p,'/'+endpoint+'/review');
      await p.getByRole('button',{name:channel==='amazon'?'Approve listing for controlled submission':'Review exact listing',exact:true}).click();
      const reviewRaw=await reviewResponse; expect(reviewRaw.status()).toBe(200); const review=await reviewRaw.json();
      expect(review.artifact_id).toBe(artifact.id); expect(review.artifact_version).toBe(artifact.version_number);
      expect(review.listing_id).toBe(draft.id); expect(review.account_id).toBe(account.id);
      mark('human_review','exact_fingerprint');
      const authResponse=waitResponse(p,'/'+endpoint+'/execution-authorizations');
      await p.getByRole('button',{name:channel==='amazon'?'Issue one-time execution authorization':'Authorize local execution',exact:true}).click();
      const authRaw=await authResponse; expect(authRaw.status()).toBe(201); const auth=await authRaw.json();
      expect(auth.review_id).toBe(review.id); expect(auth.payload_fingerprint).toBe(review.payload_fingerprint);
      const authBody={confirm:true,review_id:review.id,idempotency_key:auth.idempotency_key,expires_seconds:600};
      const replays=await Promise.all([api('post',endpoint+'/execution-authorizations',authBody),api('post',endpoint+'/execution-authorizations',authBody)]);
      expect(new Set(replays.map(v=>v.id))).toEqual(new Set([auth.id])); mark('repeat_concurrent');
      const revoke=waitResponse(p,'/'+endpoint+'/execution-authorizations/'+auth.id+'/revoke');
      await p.getByRole('button',{name:'Revoke authorization',exact:true}).click(); expect((await revoke).status()).toBe(200);
      await p.reload();
      if(channel==='flipkart') await p.locator('[aria-label="Listing editor sections"]').getByText('Readiness',{exact:true}).click();
      await expect(p.locator('main')).toContainText('revoked');
      if(channel==='flipkart') await p.locator('[aria-label="Listing editor sections"]').getByText('Readiness',{exact:true}).click();
      const renewResponse=waitResponse(p,'/'+endpoint+'/execution-authorizations');
      await p.getByRole('button',{name:channel==='amazon'?'Issue one-time execution authorization':'Authorize local execution',exact:true}).click();
      const renewed=await renewResponse; expect(renewed.status()).toBe(201); const expiring=await renewed.json();
      expect(expiring.id).not.toBe(auth.id); expect(expiring.status).toBe('issued');
      const clock=await p.request.post(s.origin+'/__qa/wp7a7/expire-authorization',{headers:{'x-qa-token':s.token},data:{channel,authorization_id:expiring.id}});
      expect(clock.status()).toBe(200);
      await p.reload();
      if(channel==='flipkart') await p.locator('[aria-label="Listing editor sections"]').getByText('Readiness',{exact:true}).click();
      await expect(p.locator('main')).toContainText('expired');
      const savedPrice=await api('get','marketplaces/listings/'+draft.id+'/pricing');
      expect(Number(savedPrice.selling_price)).toBe(100.25);
      expect((await api('get',endpoint+'/execution-authorizations/latest')).status).toBe('expired'); mark('authorization_states');
      await api('patch','marketplaces/listings/'+draft.id,{title:body.title+' changed',idempotency_key:'wp7a7-stale-'+draft.id});
      const stale=await p.request.post(s.origin+'/api/v1/'+endpoint+'/execution-authorizations',{data:{...authBody,idempotency_key:'wp7a6-stale-'+draft.id}});
      expect(stale.status()).toBe(409); mark('stale_mismatch');
      await p.reload(); await expect(p.locator('main')).not.toContainText('undefined');
      mark('reload_failure_recovery');
      expect((await api('get','marketplaces/listings/'+draft.id)).remote_listing_id).toBeNull();
      const saved=await state();
      const table=channel==='amazon'?'amazon_listing_execution_authorizations':'marketplace_listing_execution_authorizations';
      expect(saved[table].filter(v=>v.listing_id===draft.id).every(v=>!v.consumed_at)).toBe(true); mark('no_submission');
    }
    return finish(channel+': persisted unpublished preparation, exact review boundaries, negative states and no external submission checked.');
  }
  if(entry.id==='L-16') {
    const campaign=await api('post','campaigns',{brand_id:brand.id,name:'[QA SYNTHETIC] WP7A3 WP7A4 QA7 '+run.label,
      timezone_name:'Asia/Kolkata',local_start_at:'2026-11-01T09:00:00',local_end_at:'2026-11-15T18:00:00'}), artifact=await content();
    const destination=await api('post','publishing/destinations',{name:'[QA SYNTHETIC] WP7A7 metadata '+run.label,connector_key:'mock_publisher_v1',configuration:{channel_name:'QA-WP7A7-LOCAL'}});
    const activity=await api('post',`campaigns/${campaign.id}/activities`,{activity_type:'mock_publish',name:'[QA SYNTHETIC] QA7 versioned',sequence:3,
      product_id:product.id,artifact_id:artifact.id,destination_id:destination.id,scheduled_local_date:'2026-11-02',scheduled_local_time:'09:00:00'});
    const checkpoint=await api('post',`campaigns/${campaign.id}/activities`,{activity_type:'review_checkpoint',name:'[QA SYNTHETIC] QA7 predecessor',sequence:2,scheduled_local_date:'2026-11-01',scheduled_local_time:'10:00:00'});
    const activities=()=>api('get',`campaigns/${campaign.id}/activities`);
    expect((await activities()).find(v=>v.id===activity.id).artifact_version).toBe(artifact.version_number);
    // This fixture uses the legacy product-content contract. Generate its next
    // immutable version through that same authority, not Studio's typed schema.
    const regenerated=await api('post','ai/generations',{product_id:product.id,prompt_template_id:artifact.template_id,
      provider_key:'deterministic_mock_v1',additional_instructions:'[QA SYNTHETIC] WP7A4 '+run.label+' revised'});
    const replacement=await api('get','ai/artifacts/'+regenerated.artifact_id);
    expect(replacement.version_number).toBeGreaterThan(artifact.version_number);
    expect(replacement.status).toBe('pending_review');
    expect((await activities()).find(v=>v.id===activity.id).artifact_id).toBe(artifact.id);
    await p.goto(s.origin+'/ai/artifacts/'+replacement.id);
    await p.getByRole('button',{name:'Approve',exact:true}).click();
    await expect(p.locator('main')).toContainText('approved');
    const handoff='ai/studio/artifacts/'+replacement.id+'/campaign-handoff';
    const handoffBody={activity_id:activity.id,expected_artifact_version:replacement.version_number,expected_current_artifact_version:artifact.version_number,confirm:false};
    const preview=await api('post',handoff,handoffBody);
    expect(preview.status).toBe('confirmation_required');
    expect((await activities()).find(v=>v.id===activity.id).artifact_id).toBe(artifact.id);
    const stale=await p.request.post(s.origin+'/api/v1/'+handoff,{data:{...handoffBody,confirm:true,expected_current_artifact_version:999999}});
    expect(stale.status()).toBe(409);
    const confirmed=await api('post',handoff,{...handoffBody,confirm:true});
    expect(confirmed.artifact_id).toBe(replacement.id);
    const concurrent=await Promise.all([api('post',handoff,{...handoffBody,confirm:true}),api('post',handoff,{...handoffBody,confirm:true})]);
    expect(concurrent.every(v=>v.idempotent_reuse===true)).toBe(true);
    mark('draft_identity','artifact_versions','concurrent_replay');
    const interrupted=await p.request.post(s.origin+'/__qa/wp7a7/interrupted-activity',{
      headers:{'x-qa-token':s.token},data:{activity_id:activity.id}});
    expect(interrupted.status()).toBe(200);
    expect((await interrupted.json()).worker_executed).toBe(false);
    const current=(await activities()).find(v=>v.id===activity.id);
    const reschedule={activity_id:activity.id,expected_activity_row_version:current.row_version,
      proposed_local_datetime:'2026-11-14T09:00:00',proposed_timezone:'Asia/Kolkata',reason:'[QA SYNTHETIC] exact dependency review'};
    const first=await api('post',`campaigns/${campaign.id}/recovery/reschedule-activity/preview`,reschedule);
    expect(first.preview_fingerprint).toMatch(/^[a-f0-9]{64}$/);
    await p.goto(s.origin+`/campaigns/${campaign.id}/dependencies`);
    await p.locator('select[name=predecessor]').selectOption(checkpoint.id);
    await p.locator('select[name=successor]').selectOption(activity.id);
    const edgeResponse=waitResponse(p,`/campaigns/${campaign.id}/dependencies`);
    await p.getByRole('button',{name:'Add dependency',exact:true}).click(); expect((await edgeResponse).status()).toBe(201);
    await p.reload(); await expect(p.locator('main')).toContainText('QA7 predecessor');
    const edges=await api('get',`campaigns/${campaign.id}/dependencies`);
    expect(edges.some(v=>v.predecessor_activity_id===checkpoint.id && v.successor_activity_id===activity.id)).toBe(true);
    for(const pair of [[activity.id,checkpoint.id],[activity.id,activity.id]]) {
      const response=await p.request.post(s.origin+`/api/v1/campaigns/${campaign.id}/dependencies`,{data:{predecessor_activity_id:pair[0],successor_activity_id:pair[1],dependency_type:'success_required'}});
      expect([409,422]).toContain(response.status());
    }
    mark('dependency_graph');
    await h.capture(run,entry.id+'-dependency-review',true);
    const second=await api('post',`campaigns/${campaign.id}/recovery/reschedule-activity/preview`,reschedule);
    expect(second.preview_fingerprint,'Dependency changes must invalidate the reviewed impact').not.toBe(first.preview_fingerprint);
    mark('changed_preview_stale');
    const staleAction=await p.request.post(s.origin+'/api/v1/campaigns/recovery/actions',{
      data:{...reschedule,action:'reschedule_activity',campaign_id:campaign.id,confirm:true,preview_fingerprint:first.preview_fingerprint}});
    expect(staleAction.status()).toBe(409);
    expect((await activities()).find(v=>v.id===activity.id).schedule_id).toBeNull();
    await p.goto(s.origin+'/campaigns/'+campaign.id);
    await p.locator('article.card').filter({hasText:activity.name}).getByRole('button',{name:'Reschedule Activity',exact:true}).click();
    const panel=p.locator('app-reschedule-dialog');
    await panel.getByLabel('Local date',{exact:true}).fill('2026-11-14');
    await panel.getByLabel('Local time',{exact:true}).fill('09:00');
    await panel.getByLabel('IANA timezone',{exact:true}).fill('Asia/Kolkata');
    await panel.getByLabel('Reason',{exact:true}).fill(reschedule.reason);
    const previewResponse=waitResponse(p,`/campaigns/${campaign.id}/recovery/reschedule-activity/preview`);
    await panel.getByRole('button',{name:'Preview change',exact:true}).click();
    const reviewed=await previewResponse; expect(reviewed.status()).toBe(200);
    const finalPreview=await reviewed.json();
    expect((await h.axe(run,entry.id+'-reschedule-review')).violations).toHaveLength(0);
    const confirmedResponse=waitResponse(p,'/campaigns/recovery/actions');
    await panel.getByRole('button',{name:'Confirm reschedule',exact:true}).click();
    expect((await confirmedResponse).status()).toBe(200);
    await expect(panel).toContainText('Reschedule confirmed');
    const replay=await api('post','campaigns/recovery/actions',{...reschedule,action:'reschedule_activity',campaign_id:campaign.id,confirm:true,preview_fingerprint:finalPreview.preview_fingerprint});
    expect(replay.result.outcome).toBe('reused');
    expect(replay.result.idempotent_reuse).toBe(true);
    mark('fingerprint_confirmation','interrupted_recovery');
    const after=await state();
    expect(after.campaigns.find(v=>v.id===campaign.id).status).toBe('draft');
    expect(after.campaign_activities.find(v=>v.id===activity.id).artifact_id).toBe(replacement.id);
    expect(after.campaign_activity_dependencies.filter(v=>v.campaign_id===campaign.id).every(v=>v.released_at===null)).toBe(true);
    mark('no_release');
    await p.goto(s.origin+'/campaigns/'+campaign.id); await p.reload();
    await expect(p.locator('main')).toContainText(campaign.name); mark('reload_owned');
    return finish('Campaign immutable version replacement, explicit review and dependency changes tested without release.');
  }
  if(entry.id==='L-17') {
    const account=await h.adAccount(), artifact=await content();
    await p.goto(s.origin+'/ads/create');
    await p.locator('select[name=account_id]').selectOption(account.id);
    await p.getByLabel('Campaign name',{exact:true}).fill('[QA SYNTHETIC] WP7A2 QA7 '+run.label);
    await p.getByRole('button',{name:'Next',exact:true}).click();
    await p.getByLabel('Product',{exact:true}).selectOption(product.id);
    await p.getByRole('button',{name:'Next',exact:true}).click();
    await p.locator('select[name=creative_type]').selectOption('content');
    await p.getByLabel('Approved creative',{exact:true}).selectOption(artifact.id);
    await p.getByLabel('Exact Artifact version',{exact:true}).fill(String(artifact.version_number));
    await p.getByLabel('Destination URL',{exact:true}).fill('https://example.invalid/qa7');
    const readiness=waitResponse(p,'/ads/creatives/readiness');
    await p.getByRole('button',{name:'Check server readiness',exact:true}).click();
    expect((await readiness).status(),'Selected prospective creative must be reviewable through the supported UI').toBe(200);
    const prospective={campaign_id:'00000000-0000-0000-0000-000000000000',account_id:account.id,product_id:product.id,
      creative_type:'content',artifact_id:artifact.id,artifact_version:artifact.version_number,destination_url:'https://example.invalid/qa7',idempotency_key:'wp7a7-prospective'};
    const bad=await api('post','ads/creatives/readiness',{...prospective,artifact_version:999999});
    expect(bad.ready).toBe(false);
    expect(bad.approval_granted).toBe(false); mark('missing_invalid_prerequisites');
    await api('post','ads/accounts/'+account.id+'/disable',{});
    const disabled=await p.request.post(s.origin+'/api/v1/ads/creatives/readiness',{data:prospective});
    expect(disabled.status()).toBe(422);
    await api('post','ads/accounts/'+account.id+'/enable',{});
    const missingAccount=await p.request.post(s.origin+'/api/v1/ads/creatives/readiness',{data:{...prospective,account_id:crypto.randomUUID()}});
    expect(missingAccount.status()).toBe(404);
    await api('delete','ads/accounts/'+account.id+'/credentials',{});
    const missingCredentials=await p.request.post(s.origin+'/api/v1/ads/creatives/readiness',{data:prospective});
    expect(missingCredentials.status()).toBe(422);
    await api('patch','ads/accounts/'+account.id,{credentials:{token:'QA-SYNTHETIC-NOT-A-REAL-CREDENTIAL'}});
    await api('post','ads/accounts/'+account.id+'/validate',{});
    await api('post','ads/accounts/'+account.id+'/enable',{}); mark('authorization_states');
    const image=await h.once('wp7a7-ads-image',async()=>{
      const output=await h.image();
      await p.goto(s.origin+'/ai/images/assets/'+output.id);
      const approved=waitResponse(p,'/outputs/'+output.id+'/approve');
      await p.getByRole('button',{name:'Approve exact output',exact:true}).click();
      expect((await approved).status()).toBe(200);
      return api('get','ai/images/outputs/'+output.id);
    });
    const imageReady=await api('post','ads/creatives/readiness',{...prospective,creative_type:'image',artifact_id:null,artifact_version:null,
      image_output_id:image.id,image_media_id:image.media_id,image_version:1});
    expect(imageReady.ready).toBe(true);
    expect(imageReady.exact_creative.image_output_id).toBe(image.id);
    expect(imageReady.exact_creative.image_media_id).toBe(image.media_id);
    // Reopen the actual wizard after reviewing the immutable Image Output.
    await p.goto(s.origin+'/ads/create');
    await p.locator('select[name=account_id]').selectOption(account.id);
    await p.getByLabel('Campaign name',{exact:true}).fill('[QA SYNTHETIC] WP7A2 QA7 '+run.label);
    await p.getByRole('button',{name:'Next',exact:true}).click();
    await p.getByLabel('Product',{exact:true}).selectOption(product.id);
    await p.getByRole('button',{name:'Next',exact:true}).click();
    await p.locator('select[name=creative_type]').selectOption('image');
    await p.getByLabel('Approved Image Output ID',{exact:true}).fill(image.id);
    await p.getByLabel('Exact media version',{exact:true}).fill('1');
    await p.locator('fieldset.media-selector label').filter({hasText:'(64x64)'}).getByRole('checkbox').check();
    const imageUiResponse=waitResponse(p,'/ads/creatives/readiness');
    await p.getByRole('button',{name:'Check server readiness',exact:true}).click();
    const imageUi=await imageUiResponse; expect(imageUi.status()).toBe(200);
    const imageUiReady=await imageUi.json(); expect(imageUiReady.ready).toBe(true);
    expect(imageUiReady.exact_creative.image_media_id).toBe(image.media_id);
    await h.capture(run,entry.id+'-immutable-image-readiness',true); mark('creative_content_image');
    expect((await h.axe(run,entry.id+'-creative-readiness')).violations).toHaveLength(0);
    await p.locator('select[name=creative_type]').selectOption('content');
    await p.getByLabel('Approved creative',{exact:true}).selectOption(artifact.id);
    await p.getByLabel('Exact Artifact version',{exact:true}).fill(String(artifact.version_number));
    await p.getByLabel('Destination URL',{exact:true}).fill('https://example.invalid/qa7');
    await p.getByRole('button',{name:'Next',exact:true}).click();
    await p.getByLabel('Amount',{exact:true}).fill('100');
    await p.getByRole('button',{name:'Next',exact:true}).click();
    const previewResponse=waitResponse(p,'/ads/campaigns/preview');
    await p.getByRole('button',{name:'Run server preview',exact:true}).click();
    const previewRaw=await previewResponse; expect(previewRaw.status()).toBe(200);
    const preview=await previewRaw.json(), payload=previewRaw.request().postDataJSON();
    expect(payload.creative.artifact_id).toBe(artifact.id);
    expect(payload.creative.artifact_version).toBe(artifact.version_number);
    expect(preview.fingerprint).toMatch(/^[a-f0-9]{64}$/); mark('exact_versions','preview_fingerprint');
    const stale=await p.request.post(s.origin+'/api/v1/ads/campaigns/confirm',{data:{campaign:{...payload,creative:{...payload.creative,headline:'changed after review'}},
      confirm:true,preview_fingerprint:preview.fingerprint,idempotency_key:'wp7a7-stale-'+run.label}});
    expect(stale.status()).toBe(409);
    for(let n=0;n<7;n++) await p.getByRole('button',{name:'Next',exact:true}).click();
    const submit=p.getByRole('button',{name:'Confirm and queue campaign',exact:true});
    await expect(submit).toBeDisabled();
    const checkbox=p.locator('input[name=confirm_checked]'); await checkbox.focus(); await p.keyboard.press('Space');
    await expect(submit).toBeEnabled();
    const confirmResponse=waitResponse(p,'/ads/campaigns/confirm');
    await submit.click();
    const confirmRaw=await confirmResponse; expect(confirmRaw.status()).toBe(200);
    const confirmation=confirmRaw.request().postDataJSON(), result=await confirmRaw.json();
    const replays=await Promise.all([api('post','ads/campaigns/confirm',confirmation),api('post','ads/campaigns/confirm',confirmation)]);
    expect(new Set(replays.map(v=>v.campaign.id))).toEqual(new Set([result.campaign.id]));
    expect(new Set(replays.map(v=>v.job.id))).toEqual(new Set([result.job.id]));
    mark('human_confirm','stale_concurrent');
    await expect(p).toHaveURL(new RegExp('/ads/campaigns/'+result.campaign.id+'$'));
    await expect(p.locator('main')).toContainText(artifact.id);
    await p.reload();
    const detail=await api('get','ads/campaigns/'+result.campaign.id);
    expect(detail.creatives[0].lineage.artifact_id).toBe(artifact.id);
    expect(detail.creatives[0].lineage.artifact_version).toBe(artifact.version_number); mark('reload_owned');
    const failure=await p.request.post(s.origin+'/__qa/wp7a2/control',{headers:{'x-qa-token':s.token},data:{scenario:'ADS_FAILURE',id:result.campaign.id}});
    expect(failure.status()).toBe(200);
    await p.goto(s.origin+'/ads/recovery');
    const row=p.getByRole('row').filter({hasText:'ads.connector_unavailable'}).filter({has:p.getByRole('button',{name:'retry',exact:true})});
    await expect(row).toContainText('Observed');
    const recovered=waitResponse(p,'/ads/recovery');
    await row.getByRole('button',{name:'retry',exact:true}).click(); expect((await recovered).status()).toBe(200);
    mark('failure_recovery_latest');
    const saved=await state();
    expect(saved.ad_campaigns.filter(v=>v.id===result.campaign.id)).toHaveLength(1);
    expect(saved.ad_campaigns.filter(v=>v.id===result.campaign.id).every(v=>!v.remote_campaign_id)).toBe(true);
    expect(saved.ad_jobs.every(v=>!v.remote_checkpoint_json || Object.keys(v.remote_checkpoint_json).length===0)).toBe(true);
    mark('no_spend');
    return finish('Ads exact creative preparation exercised; no real authorization expiry or spend certified.');
  }
  // Fail visibly rather than treating route visits or owner-approved scope as closure.
  await previous(entry,h);
  return finish('Exact remaining workflow scenario implementation not yet complete.');
}
