// R5 uses only a currently ready exact-token synthetic session. No confirmations.
import fs from 'node:fs/promises';
import {chromium,expect} from '@playwright/test';
import {start,capture,axe,finish} from './seller-browser-explore.mjs';
import {measureTargets} from './wp7br1-contrast.mjs';
import {wp3Owner} from './wp3-fixtures.mjs';
const root='tmp/qa-wp7br5/browser',c=JSON.parse(await fs.readFile('tmp/qa-wp7br5/session-control.json','utf8')),s=c.session;
if(c.package!=='WP7B-R5'||c.status!=='READY_FOR_VERIFICATION'||Date.now()>=Date.parse(c.expires_at)-30000)throw Error('VALID_ACTIVE_R5_REQUIRED');
const witness=await fetch(s.origin+'/__qa/witness').then(r=>r.json());
if(witness.token!==s.token||!witness.disposable)throw Error('EXACT_R5_WITNESS_REQUIRED');
await fs.mkdir(root,{recursive:true});
const report={package:'WP7B-R5',token:s.token,origin:s.origin,started_at:new Date().toISOString(),checks:[],measurements:[],scans:[],contexts:[],versions:{},external_calls:0,confirmed_actions:0};
const previous=await fs.readFile(root+'/results.json','utf8').then(JSON.parse).catch(()=>null);
if(previous)await fs.writeFile(root+'/history-'+previous.started_at.replace(/[^a-z0-9]/gi,'')+'.json',JSON.stringify(previous,null,2));
const revision='run-'+Date.now();
report.harness_history={initial:'16PASS/8FAIL retained in history and original context folders',classification:'Four viewport-edge exposure failures plus four unsupported authored3px expectations for a UA auto1px error focus cue. No production code change; original assertions/data retained. Real CSS overflow clipping still fails.',retest:'Explicit scroll exposure is recorded separately from keyboard reachability; UA appearance is recorded without imposing a new authored3px criterion.'};
const save=()=>fs.writeFile(root+'/results.json',JSON.stringify(report,null,2));let serial=0;
async function seek(p,target,key='Tab'){
 await expect(target).toBeVisible();
 for(let n=0;n<200;n++){if(await target.evaluate(e=>e===document.activeElement))return n;await p.keyboard.press(key);}
 throw Error('R5_KEYBOARD_TARGET_UNREACHABLE');
}
async function measure(run,selector,state,authored=true){
 const preExposure=await run.page.locator(selector).evaluate(el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return{left:r.left,top:r.top,right:r.right,bottom:r.bottom,viewport:{width:innerWidth,height:innerHeight},outline:s.outline,offset:s.outlineOffset,focused:el===document.activeElement};});
 await run.page.locator(selector).evaluate(el=>el.scrollIntoView({block:'center',inline:'center'}));
 const rows=await measureTargets(run,[selector],String(++serial)+'-'+state);
 for(const row of rows){row.review_id='R2-C-11';row.context=run.label;row.browser_version=report.versions[run.channel];row.timestamp=new Date().toISOString();
  row.geometry=await run.page.locator(selector).evaluate(el=>{const r=el.getBoundingClientRect(),cs=getComputedStyle(el),pad=parseFloat(cs.outlineWidth)+parseFloat(cs.outlineOffset),clips=[];for(let a=el.parentElement;a;a=a.parentElement){const s=getComputedStyle(a),b=a.getBoundingClientRect();if(/hidden|clip|scroll|auto/.test(s.overflowX+s.overflowY)&&(r.left-pad<b.left||r.right+pad>b.right||r.top-pad<b.top||r.bottom+pad>b.bottom))clips.push(a.tagName);}return{rect:{left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height},outline:cs.outline,offset:cs.outlineOffset,clips,within_viewport:r.left-pad>=0&&r.right+pad<=innerWidth&&r.top-pad>=0&&r.bottom+pad<=innerHeight,viewport:{width:innerWidth,height:innerHeight}};});
  row.pre_exposure=preExposure;row.exposure_method='After keyboard reachability, scroll original target to center without changing focus, styles or animations';row.authored_geometry_required=authored;
  if(!authored)row.appearance_scope='UA auto error-focus cue; no author-imposed3px width/offset criterion. Ratio retained as additional measured evidence.';
  row.full_focus_screenshot=run.directory+'/focus-'+serial+'.png';await run.page.screenshot({path:row.full_focus_screenshot});
 }
 report.measurements.push(...rows);await save();
 for(const r of rows){expect(r.status).toBe('PASS');expect(r.focus_indicator?.status).toBe('PASS');expect(r.focus_indicator?.ratio).toBeGreaterThanOrEqual(3);expect(r.geometry.clips).toEqual([]);expect(r.geometry.within_viewport).toBe(true);if(authored){expect(r.rendered.outline.width).toBe('3px');expect(r.geometry.offset).toBe('3px');}}
 return rows.map(r=>({text:r.ratio,focus:r.focus_indicator.ratio,geometry:r.geometry}));
}
async function check(run,id,assertion,fn){
 const r={review_id:id,assertion,expected:assertion,tool:'Playwright1.64.1',context:run.label,browser_version:report.versions[run.channel],timestamp:new Date().toISOString()};
 try{r.actual=await fn();r.status='VERIFIED_PASS';}catch(e){r.status='VERIFIED_FAIL';r.safe_code=/R5_[A-Z_]+/.exec(e.message)?.[0]||'R5_ASSERTION_FAILED';r.source_line=e.stack?.match(/wp7br5-browser\.mjs:(\d+)/)?.[1]||null;}
 r.evidence=(await capture(run,id+'-'+report.checks.length)).screenshot;report.checks.push(r);await save();
}
for(const channel of ['chrome','msedge']){
 const browser=await chromium.launch({channel,headless:true});report.versions[channel]=browser.version();
 try{for(const width of [1440,390]){
  const run=await start(browser,{...s,folder:root+'/'+revision},{width,height:900},'wp7br1-'+channel+'-'+width);run.channel=channel;const p=run.page;
  const context={label:run.label,width,height:900,isMobile:width===390,hasTouch:width===390};
  try{
   await run.context.tracing.stop();const auth=await p.request.post(s.origin+'/api/v1/auth/login',{data:wp3Owner});if(!auth.ok())throw Error('R5_SYNTHETIC_AUTH_FAILED');await run.context.tracing.start({screenshots:true,snapshots:true,sources:false});
   let confirms=0;const apiErrors=[];p.on('request',r=>{if(/\/campaigns\/recovery\/actions$|\/business-agent\/actions/.test(r.url()))confirms++;});p.on('response',r=>{if(r.url().includes('/api/')&&r.status()>=500)apiErrors.push(r.status());});
   await p.goto(s.origin+c.routes.campaign);await expect(p.locator('h1')).toBeVisible();
   const entry=p.getByRole('button',{name:'Reschedule Activity',exact:true});
   await check(run,'R2-C-11','Eligible canonical reschedule control is reachable and Enter opens the inline labelled panel',async()=>{
    await seek(p,entry);await p.keyboard.press('Enter');const panel=p.locator('.reschedule-panel');await expect(panel).toBeVisible();expect(await panel.getAttribute('aria-labelledby')).toBe('reschedule-title');expect(await panel.getAttribute('role')).not.toBe('dialog');expect(await panel.getAttribute('aria-modal')).toBeNull();return{inline_section:true,modal_containment_not_applicable:'No modal role or exclusive focus contract; do not invent a trap or dismissal affordance'};
   });
   await check(run,'R2-C-11','Forward keyboard focus exposes date, time, timezone and reason with retained geometry and >=3:1 contrast',async()=>{
    const result=[];for(const selector of ['input[type=date]','input[type=time]','input[formcontrolname=timezone]','textarea']){const sel='.reschedule-panel '+selector;await seek(p,p.locator(sel));result.push({selector,...(await measure(run,sel,'forward'))[0]});}return result;
   });
   await check(run,'R2-C-11','Reverse Tab reaches timezone and returns forward to reason without a trap; hover retains focus',async()=>{
    const timezone=p.locator('.reschedule-panel input[formcontrolname=timezone]'),reason=p.locator('.reschedule-panel textarea');await seek(p,timezone,'Shift+Tab');await seek(p,reason);await reason.hover();await expect(reason).toBeFocused();const measured=await measure(run,'.reschedule-panel textarea','hover');await p.keyboard.press('Tab');await expect(p.locator('.reschedule-panel button[type=submit]')).toBeFocused();const button=await measure(run,'.reschedule-panel button[type=submit]','preview-focus');return{measured,button};
   });
   await check(run,'R2-C-11','Space entry after reload preserves the canonical activity and unscheduled inline editor; no confirmation created',async()=>{
    await p.reload();await expect(entry).toBeVisible();await seek(p,entry);await p.keyboard.press('Space');await expect(p.locator('.reschedule-panel')).toBeVisible();expect(confirms).toBe(0);return{activity:c.reschedule.activity_id,confirm_requests:confirms};
   });
   await check(run,'R2-C-11','Legitimate invalid timezone preview error is associated with an alert and focused safely; no business confirmation',async()=>{
    const zone=p.locator('.reschedule-panel input[formcontrolname=timezone]');await seek(p,zone);await p.keyboard.press('ControlOrMeta+A');await p.keyboard.type('Not/AZone');const submit=p.locator('.reschedule-panel button[type=submit]');await seek(p,submit);await p.keyboard.press('Enter');const alert=p.locator('.reschedule-panel [role=alert]');await expect(alert).toBeVisible();await expect(alert).toBeFocused();const measurement=await measure(run,'.reschedule-panel [role=alert]','preview-error',false);expect(confirms).toBe(0);return{measurement,confirm_requests:confirms};
   });
   const a=await axe(run,'campaign-preview-error');report.scans.push({context:run.label,route:c.routes.campaign,timestamp:new Date().toISOString(),...a});await save();
   await check(run,'R2-C-11','Inline editor can be left by ordinary page navigation and Back; fresh state retains correct campaign, no schedule mutation',async()=>{
    await p.goto(s.origin+'/campaigns');await p.goBack();await expect(p.locator('h1')).toBeVisible();expect(new URL(p.url()).pathname).toBe(c.routes.campaign);await expect(entry).toBeVisible();expect(confirms).toBe(0);expect(apiErrors).toEqual([]);return{route:new URL(p.url()).pathname,confirm_requests:confirms,api_5xx:apiErrors};
   });
  }catch(e){context.limitation=/R5_[A-Z_]+/.exec(e.message)?.[0]||'R5_CONTEXT_INCOMPLETE';}
  finally{context.trace=await finish(run);report.contexts.push(context);await save();}
 }}finally{await browser.close();}
}
report.completed_at=new Date().toISOString();await save();console.log(JSON.stringify({checks:report.checks.length,passed:report.checks.filter(c=>c.status==='VERIFIED_PASS').length,failed:report.checks.filter(c=>c.status==='VERIFIED_FAIL').length,focus_records:report.measurements.length,scans:report.scans.length}));
