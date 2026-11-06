// Verification only: reuse a still-valid R3 session, never create/extend resources.
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium,expect} from '@playwright/test';
import {start,capture,axe,finish} from './seller-browser-explore.mjs';
import {measureTargets} from './wp7br1-contrast.mjs';
import {wp3Owner} from './wp3-fixtures.mjs';
const control=JSON.parse(await fs.readFile('tmp/qa-wp7br3/session-control.json','utf8'));
const s=control.session, deadline=Date.parse(control.expires_at)-15000;
if(control.status!=='AWAITING_HUMAN_OBSERVATION'||Date.now()>=deadline||!s?.synthetic)throw Error('VALID_EXISTING_R3_REQUIRED');
const witness=await fetch(s.origin+'/__qa/witness',{signal:AbortSignal.timeout(5000)}).then(r=>r.json());
if(!witness.disposable||witness.token!==s.token)throw Error('EXACT_R3_WITNESS_REQUIRED');
const folder=path.resolve('tmp/qa-wp7br3a');await fs.mkdir(folder,{recursive:true});
const report={package:'WP7B-R3A',started_at:new Date().toISOString(),token:s.token,origin:s.origin,expires_at:control.expires_at,
  existing_session_only:true,new_database_operations:0,checks:[],contrast:[],scans:[],versions:{},speech_verified_by_automation:false,native_zoom:'NOT_VERIFIED',runs:[]};
const save=()=>fs.writeFile(path.join(folder,'browser-results.json'),JSON.stringify(report,null,2));
async function check(run,id,assertion,fn){
 if(Date.now()>=deadline)throw Error('EXISTING_SESSION_EXPIRES');
 const row={review_id:id,assertion,expected:'Stated deterministic assertion holds',browser:run.label,tool:'Playwright',timestamp:new Date().toISOString(),route:new URL(run.page.url()).pathname};
 try{row.actual=await fn();row.status='VERIFIED_PASS';}catch(e){row.status='VERIFIED_FAIL';row.actual=e.message.split('\n')[0].slice(0,200);}
 row.evidence=(await capture(run,id+'-'+report.checks.length)).screenshot;report.checks.push(row);await save();
}
async function tabTo(p,target){for(let n=0;n<120;n++){if(await target.evaluate(e=>e===document.activeElement))return n;await p.keyboard.press('Tab');}throw Error('KEYBOARD_TARGET_NOT_REACHED');}
const routes=control.routes;
try{
 for(const channel of ['chrome','msedge']){
  if(Date.now()>=deadline)break;
  const browser=await chromium.launch({channel,headless:true});report.versions[channel]=browser.version();
  try{for(const width of [1440,390]){
   if(Date.now()>=deadline)break;
   const run=await start(browser,{...s,folder},{width,height:900},'wp7br1-r3a-'+channel+'-'+width);report.runs.push({label:run.label,viewport:{width,height:900}});
   const p=run.page;p.setDefaultTimeout(4000);
   try{
    await p.goto(s.origin+'/login');
    await check(run,'R2-SR-01','Email/password accessible labels and Show password name/state; keyboard order and state persistence',async()=>{
     const email=p.getByRole('textbox',{name:'Email',exact:true}),password=p.locator('#password'),toggle=p.getByRole('button',{name:'Show password',exact:true});
     await expect(email).toBeVisible();await expect(password).toHaveAttribute('type','password');
     const tabs=await tabTo(p,email);await p.keyboard.press('Tab');await expect(password).toBeFocused();await p.keyboard.press('Tab');await expect(toggle).toBeFocused();
     await p.keyboard.press('Space');await expect(password).toHaveAttribute('type','text');await expect(toggle).toBeFocused();
     const shown=await toggle.getAttribute('aria-pressed');await p.keyboard.press('Space');await expect(password).toHaveAttribute('type','password');
     return {email_to_password_to_toggle:true,initial_tabs:tabs,shown_pressed:shown,hidden_pressed:await toggle.getAttribute('aria-pressed'),speech:'not inferred'};
    });
    // No credentials in retained traces. Canonical synthetic login in memory.
    await run.context.tracing.stop();
    const login=await p.request.post(s.origin+'/api/v1/auth/login',{data:wp3Owner});
    if(!login.ok())throw Error('CANONICAL_SYNTHETIC_LOGIN_FAILED');
    await run.context.tracing.start({screenshots:true,snapshots:true,sources:false});
    await p.goto(s.origin+routes.goals);
    await check(run,'R2-SR-03','Disclosure Enter and Space preserve focus and match expanded state',async()=>{
     const summary=p.locator('details.goal-creation > summary');await tabTo(p,summary);
     const before=await summary.getAttribute('aria-expanded');await p.keyboard.press('Enter');await expect(summary).toBeFocused();
     const after=await summary.getAttribute('aria-expanded');expect(after).not.toBe(before);
     await p.keyboard.press('Space');await expect(summary).toHaveAttribute('aria-expanded',before);return {before,after,restored:before};
    });
    await check(run,'R2-SR-04','Goal textarea has accessible label and help relationship',async()=>{
     const summary=p.locator('details.goal-creation > summary');if(await summary.getAttribute('aria-expanded')==='false')await summary.press('Enter');
     const field=p.locator('textarea[name=goal]');await expect(field).toBeVisible();
     await tabTo(p,field);await expect(field).toHaveAccessibleName(/what are you trying to accomplish/i);
     return await field.evaluate(e=>({required:e.required,describedby:e.getAttribute('aria-describedby'),invalid:e.getAttribute('aria-invalid'),focused:e===document.activeElement}));
    });
    report.contrast.push(...(await measureTargets(run,['textarea[name=goal]','#goal-help'],'goal-'+channel+'-'+width)).map(r=>({...r,review_id:'R2-C-06',timestamp:new Date().toISOString()})));
    for(const key of ['accounts','meesho','ads','finance','flipkart','social']){
     if(Date.now()>=deadline)break;
     await p.goto(s.origin+routes[key]);await expect(p.locator('h1')).toBeVisible();
     if(key==='accounts')await check(run,'R2-SR-06','Read-only import group is named and all child controls expose names/states; no import executed',async()=>{
      const group=p.getByRole('group',{name:/import/i});await expect(group.first()).toBeVisible();return await group.first().ariaSnapshot();
     });
     if(key==='meesho')await check(run,'R2-SR-07','Named listing editor group supports keyboard panel activation',async()=>{
      const group=p.getByRole('group',{name:'Listing editor sections'});await expect(group).toBeVisible();const button=group.getByRole('button',{name:'Product',exact:true});await tabTo(p,button);await p.keyboard.press('Enter');await expect(button).toBeFocused();return await group.ariaSnapshot();
     });
     if(key==='ads'){
      const preview=p.getByRole('button',{name:'Preview',exact:true}).first();
      await check(run,'R2-SR-08','Preview opens a named dialog and focus enters title',async()=>{
       await tabTo(p,preview);await p.keyboard.press('Enter');const dialog=p.getByRole('dialog',{name:'Preview optimization'});await expect(dialog).toBeVisible();await expect(dialog.locator('h2')).toBeFocused();return await dialog.ariaSnapshot();
      });
      await check(run,'R2-SR-09','Tab/Shift+Tab containment, Space Close, Escape and return focus',async()=>{
       const dialog=p.getByRole('dialog',{name:'Preview optimization'});await expect(dialog).toBeVisible();const sequence=[];
       for(const key of ['Tab','Tab','Shift+Tab']){await p.keyboard.press(key);expect(await dialog.evaluate(e=>e.contains(document.activeElement))).toBe(true);sequence.push(await p.evaluate(()=>({tag:document.activeElement.tagName,text:document.activeElement.textContent?.slice(0,80)})));}
       const close=dialog.getByRole('button',{name:'Close',exact:true});await tabTo(p,close);await p.keyboard.press('Space');await expect(dialog).not.toBeVisible();await expect(preview).toBeFocused();await p.keyboard.press('Enter');await expect(dialog).toBeVisible();await p.keyboard.press('Escape');await expect(preview).toBeFocused();return sequence;
      });
     }
     const selectors=key==='finance'?['main caption','main th']:key==='social'?['main textarea','.timeline strong']:key==='accounts'?['main button','main input']:key==='meesho'||key==='flipkart'?['.inner-tabs button','main form label','main input[type=number]']:[];
     const map=key==='finance'?'R2-C-07':key==='social'?'R2-C-01':key==='accounts'?'R2-C-12':key==='meesho'?'R2-C-05':'R2-C-03';
     // Address every matched node separately; do not silently drop nodes beyond the old eight-sample bound.
     for(const sel of selectors){const count=await p.locator(sel).count();for(let i=0;i<count&&Date.now()<deadline;i++){
      const exact=`:is(${sel}):nth-match(:is(${sel}), ${i+1})`;
      const target=p.locator(sel).nth(i);if(!await target.isVisible())continue;
      // Playwright's nth-match pseudo-class uniquely scopes the existing verified sampler.
      const rows=await measureTargets(run,[`:nth-match(${sel}, ${i+1})`],key+'-'+channel+'-'+width+'-'+i);
      report.contrast.push(...rows.map(r=>({...r,review_id:map,original_selector:sel,original_index:i,timestamp:new Date().toISOString()})));
     }}
     report.scans.push({review_surface:key,browser:run.label,timestamp:new Date().toISOString(),...await axe(run,key)});await save();
    }
   }catch(e){report.runs.at(-1).limitation=/EXPIRES/.test(e.message)?'SESSION_EXPIRY':e.message.split('\n')[0].slice(0,160);}
   finally{report.runs.at(-1).trace=await finish(run);await save();}
  }}finally{await browser.close();}
 }
}finally{report.completed_at=new Date().toISOString();report.passed=report.checks.filter(r=>r.status==='VERIFIED_PASS').length;report.failed=report.checks.filter(r=>r.status==='VERIFIED_FAIL').length;await save();console.log(JSON.stringify({checks:report.checks.length,passed:report.passed,failed:report.failed,contrast_records:report.contrast.length,scans:report.scans.length,versions:report.versions}));}
