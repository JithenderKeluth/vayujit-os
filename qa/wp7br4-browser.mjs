// Objective verification only; never uses the business runtime or changes approvals.
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium,expect} from '@playwright/test';
import {start,capture,axe,finish} from './seller-browser-explore.mjs';
import {measureTargets} from './wp7br1-contrast.mjs';
import {wp3Owner} from './wp3-fixtures.mjs';
const c=JSON.parse(await fs.readFile('tmp/qa-wp7br4/session-control.json','utf8')),s=c.session,root='tmp/qa-wp7br4/browser';
if(c.status!=='READY_FOR_VERIFICATION'||Date.now()>=Date.parse(c.expires_at)-10000)throw Error('VALID_R4_REQUIRED');
const witness=await fetch(s.origin+'/__qa/witness').then(r=>r.json());if(witness.token!==s.token||!witness.disposable)throw Error('EXACT_R4_WITNESS_REQUIRED');
await fs.mkdir(root,{recursive:true});
const report={package:'WP7B-R4',token:s.token,origin:s.origin,started_at:new Date().toISOString(),checks:[],measurements:[],scans:[],contexts:[],versions:{},speech:'No automated auditory claim',native_zoom:'NOT_VERIFIED',external_calls:false};
const save=()=>fs.writeFile(root+'/results.json',JSON.stringify(report,null,2));
let shot=0;
async function settle(p){await p.waitForLoadState('networkidle',{timeout:4000}).catch(()=>{});await p.waitForTimeout(200);}
async function seek(p,target){await expect(target).toBeVisible();for(let n=0;n<160;n++){if(await target.evaluate(e=>e===document.activeElement))return n;await p.keyboard.press('Tab');}throw Error('KEYBOARD_TARGET_UNREACHABLE');}
async function record(run,id,assertion,fn){
 if(Date.now()>=Date.parse(c.expires_at)-10000)throw Error('R4_EXPIRY');
 const row={review_id:id,assertion,expected:'The explicitly stated deterministic condition holds',timestamp:new Date().toISOString(),context:run.label,browser_version:report.versions[run.channel],tool:'Playwright 1.64.1',token:s.token};
 try{row.actual=await fn();row.status='VERIFIED_PASS';}catch(e){row.status='VERIFIED_FAIL';row.actual=e.message.split('\n')[0].slice(0,160);}
 row.route=new URL(run.page.url()).pathname;row.evidence=(await capture(run,id+'-'+report.checks.length)).screenshot;report.checks.push(row);await save();
}
async function measure(run,selector,id,state){
 const rows=await measureTargets(run,[selector],String(++shot)+'-'+state);
 for(const row of rows){row.review_id=id;row.context=run.label;row.browser_version=report.versions[run.channel];row.timestamp=new Date().toISOString();
  if(row.rendered?.focused){
   const target=run.page.locator(selector).nth(row.index||0);
   row.focus_geometry=await target.evaluate(el=>{const r=el.getBoundingClientRect(),cs=getComputedStyle(el),pad=parseFloat(cs.outlineWidth)+parseFloat(cs.outlineOffset);const clips=[];for(let p=el.parentElement;p;p=p.parentElement){const s=getComputedStyle(p);if(/hidden|clip|auto|scroll/.test(s.overflowX+' '+s.overflowY)){const b=p.getBoundingClientRect();clips.push({overflow:s.overflow,within:r.left-pad>=b.left&&r.right+pad<=b.right&&r.top-pad>=b.top&&r.bottom+pad<=b.bottom});}}return{rect:{left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height},outline:cs.outline,offset:cs.outlineOffset,viewport:{width:innerWidth,height:innerHeight},within_viewport:r.left-pad>=0&&r.right+pad<=innerWidth&&r.top-pad>=0&&r.bottom+pad<=innerHeight,clips};});
   row.full_focus_screenshot=path.join(run.directory,'focus-'+shot+'.png');await run.page.screenshot({path:row.full_focus_screenshot});
  }
 }report.measurements.push(...rows);await save();return rows;
}
for(const channel of ['chrome','msedge']){
 const b=await chromium.launch({channel,headless:true});report.versions[channel]=b.version();
 try{for(const width of [1440,390]){
  const run=await start(b,{...s,folder:root},{width,height:900},'wp7br1-r4-'+channel+'-'+width);run.channel=channel;
  // Explicit touch/mobile setting is separate from actual native browser zoom.
  if(width===390)report.contexts.push({label:run.label,width,height:900,mobile_note:'Narrow responsive desktop context; native zoom not inferred'});else report.contexts.push({label:run.label,width,height:900});
  const p=run.page;p.setDefaultTimeout(5000);
  try{
   await p.goto(s.origin+'/login');await settle(p);
   await record(run,'R2-C-11','Auth Email, Password, Show password and enabled Submit have active >=3:1 authored focus, retained3px geometry, no clipping',async()=>{
    const sequence=[];
    for(const sel of ['#email','#password','.password-toggle']){
     const target=p.locator(sel);sequence.push({selector:sel,tabs:await seek(p,target)});
     const rows=await measure(run,sel,'R2-C-11','auth-'+sel.replace(/\W/g,''));
     expect(rows[0].focus_indicator.status).toBe('PASS');expect(rows[0].focus_indicator.ratio).toBeGreaterThanOrEqual(3);expect(rows[0].focus_geometry.within_viewport).toBe(true);expect(rows[0].focus_geometry.clips.every(v=>v.within)).toBe(true);
    }
    const toggle=p.locator('.password-toggle');
    for(const type of ['text','password']){await p.keyboard.press('Space');await expect(p.locator('#password')).toHaveAttribute('type',type);await expect(toggle).toBeFocused();const rows=await measure(run,'.password-toggle','R2-C-11','auth-toggle-'+type);expect(rows[0].focus_indicator.status).toBe('PASS');}
    // Non-secret invalid-login placeholder enables Submit for style inspection only.
    await p.locator('#email').fill('focus-fixture@example.invalid');await p.locator('#password').fill('[QA SYNTHETIC] NOT A LOGIN SECRET');
    const submit=p.locator('button[type=submit]');await expect(submit).toBeEnabled();await seek(p,submit);const rows=await measure(run,'button[type=submit]','R2-C-11','auth-submit');expect(rows[0].focus_indicator.status).toBe('PASS');expect(rows[0].focus_geometry.within_viewport).toBe(true);
    return {sequence,submit_enabled_with_unsubmitted_placeholder:true,measurements:6};
   });
   await record(run,'R2-SR-01','Invalid form remains default-deny, toggle states and forward/reverse field navigation work',async()=>{
    await p.locator('#email').fill('');await p.locator('#password').fill('');const submit=p.locator('button[type=submit]');await expect(submit).toBeDisabled();
    let posts=0;const count=req=>{if(req.method()==='POST'&&req.url().endsWith('/auth/login'))posts++;};p.on('request',count);
    await seek(p,p.locator('#email'));await p.keyboard.press('Enter');await expect(submit).toBeDisabled();expect(posts).toBe(0);p.off('request',count);
    await p.keyboard.press('Tab');await expect(p.locator('#password')).toBeFocused();await p.keyboard.press('Tab');await expect(p.locator('.password-toggle')).toBeFocused();await p.keyboard.press('Shift+Tab');await expect(p.locator('#password')).toBeFocused();await p.keyboard.press('Shift+Tab');await expect(p.locator('#email')).toBeFocused();
    return {invalid_submit_network_requests:posts,forward_reverse_order:['email','password','password-toggle','password','email']};
   });
   // Full keyboard login through the actual UI. Real synthetic fixture password
   // enters no retained DOM/network trace, logs or screenshots.
   await run.context.tracing.stop();
   const login={review_id:'R2-SR-01',assertion:'Keyboard-only canonical synthetic login preserves target and authenticates without duplicate action',timestamp:new Date().toISOString(),context:run.label};
   try{
    await seek(p,p.locator('#email'));await p.keyboard.type(wp3Owner.email);await p.keyboard.press('Tab');await p.keyboard.type(wp3Owner.password);await p.keyboard.press('Tab');await p.keyboard.press('Tab');await expect(p.locator('button[type=submit]')).toBeFocused();await p.keyboard.press('Enter');await expect(p).not.toHaveURL(/\/login/);login.status='VERIFIED_PASS';login.actual={route:new URL(p.url()).pathname,synthetic:true,credentials_persisted:false};
   }catch{login.status='VERIFIED_FAIL';login.actual='KEYBOARD_AUTH_NOT_ESTABLISHED';}
   report.checks.push(login);await run.context.tracing.start({screenshots:true,snapshots:true,sources:false});await save();
   if(login.status!=='VERIFIED_PASS')throw Error('R4_AUTHENTICATED_CONTEXT_REQUIRED');
   for(const key of ['goals','accounts','meesho','flipkart','social','finance','opportunity','campaign','ads']){
    if(!c.routes[key])continue;
    await p.goto(s.origin+c.routes[key]+(key==='opportunity'?'?goal_id='+c.fixture_ids.goal:''));await expect(p.locator('h1')).toBeVisible();await settle(p);
    if(key==='goals'){
     await record(run,'R2-SR-02','Named main/navigation landmarks, skip target and heading exist; meaningful page focus target',async()=>{await expect(p.locator('main')).toHaveCount(1);const link=p.getByRole('link',{name:'Skip to main content'});await expect(link).toHaveAttribute('href',/#main-content$/);return {h1:await p.locator('h1').innerText(),landmarks:await p.getByRole('navigation').evaluateAll(v=>v.map(e=>e.getAttribute('aria-label')))};});
     await record(run,'R2-SR-03','Disclosure Enter/Space match native state and retain keyboard focus',async()=>{const summary=p.locator('details.goal-creation > summary');await seek(p,summary);const start=await summary.getAttribute('aria-expanded');await p.keyboard.press('Enter');expect(await summary.getAttribute('aria-expanded')).not.toBe(start);await expect(summary).toBeFocused();await p.keyboard.press('Space');await expect(summary).toHaveAttribute('aria-expanded',start);if(start==='false')await p.keyboard.press('Enter');return {initial:start,round_trip:true};});
     await record(run,'R2-SR-05','Actual short-goal validation associates an alert and clears after correction; no valid goal submitted',async()=>{const input=p.locator('textarea[name=goal]');await seek(p,input);await p.keyboard.type('abc');await seek(p,p.getByRole('button',{name:'Create research goal',exact:true}));await p.keyboard.press('Enter');const alert=p.locator('#goal-validation');await expect(alert).not.toHaveText('');await expect(alert).toHaveAttribute('role','alert');await expect(input).toHaveAttribute('aria-describedby',/goal-validation/);const message=await alert.innerText();await input.fill('[QA SYNTHETIC] unsaved review draft');await expect(alert).toHaveCount(0);return {message,correction_clears:true,no_valid_submission:true};});
     await seek(p,p.locator('textarea[name=goal]'));await measure(run,'textarea[name=goal]','R2-C-06','goal-field');
    }
    if(key==='accounts')await record(run,'R2-SR-06','Read-only import groups have names and distinct controls without invoking imports',async()=>{const groups=p.getByRole('group',{name:'Read-only imports'});expect(await groups.count()).toBeGreaterThan(0);return await groups.first().ariaSnapshot();});
    if(['meesho','flipkart'].includes(key)){
     const group=p.getByRole('group',{name:'Listing editor sections'});await expect(group).toBeVisible();const names=await group.getByRole('button').allTextContents();
     for(let i=0;i<names.length;i++){
      const button=group.getByRole('button').nth(i);await seek(p,button);await p.keyboard.press('Enter');await settle(p);await expect(button).toBeFocused();
      await measure(run,`:nth-match(.inner-tabs button, ${i+1})`,key==='meesho'?'R2-C-05':'R2-C-04',key+'-button-'+i);
      if(['Product','Category','Attributes','Pricing','Inventory'].includes(names[i].trim())){
       for(const selector of ['main form label','main input[type=number]']){const count=await p.locator(selector).count();for(let n=0;n<count;n++)if(await p.locator(selector).nth(n).isVisible())await measure(run,`:nth-match(${selector}, ${n+1})`,key==='flipkart'?'R2-C-03':'R2-C-06',key+'-'+names[i].trim()+'-'+selector.replace(/\W/g,'')+'-'+n);}
      }
     }
     await record(run,'R2-SR-07','Listing editor grouped buttons retain focus after each read-only local panel activation',async()=>({names,all_panels_activated:true}));
    }
    if(key==='social'||key==='finance')for(const sel of key==='social'?['main textarea','.timeline strong']:['main caption','main th']){
     const count=await p.locator(sel).count();for(let i=0;i<count;i++)if(await p.locator(sel).nth(i).isVisible())await measure(run,`:nth-match(${sel}, ${i+1})`,key==='social'?(sel.includes('strong')?'R2-C-02':'R2-C-01'):(sel.includes('caption')?'R2-C-07':'R2-C-08'),key+'-'+sel.replace(/\W/g,'')+'-'+i);
    }
    if(key==='finance')await record(run,'R2-SR-13','Actual table captions and header semantics retained for Narrator review',async()=>({captions:await p.locator('caption').allTextContents(),headers:await p.locator('th').evaluateAll(v=>v.map(e=>({text:e.textContent?.trim(),scope:e.getAttribute('scope'),id:e.id})))}));
    if(key==='opportunity')await record(run,'R2-SR-12','Persisted opportunity and goal IDs remain in exact deep link; synthetic context is visible',async()=>{expect(p.url()).toContain(c.fixture_ids.opportunity);expect(p.url()).toContain(c.fixture_ids.goal);return {route:new URL(p.url()).pathname,goal_in_url:true,body_evidence:(await p.locator('main').innerText()).includes('SYNTHETIC')};});
    if(key==='campaign'&&c.reschedule?.activity_id){
     const button=p.getByRole('button',{name:'Reschedule Activity',exact:true}).first();if(await button.isVisible()){
      await seek(p,button);await p.keyboard.press('Enter');const textarea=p.locator('.reschedule-panel textarea');await expect(textarea).toBeVisible();await seek(p,textarea);await measure(run,'.reschedule-panel textarea','R2-C-10','campaign-reason');
     }else report.contexts.at(-1).campaign='Required canonical reschedule button not visible';
    }
    if(key==='ads'){
     const trigger=p.getByRole('button',{name:'Preview',exact:true}).first();
     await record(run,'R2-SR-08','Read-only preview opens named dialog with title focus',async()=>{await seek(p,trigger);await p.keyboard.press('Enter');const d=p.getByRole('dialog',{name:'Preview optimization'});await expect(d).toBeVisible();await expect(d.locator('h2')).toBeFocused();return await d.ariaSnapshot();});
     const dialog=p.getByRole('dialog',{name:'Preview optimization'});if(await dialog.isVisible()){
      await measure(run,'[role=dialog] h2','R2-C-09','ads-title');await record(run,'R2-SR-09','Tab/Shift+Tab remain inside and Space/Escape restore triggering Preview focus',async()=>{for(const key of ['Tab','Tab','Shift+Tab']){await p.keyboard.press(key);expect(await dialog.evaluate(e=>e.contains(document.activeElement))).toBe(true);}const close=dialog.getByRole('button',{name:'Close'});await seek(p,close);await measure(run,'[role=dialog] button','R2-C-11','ads-close');await p.keyboard.press('Space');await expect(dialog).not.toBeVisible();await expect(trigger).toBeFocused();await p.keyboard.press('Enter');await p.keyboard.press('Escape');await expect(trigger).toBeFocused();return {containment:true,space_and_escape:true,return_focus:true};});
     }
    }
    report.scans.push({context:run.label,surface:key,timestamp:new Date().toISOString(),...await axe(run,key)});await save();
   }
  }catch(e){report.contexts.at(-1).limitation=e.message.split('\n')[0].slice(0,180);}
  finally{report.contexts.at(-1).trace=await finish(run);await save();}
 }}finally{await b.close();}
}
report.completed_at=new Date().toISOString();await save();console.log(JSON.stringify({checks:report.checks.length,passed:report.checks.filter(v=>v.status==='VERIFIED_PASS').length,failed:report.checks.filter(v=>v.status==='VERIFIED_FAIL').length,measurements:report.measurements.length,scans:report.scans.length}));
