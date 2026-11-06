// Synthetic R5 only. Real pending response + explicit browser transport fault.
// Never misrepresents injected network failure as a provider/application outage.
import fs from 'node:fs/promises';
import {chromium,expect} from '@playwright/test';
import {start,capture,axe,finish} from './seller-browser-explore.mjs';
import {resolveContrast,waitForTransitions} from './wp7br1-contrast.mjs';
import {wp3Owner} from './wp3-fixtures.mjs';
const c=JSON.parse(await fs.readFile('tmp/qa-wp7br5/session-control.json','utf8')),s=c.session,root='tmp/qa-wp7br5/ads-states';
if(c.package!=='WP7B-R5'||c.status!=='READY_FOR_VERIFICATION'||Date.now()>Date.parse(c.expires_at)-30000)throw Error('ACTIVE_R5_REQUIRED');
const w=await fetch(s.origin+'/__qa/witness').then(r=>r.json());if(w.token!==s.token||!w.disposable)throw Error('EXACT_R5_REQUIRED');
await fs.mkdir(root,{recursive:true});const report={package:'WP7B-R5',token:s.token,started_at:new Date().toISOString(),checks:[],measurements:[],scans:[],contexts:[],versions:{},external_calls:0,confirmations:0,scope:'Actual page loading/error and real read-only dialog; explicit local-browser network fault, not provider evidence'};let serial=0;
const previous=await fs.readFile(root+'/results.json','utf8').then(JSON.parse).catch(()=>null);
if(previous)await fs.writeFile(root+'/history-'+previous.started_at.replace(/[^a-z0-9]/gi,'')+'.json',JSON.stringify(previous,null,2));
const revision='run-'+Date.now();
report.initial_sample_limitation='One initial Chrome desktop Close sample reported not fully within viewport, but its later full screenshot shows a fully visible control. Initial15PASS/1FAIL and images retained; no demonstrated persistent clipping cause inferred. Retest records rectangle settlement before measurement, without disabling scrolling/transitions or changing thresholds.';
const save=()=>fs.writeFile(root+'/results.json',JSON.stringify(report,null,2));
async function seek(p,t){await expect(t).toBeVisible();for(let i=0;i<200;i++){if(await t.evaluate(e=>e===document.activeElement))return;await p.keyboard.press('Tab');}throw Error('R5_ADS_KEYBOARD_TARGET_MISSING');}
async function sample(run,selector,state,focus=false){
 const target=run.page.locator(selector);await target.evaluate(el=>el.scrollIntoView({block:'center'}));
 const settlement=await target.evaluate(async el=>{const frames=[],start=performance.now();let stable=0,prior;while(performance.now()-start<1800){await new Promise(r=>requestAnimationFrame(r));const b=el.getBoundingClientRect(),r={time:performance.now()-start,left:b.left,top:b.top,width:b.width,height:b.height};frames.push(r);stable=prior&&['left','top','width','height'].every(k=>Math.abs(r[k]-prior[k])<0.01)?stable+1:0;prior=r;if(stable>=5)return{settled:true,frames};}return{settled:false,frames};});
 expect(settlement.settled).toBe(true);
 // Observe the already exposed target without the generic helper's additional
 // element-screenshot auto-scroll between computed data and image capture.
 expect(await waitForTransitions(target)).toBe(true);
 const m=await target.evaluate(el=>{const s=getComputedStyle(el),r=el.getBoundingClientRect(),hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2),ancestors=[];for(let a=el;a;a=a.parentElement){const c=getComputedStyle(a);ancestors.push({backgroundColor:c.backgroundColor,backgroundImage:c.backgroundImage,opacity:c.opacity});}return{color:s.color,fontSize:parseFloat(s.fontSize),fontWeight:parseInt(s.fontWeight),textShadow:s.textShadow,disabled:el.matches(':disabled'),visible:r.width>0&&r.height>0&&r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight,obscured:!!hit&&!el.contains(hit),focused:el===document.activeElement,outline:{color:s.outlineColor,width:s.outlineWidth,style:s.outlineStyle},ancestors,rect:{left:r.left,top:r.top,width:r.width,height:r.height}};});
 const ring=m.focused&&m.outline.style!=='none'&&parseFloat(m.outline.width)>0?{...resolveContrast({...m,color:m.outline.color,fontSize:24,fontWeight:700,textShadow:'none',ancestors:m.ancestors.slice(1)}),criterion:'1.4.11'}:{status:'NOT VERIFIED',reason:'No active outline sampled'};
 const row={state:String(++serial)+'-'+state,selector,review_id:'R2-C-09',context:run.label,timestamp:new Date().toISOString(),rendered:m,...resolveContrast(m),focus_indicator:ring,rectangle_settlement:settlement,full_screenshot:run.directory+'/full-'+serial+'.png',method:'Existing contrast arithmetic; no element screenshot/extra scroll after sampling'};
 await run.page.screenshot({path:row.full_screenshot});
 row.after_screenshot_rect=await target.evaluate(el=>{const r=el.getBoundingClientRect();return{left:r.left,top:r.top,width:r.width,height:r.height};});
 row.image_geometry_aligned=['left','top','width','height'].every(k=>Math.abs(m.rect[k]-row.after_screenshot_rect[k])<0.5);
 if(!row.image_geometry_aligned){row.status='NOT VERIFIED';row.temporal_limitation='Geometry changed during full image capture; no aligned visual PASS';}
 report.measurements.push(row);await save();expect(row.status).toBe('PASS');expect(row.image_geometry_aligned).toBe(true);if(focus){expect(row.focus_indicator.status).toBe('PASS');expect(row.focus_indicator.ratio).toBeGreaterThanOrEqual(3);}return[{ratio:row.ratio,focus:row.focus_indicator}];
}
async function check(run,id,text,fn){const row={review_id:id,assertion:text,expected:text,context:run.label,browser_version:report.versions[run.channel],timestamp:new Date().toISOString()};try{row.actual=await fn();row.status='VERIFIED_PASS';}catch(e){row.status='VERIFIED_FAIL';row.safe_code=/R5_[A-Z_]+/.exec(e.message)?.[0]||'R5_ADS_ASSERTION_FAILED';row.source_line=e.stack?.match(/wp7br5-ads-states\.mjs:(\d+)/)?.[1]||null;}row.evidence=(await capture(run,id+'-'+report.checks.length)).screenshot;report.checks.push(row);await save();}
for(const channel of ['chrome','msedge']){
 const b=await chromium.launch({channel,headless:true});report.versions[channel]=b.version();
 try{for(const width of [1440,390]){
  const run=await start(b,{...s,folder:root+'/'+revision},{width,height:900},'wp7br1-'+channel+'-'+width);run.channel=channel;const p=run.page,ctx={context:run.label,width,height:900,mobile:width===390};let release;
  try{
   await run.context.tracing.stop();const auth=await p.request.post(s.origin+'/api/v1/auth/login',{data:wp3Owner});if(!auth.ok())throw Error('R5_ADS_AUTH_FAILED');await run.context.tracing.start({screenshots:true,snapshots:true,sources:false});
   let mutationRequests=0;p.on('request',r=>{if(r.method()==='POST'&&/\/(?:confirm|execute|evaluate|actions)$/.test(new URL(r.url()).pathname))mutationRequests++;});
   const overview=s.origin+'/api/v1/ads/optimization/overview';let pendingResponse;const gate=new Promise(r=>release=r);
   await p.route(overview,async route=>{pendingResponse=await route.fetch();await gate;await route.fulfill({response:pendingResponse});});
   await p.goto(s.origin+c.routes.ads,{waitUntil:'domcontentloaded'});
   await check(run,'R2-C-09','Real page loading message remains readable with a polite live region while an actual response is pending',async()=>{const loading=p.getByText('Loading optimization intelligence...',{exact:true});await expect(loading).toBeVisible();expect(await loading.getAttribute('aria-live')).toBe('polite');const rows=await sample(run,'main p[aria-live=polite]','loading');report.scans.push({context:run.label,state:'loading',...await axe(run,'loading')});return{rows,speech_not_inferred:true,condition:'Actual response held, not fabricated'};});
   release();await expect(p.getByRole('button',{name:'Preview',exact:true}).first()).toBeVisible();await p.unroute(overview);expect(pendingResponse.ok()).toBe(true);
   const previewPath=s.origin+'/api/v1/ads/recommendations/*/preview';await p.route(previewPath,route=>route.abort('failed'));
   await check(run,'R2-C-09','A declared browser transport failure exposes the real application error text and alert semantics with sufficient contrast',async()=>{const trigger=p.getByRole('button',{name:'Preview',exact:true}).first();await seek(p,trigger);await p.keyboard.press('Enter');await expect(p.locator('main [role=alert]')).toBeVisible();const rows=await sample(run,'main [role=alert]','preview-transport-error');report.scans.push({context:run.label,state:'error',...await axe(run,'transport-error')});return{rows,fault_injected:'Browser-only abort for local read-only preview; not live provider or actual outage claim',message:await p.locator('main [role=alert]').innerText()};});
   await p.unroute(previewPath);await p.reload();await expect(p.getByRole('button',{name:'Preview',exact:true}).first()).toBeVisible();
   await check(run,'R2-C-09','After removing the injected fault, the canonical non-mutating preview title and Close retain readable text and keyboard focus',async()=>{const trigger=p.getByRole('button',{name:'Preview',exact:true}).first();await seek(p,trigger);await p.keyboard.press('Enter');const d=p.getByRole('dialog',{name:'Preview optimization'});await expect(d).toBeVisible();await expect(d.locator('h2')).toBeFocused();const title=await sample(run,'[role=dialog] h2','title',true);await seek(p,d.getByRole('button',{name:'Close',exact:true}));const close=await sample(run,'[role=dialog] button','close',true);report.scans.push({context:run.label,state:'dialog',...await axe(run,'dialog')});return{title,close,dialog_label:await d.getAttribute('aria-labelledby')};});
   await check(run,'R2-SR-09','Escape dismisses the read-only dialog and restores the actual Preview trigger without confirmation or evaluation',async()=>{await p.keyboard.press('Escape');await expect(p.getByRole('dialog')).not.toBeVisible();await expect(p.getByRole('button',{name:'Preview',exact:true}).first()).toBeFocused();expect(mutationRequests).toBe(0);return{mutations:mutationRequests,actual_speech_not_inferred:true};});
  }catch(e){ctx.limitation=/R5_[A-Z_]+/.exec(e.message)?.[0]||'R5_ADS_CONTEXT_INCOMPLETE';}
  finally{release?.();ctx.trace=await finish(run);report.contexts.push(ctx);await save();}
 }}finally{await b.close();}
}
report.completed_at=new Date().toISOString();await save();console.log(JSON.stringify({checks:report.checks.length,passed:report.checks.filter(c=>c.status==='VERIFIED_PASS').length,failed:report.checks.filter(c=>c.status==='VERIFIED_FAIL').length,scans:report.scans.length,measurements:report.measurements.length}));
