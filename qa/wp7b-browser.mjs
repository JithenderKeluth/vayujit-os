// Guided keyboard-only actions; API setup is explicitly separate fixture preparation.
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium,expect} from '@playwright/test';
import {start,capture,axe,finish} from './seller-browser-explore.mjs';
import {wp3Owner,wp3Product,wp3Economics} from './wp3-fixtures.mjs';
import {wp5Operations} from './wp5-fixtures.mjs';
import {prepareReadOnlyRecommendation} from './wp7b-domain-fixture.mjs';
import {sourceFingerprint} from './wp7a7-source.mjs';
import {prepareReviews} from './wp7br1-review-fixtures.mjs';
import {measureTargets} from './wp7br1-contrast.mjs';
import {nativeReview} from './wp7br1-native.mjs';
const s=JSON.parse(await fs.readFile(process.argv[2],'utf8'));
const r1=process.env.QA_ASSESSMENT_PACKAGE==='WP7BR1';
const packageKey=r1?'wp7br1':'wp7b';
const approval=JSON.parse(await fs.readFile('tmp/qa-'+packageKey+'/owner-authorization.json','utf8'));
if(!approval.task_specific_database_approval || s.qa_phase!=='WP7A7' || !s.synthetic) throw Error('WP7B_APPROVAL_AND_REUSED_FIXTURE_CONTRACT_REQUIRED');
const witness=await fetch(s.origin+'/__qa/witness').then(r=>r.json());
if(!witness.disposable || witness.token!==s.token) throw Error('EXACT_QA_WITNESS_REQUIRED');
const report={package:r1?'WP7B-R1':'WP7B',token:s.token,fixture_contract:'WP7A7 (reused, not WP7A recertification)',synthetic:true,checks:[],scans:[],keyboard:[],versions:{},fixture_errors:[],screen_reader:'NOT VERIFIED: actual spoken output not captured',external_calls:false,goal_diagnostics:[],contrast:[]};
const runs=[],browsers=[];
const testedSource=await sourceFingerprint();
await fs.writeFile(path.join(s.folder,packageKey+'-tested-source-sha256.json'),JSON.stringify(testedSource,null,2));
let f;
const save=()=>fs.writeFile(path.join(s.folder,packageKey+'-browser.json'),JSON.stringify(report,null,2));
async function seek(run,target,limit=180) {
 const p=run.page;
 await expect(target).toBeVisible();
 for(let n=0;n<=limit;n++) {
  if(await target.evaluate(e=>e===document.activeElement)) {
   const focus=await target.evaluate(e=>({tag:e.tagName,role:e.getAttribute('role'),outline:getComputedStyle(e).outlineStyle,width:getComputedStyle(e).outlineWidth,rect:{width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}}));
   report.keyboard.push({context:run.label,route:new URL(p.url()).pathname,tab_count:n,...focus});
   return;
  }
  await p.keyboard.press('Tab');
 }
 throw Error('KEYBOARD_TARGET_NOT_REACHED');
}
async function type(run,target,value){await seek(run,target);await run.page.keyboard.press('ControlOrMeta+A');await run.page.keyboard.type(value);}
async function activate(run,target,key='Enter'){await seek(run,target);await run.page.keyboard.press(key);}
async function login(run) {
 const p=run.page, setup=await p.request.get(s.origin+'/api/v1/auth/setup-status').then(r=>r.json());
 await p.goto(s.origin+(setup.ownerExists?'/login?returnUrl=%2Fcatalog':'/setup'));
 if(!setup.ownerExists) await type(run,p.locator('#full-name'),'[QA SYNTHETIC] WP7B Owner');
 await type(run,p.locator('#email'),wp3Owner.email);
 await type(run,p.locator('#password'),wp3Owner.password);
 if(!setup.ownerExists) await type(run,p.locator('#confirmation'),wp3Owner.password);
 await activate(run,p.getByRole('button',{name:setup.ownerExists?'Sign in':'Create owner',exact:true}));
 await expect(p).not.toHaveURL(/\/(login|setup)(?:\?|$)/);
}
async function check(run,id,fn){
 if(process.env.WP7B_CASE_IDS && !process.env.WP7B_CASE_IDS.split(',').includes(id))return;
 let status='PASS',reason='Bounded keyboard/visual assertions passed';
 const before=run.signals.network.length;
 try{await fn();}catch(e){status='FAIL';reason=e.message.split('\n')[0].slice(0,180);}
 let shot;
 try{shot=await capture(run,id+'-'+status,true);const scan=await axe(run,id);report.scans.push({context:run.label,id,...scan});if(scan.violations.length){status='FAIL';reason='AXE_VIOLATIONS';}}catch{status='FAIL';reason='EVIDENCE_CAPTURE_FAILED';}
 if(run.signals.network.slice(before).some(n=>n.status>=500)){status='FAIL';reason='UNEXPECTED_API_5XX';}
 report.checks.push({context:run.label,id,status,reason,...(status==='FAIL' && run.assertionStage?{failure_operation:run.assertionStage}:{}),route:new URL(run.page.url()).pathname,screenshot:shot?.screenshot,trace:path.join(run.directory,'trace.zip')});run.assertionStage=null;await save();
}
async function setup(run){
 const p=run.page;
 f=await wp3Product(p,s.origin);const {api,brand,op,assessment}=f;
 await api('post','brands/'+brand.id+'/activate',{});
 f.ops=await wp5Operations(api,brand);
 await api('post',`intelligence/product-opportunities/${op.id}/assessments/${assessment.id}/decision`,{
   action:'shortlist',rationale:'[QA SYNTHETIC] WP7B owner reviewed fixture identity; no procurement or live evidence approval.',idempotency_key:'wp7b-fixture-product-review'});
 const discovery=await api('post','intelligence/suppliers/research',{product_opportunity_id:op.id,product_query:op.product_concept,category:op.category,
   mode:'LOCAL_FIXTURE',max_candidates:3,idempotency_key:'wp7b-local-supplier-fixture'});
 expect((discovery.result || discovery).external_calls).toBe(false);
 const suppliers=await api('get','intelligence/suppliers/research-results?opportunity_id='+op.id);
 f.supplier=suppliers.suppliers[0];
 f.economics=await wp3Economics(api,op,assessment);
 const generation=await api('post','ai/generations',{product_id:f.ops.product.id,provider_key:'deterministic_mock_v1',additional_instructions:'[QA SYNTHETIC] WP7A4 WP7B accessibility fixture'});
 f.artifact=await api('get','ai/artifacts/'+generation.artifact_id);
 // Explicit owned approval through the existing domain API, setup not keyboard proof.
 await api('post','ai/artifacts/'+f.artifact.id+'/approve',{});
 const account=await api('post','marketplaces/accounts',{marketplace:'meesho',environment:'sandbox',display_name:'[QA SYNTHETIC] WP7A4 WP7B Meesho',seller_account_id:'qa3-wp7b-meesho',credentials:{}});
 f.meesho=await api('post','marketplaces/meesho/listings',{account_id:account.id,brand_id:brand.id,product_id:f.ops.product.id,artifact_id:f.artifact.id,title:'[QA SYNTHETIC] QA7 WP7B Meesho',category:'Kids',marketplace_sku:'QA7-WP7B',idempotency_key:'wp7b-meesho'});
 f.adAccount=await api('post','ads/accounts',{provider:'meta',environment:'local',display_name:'[QA SYNTHETIC] WP7A2 WP7B',external_account_id:'qa-wp7a2-wp7b',credentials:{token:'QA-SYNTHETIC-NOT-A-REAL-CREDENTIAL'}});
 await api('post','ads/accounts/'+f.adAccount.id+'/validate',{});await api('post','ads/accounts/'+f.adAccount.id+'/enable',{});
 const campaign={provider:'meta',account_id:f.adAccount.id,product_id:f.ops.product.id,name:'[QA SYNTHETIC] WP7A2 WP7B',objective:'awareness',budget:{daily_amount:'100',currency:'INR'},idempotency_key:'wp7b-campaign'};
 const preview=await api('post','ads/campaigns/preview',campaign);
 f.adCampaign=(await api('post','ads/campaigns/confirm',{campaign,preview_fingerprint:preview.fingerprint,confirm:true,idempotency_key:'wp7b-campaign-confirm'})).campaign;
 f.recommendation=prepareReadOnlyRecommendation(s.token,f.adCampaign.id);
 report.fixture_ids={opportunity:op.id,goal:f.goal.id,product:f.ops.product.id,artifact:f.artifact.id,meesho:f.meesho.id,recommendation:f.recommendation.id};await save();
 if(r1 && process.env.WP7BR1_REVIEWS==='1'){try{f.reviews=await prepareReviews(run,s,f);report.review_fixture_ids={social:f.reviews.social.id,flip:f.reviews.flip.id,campaign:f.reviews.campaign.id,activity:f.reviews.activity.id};}catch(e){report.review_fixture_failure={status:'BLOCKED',safe_code:e.message.split('\n')[0].slice(0,120)};}await save();}
}
async function routeReview(run,id,url,target) {
 await check(run,id,async()=>{const p=run.page;await p.goto(s.origin+url);await expect(p.locator('main')).toBeVisible();
  const control=target?target(p):p.locator('main button:enabled,main a[href],main input:enabled,main select:enabled,main [tabindex="0"]').filter({visible:true}).first();
  await seek(run,control);await p.keyboard.press('Tab');await p.keyboard.press('Shift+Tab');await expect(control).toBeFocused();
  expect(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 });
}
try {
 for(const channel of process.env.WP7B_BASELINE==='1'?['chrome']:['chrome','msedge']) {
  const browser=await chromium.launch({channel,headless:process.env.WP7B_HEADED!=='1',...(r1?{args:['--window-position=0,0','--window-size=1280,900']}: {})});browsers.push(browser);report.versions[channel]=browser.version();
  for(const width of process.env.WP7B_BASELINE==='1'?[1440]:[1440,390]) {
   const run=await start(browser,s,{width,height:900},packageKey+'-'+channel+'-'+width);runs.push(run);run.page.setDefaultTimeout(10000);
   const p=run.page;
   if(r1){await p.addInitScript(()=>{globalThis.__r1GoalEvents=[];document.addEventListener('toggle',e=>{if(e.target instanceof HTMLDetailsElement && e.target.classList.contains('goal-creation'))globalThis.__r1GoalEvents.push({time:performance.now(),open:e.target.open,active:document.activeElement?.tagName});},true);});}
   await check(run,'B-LOGIN',()=>login(run));
   if(!f) {try{await setup(run);}catch(e){report.fixture_errors.push({code:e.message.split('\n')[0].slice(0,160)});await save();throw e;}}
   if(r1 && process.env.WP7BR1_MANUAL==='1' && channel==='chrome' && width===1440){report.manual_native=await nativeReview(browser,s,f,run.context,runs);await save();}
   await check(run,'B-NAV',async()=>{
    await p.goto(s.origin+'/dashboard');
    if(width===390){const menu=p.getByText('Application menu',{exact:true});await activate(run,menu);await expect(p.getByRole('link',{name:'Dashboard',exact:true})).toBeVisible();await p.keyboard.press('Escape');await expect(menu).toBeFocused();}
    else await seek(run,p.getByRole('link',{name:'Business Agent',exact:true}).first());
   });
   if(process.env.WP7B_NATIVE_HOLD==='1' && channel==='chrome' && width===1440){
    await p.evaluate(token=>document.title='WP7B QA '+token,s.token);
    await fs.writeFile(path.join(s.folder,'native-ready.json'),JSON.stringify({token:s.token,route:new URL(p.url()).pathname,synthetic:true}));
    const began=Date.now();while(Date.now()-began<180000 && !await fs.access(path.join(s.folder,'native-continue.json')).then(()=>true).catch(()=>false))await p.waitForTimeout(500);
    report.native_hold={available:true,continued:await fs.access(path.join(s.folder,'native-continue.json')).then(()=>true).catch(()=>false)};
   }
   await check(run,'B-GOALS',async()=>{await p.goto(s.origin+'/intelligence/business-agent');run.assertionStage='goal history heading';await expect(p.getByRole('heading',{name:'Research goals and runs',exact:true})).toBeVisible();const details=p.locator('details.goal-creation');run.assertionStage='goal creation disclosure';await expect(details).toBeVisible();if(r1)report.goal_diagnostics.push({context:run.label,stage:'before open check',open:await details.getAttribute('open'),time:await p.evaluate(()=>performance.now())});if(!await details.getAttribute('open').then(v=>v!==null)){run.assertionStage='keyboard open goal disclosure';await activate(run,details.locator(':scope > summary'));}if(r1)report.goal_diagnostics.push({context:run.label,stage:'before textarea',open:await details.getAttribute('open'),time:await p.evaluate(()=>performance.now())});run.assertionStage='keyboard reach goal textarea';try{await type(run,p.locator('textarea[name=goal]'),'[QA SYNTHETIC] Keyboard goal review only');await p.keyboard.press('Shift+Tab');await p.keyboard.press('Tab');await expect(p.locator('textarea[name=goal]')).toBeFocused();}finally{if(r1)report.goal_diagnostics.push({context:run.label,stage:'after assertion',open:await details.getAttribute('open'),events:await p.evaluate(()=>globalThis.__r1GoalEvents)});}});
   if(r1)await check(run,'R1-GOAL-PENDING',async()=>{
    let release,seen,finished;const gate=new Promise(r=>release=r),received=new Promise(r=>seen=r),done=new Promise(r=>finished=r);
    const pattern='**/api/v1/intelligence/business-agent/goals';
    const handler=async route=>{try{const response=await route.fetch();seen();await gate;await route.fulfill({response});}finally{finished();}};
    await p.route(pattern,handler);
    try{
     await p.goto(s.origin+'/intelligence/business-agent');await received;
     const input=p.locator('textarea[name=goal]'),details=p.locator('details.goal-creation');
     if(!await details.getAttribute('open').then(v=>v!==null))await activate(run,details.locator(':scope > summary'));
     await type(run,input,'[QA SYNTHETIC] Preserve focused draft while saved goals load');
     await p.screenshot({path:path.join(run.directory,'r1-goal-before-delayed-response.png')});
     report.goal_diagnostics.push({context:run.label,stage:'pending focused draft',open:await details.getAttribute('open'),focused:await input.evaluate(e=>e===document.activeElement)});
     release();await done;await expect(p.getByRole('heading',{name:f.goal.raw_goal,exact:true})).toBeVisible();
     report.goal_diagnostics.push({context:run.label,stage:'saved goals arrived',open:await details.getAttribute('open'),focused:await input.evaluate(e=>e===document.activeElement)});
     await expect(input).toBeVisible();await expect(input).toBeFocused();await expect(input).toHaveValue('[QA SYNTHETIC] Preserve focused draft while saved goals load');
    }finally{release();await done;await p.unroute(pattern,handler);}
   });
   if(r1)await check(run,'R1-GOAL-DISCLOSURE',async()=>{
    await p.goto(s.origin+'/intelligence/business-agent');await expect(p.getByRole('heading',{name:f.goal.raw_goal,exact:true})).toBeVisible();
    const details=p.locator('details.goal-creation'),summary=details.locator(':scope > summary'),input=p.locator('textarea[name=goal]');
    if(await details.getAttribute('open').then(v=>v!==null))await activate(run,summary);
    await expect(summary).toHaveAttribute('aria-expanded','false');await expect(input).not.toBeVisible();
    await activate(run,summary,'Space');await expect(summary).toHaveAttribute('aria-expanded','true');await type(run,input,'abc');
    await activate(run,p.getByRole('button',{name:'Create research goal',exact:true}));await expect(p.locator('#goal-validation')).not.toHaveText('');
    await type(run,input,'[QA SYNTHETIC] valid keyboard draft');await expect(p.locator('#goal-validation')).toHaveCount(0);
    const goalContrast=await measureTargets(run,['textarea[name=goal]','#goal-help'],'goal-'+run.label);report.contrast.push(...goalContrast);
    expect(goalContrast.filter(x=>x.status==='FAIL' || x.focus_indicator?.status==='FAIL')).toHaveLength(0);
    await p.reload();await expect(p.getByRole('heading',{name:f.goal.raw_goal,exact:true})).toBeVisible();await expect(summary).toHaveAttribute('aria-expanded','false');
    await activate(run,summary,'Enter');await expect(input).toBeVisible();await seek(run,input);
   });
   await routeReview(run,'B-RESEARCH','/intelligence/research');
   await routeReview(run,'B-OPPORTUNITY','/intelligence/product-opportunities/'+f.op.id+'?goal_id='+f.goal.id);
   await routeReview(run,'B-CATALOG','/catalog/'+f.ops.product.id,p=>p.locator('[name=new-variant-key]'));
   await check(run,'B-SPACE',async()=>{const control=p.getByRole('checkbox',{name:'Make primary',exact:true});await seek(run,control);const initial=await control.isChecked();await p.keyboard.press('Space');expect(await control.isChecked()).toBe(!initial);await p.keyboard.press('Space');expect(await control.isChecked()).toBe(initial);});
   await check(run,'B-CATALOG-ERROR',async()=>{
    await type(run,p.locator('[name=new-variant-key]'),'qa-wp7b-'+channel+width);
    await type(run,p.locator('[name=new-variant-options]'),'{invalid');
    await activate(run,p.getByRole('button',{name:'Add variant',exact:true}));
    await expect(p.getByRole('heading',{name:'Change not completed',exact:true})).toBeVisible();
    await type(run,p.locator('[name=new-variant-options]'),JSON.stringify({color:'Blue-'+channel+width}));
    await type(run,p.locator('[name=new-variant-title]'),'[QA SYNTHETIC] keyboard variant');
    await activate(run,p.getByRole('button',{name:'Add variant',exact:true}));
    await expect(p.locator('[name=new-variant-key]')).toHaveValue('');
   });
   await routeReview(run,'B-SUPPLIERS','/intelligence/cross-marketplace?opportunity_id='+f.op.id);
   await routeReview(run,'B-SOURCING','/intelligence/supplier-shortlisting');
   await routeReview(run,'B-ECONOMICS','/intelligence/sourcing-economics?opportunity_id='+f.op.id+'&assessment_id='+f.assessment.id);
   await routeReview(run,'B-FINANCE','/marketplaces/financials');
   await routeReview(run,'B-INVENTORY','/marketplaces/inventory');
   await routeReview(run,'B-ORDERS','/marketplaces/orders');
   await routeReview(run,'B-MARKETPLACE','/marketplaces/accounts');
   await check(run,'B-IMPORT-GROUP',async()=>{const group=p.locator('.marketplace-actions').first();await expect(group).toBeVisible();await expect(group).toHaveAttribute('role','group');await expect(group).toHaveAttribute('aria-label','Read-only imports');await seek(run,group.getByRole('button').first());});
   await routeReview(run,'B-MEESHO','/marketplaces/listings/'+f.meesho.id+'/meesho');
   await check(run,'B-EDITOR-GROUP',async()=>{const group=p.locator('.inner-tabs');await expect(group).toBeVisible();await expect(group).toHaveAttribute('role','group');await expect(group).toHaveAttribute('aria-label','Listing editor sections');await activate(run,group.getByRole('button',{name:'Category',exact:true}));await expect(group.getByRole('button',{name:'Category',exact:true})).toBeFocused();});
   await routeReview(run,'B-VIDEO','/ai/video');
   await routeReview(run,'B-SOCIAL','/social');
   await routeReview(run,'B-ADS','/ads/create',p=>p.locator('select[name=account_id]'));
   await check(run,'B-DIALOG',async()=>{
    await p.goto(s.origin+'/ads/recommendations');await expect(p.getByRole('heading',{name:'Optimization intelligence',exact:true})).toBeVisible();await expect(p.getByText('Loading optimization intelligence...',{exact:true})).not.toBeVisible();
    if(await p.getByText('Optimization data is unavailable. Check the authenticated API connection.',{exact:true}).isVisible()){
      report.dialog_recovery_attempts=(report.dialog_recovery_attempts||0)+1;await p.reload();await expect(p.getByRole('heading',{name:'Optimization intelligence',exact:true})).toBeVisible();await expect(p.getByText('Loading optimization intelligence...',{exact:true})).not.toBeVisible();
    }
    const trigger=p.getByRole('button',{name:'Preview',exact:true}).first();
    await activate(run,trigger);const dialog=p.getByRole('dialog',{name:'Preview optimization',exact:true});await expect(dialog).toBeVisible();
    expect(await dialog.evaluate(e=>e.contains(document.activeElement)),'Opening focus must enter modal').toBe(true);
    await p.keyboard.press('Tab');expect(await dialog.evaluate(e=>e.contains(document.activeElement))).toBe(true);
    await p.keyboard.press('Shift+Tab');expect(await dialog.evaluate(e=>e.contains(document.activeElement))).toBe(true);
    await p.keyboard.press('Space');await expect(dialog).not.toBeVisible();await expect(trigger).toBeFocused();
    await p.keyboard.press('Enter');await expect(dialog).toBeVisible();expect(await dialog.evaluate(e=>e.contains(document.activeElement))).toBe(true);
    await p.keyboard.press('Escape');await expect(dialog).not.toBeVisible();await expect(trigger).toBeFocused();
    (report.dialog_keyboard_verified ||= []).push({context:run.label,entry:true,tab:true,shift_tab:true,space_close:true,escape:true,restoration:true});
    if(r1){await p.keyboard.press('Enter');await expect(dialog).toBeVisible();report.contrast.push(...await measureTargets(run,['[role=dialog] h2','[role=dialog] p','[role=dialog] button'],'ads-dialog-'+run.label));await p.keyboard.press('Tab');const closeContrast=await measureTargets(run,['[role=dialog] button'],'ads-close-focus-'+run.label);report.contrast.push(...closeContrast);expect(closeContrast.filter(x=>x.status==='FAIL' || x.focus_indicator?.status==='FAIL')).toHaveLength(0);await p.keyboard.press('Escape');}
   });
   if(r1)await check(run,'R1-DIALOG-REFLOW',async()=>{
    await p.setViewportSize({width:320,height:900});
    try{
     const trigger=p.getByRole('button',{name:'Preview',exact:true}).first();await activate(run,trigger);
     const dialog=p.getByRole('dialog',{name:'Preview optimization',exact:true});await expect(dialog).toBeVisible();
     const bounds=await dialog.evaluate(e=>{const r=e.getBoundingClientRect();return{left:r.left,right:r.right,width:r.width,inner:innerWidth,scroll:e.scrollWidth,client:e.clientWidth};});
     expect(bounds.left).toBeGreaterThanOrEqual(0);expect(bounds.right).toBeLessThanOrEqual(bounds.inner);expect(bounds.scroll).toBeLessThanOrEqual(bounds.client+1);
     await expect(p.locator('#preview-title')).toBeInViewport();
     await p.keyboard.press('Tab');await expect(dialog.getByRole('button',{name:'Close',exact:true})).toBeFocused();
     await p.keyboard.press('Escape');await expect(dialog).not.toBeVisible();await expect(trigger).toBeFocused();
     report.responsive_dialog ||= [];report.responsive_dialog.push({context:run.label,bounds,native_zoom:false});
    }finally{await p.setViewportSize({width,height:900});}
   });
   if(r1 && process.env.WP7BR1_REVIEWS==='1'){
    for(const [id,url,selectors] of [
     ['SOCIAL',f.reviews?'/social/posts/'+f.reviews.social.id:'', ['main textarea','.timeline strong']],
     ['FLIPKART',f.reviews?'/marketplaces/listings/'+f.reviews.flip.id+'/flipkart':'',['.inner-tabs button','main form label','main input[type=number]']],
     ['MEESHO','/marketplaces/listings/'+f.meesho.id+'/meesho',['.inner-tabs button','main input[type=number]']],
     ['FINANCE','/marketplaces/financials',['main caption','main th']],
     ['CAMPAIGN',f.reviews?'/campaigns/'+f.reviews.campaign.id:'',['.reschedule-panel textarea']]]){
      await check(run,'R1-CONTRAST-'+id,async()=>{if(!url)throw Error('REQUIRED_REVIEW_FIXTURE_NOT_ESTABLISHED');await p.goto(s.origin+url);await expect(p.locator('main')).toBeVisible();
       if(id==='SOCIAL')await expect(p.getByRole('heading',{name:'Image draft review',exact:true})).toBeVisible();
       if(id==='FLIPKART' || id==='MEESHO'){
        await expect(p.getByRole('heading',{name:/^Listing editor:/})).toBeVisible();
        await activate(run,p.locator('.inner-tabs').getByRole(id==='FLIPKART'?'tab':'button',{name:'Pricing',exact:true}));
        await expect(p.getByRole('button',{name:'Review and confirm price',exact:true})).toBeEnabled();
       }
       if(id==='FINANCE')await expect(p.getByRole('region',{name:'Revenue trend table',exact:true})).toBeVisible();
       if(id==='CAMPAIGN')await activate(run,p.getByRole('button',{name:'Reschedule Activity',exact:true}).first());
       const rows=await measureTargets(run,selectors,id+'-'+run.label);report.contrast.push(...rows);expect(rows.filter(x=>x.status==='FAIL')).toHaveLength(0);expect(rows.filter(x=>x.focus_indicator?.status==='FAIL')).toHaveLength(0);expect(rows.some(x=>x.status==='PASS')).toBe(true);
      });
    }
   }
   await check(run,'B-REFLOW',async()=>{await p.goto(s.origin+'/dashboard');await p.evaluate(()=>document.documentElement.style.fontSize='200%');expect(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await p.evaluate(()=>document.documentElement.style.fontSize='');});
   await check(run,'B-320-REFLOW',async()=>{await p.setViewportSize({width:320,height:900});await p.goto(s.origin+'/catalog/'+f.ops.product.id);await expect(p.getByRole('heading',{level:1})).toBeVisible();expect(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await p.setViewportSize({width,height:900});});
  }
 }
}catch(e){report.setup_failure={code:e.message.split('\n')[0].slice(0,160)};}
finally {
 for(const run of runs) await finish(run);for(const browser of browsers)await browser.close();
 report.source_unchanged=JSON.stringify(testedSource)===JSON.stringify(await sourceFingerprint());
 report.status=report.setup_failure?'BLOCKED':report.checks.some(c=>c.status==='FAIL')?'FAIL':'EXECUTED';await save();
 console.log(JSON.stringify({token:s.token,status:report.status,checks:report.checks.length,passed:report.checks.filter(c=>c.status==='PASS').length,failed:report.checks.filter(c=>c.status==='FAIL').length}));
}
process.exitCode=report.setup_failure?1:0; // Assessment failures remain failures in the report, not setup failure.
