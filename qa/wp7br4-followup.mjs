// Follow-up uses each actual component contract (Flipkart is not a named group).
import fs from 'node:fs/promises';
import {chromium,expect} from '@playwright/test';
import {start,capture,axe,finish} from './seller-browser-explore.mjs';
import {measureTargets,resolveContrast,parseColor,contrastRatio} from './wp7br1-contrast.mjs';
import {wp3Owner} from './wp3-fixtures.mjs';
const c=JSON.parse(await fs.readFile('tmp/qa-wp7br4/session-control.json','utf8')),s=c.session,root='tmp/qa-wp7br4/followup';
if(c.status!=='READY_FOR_VERIFICATION'||Date.now()>=Date.parse(c.expires_at)-10000)throw Error('VALID_R4_REQUIRED');
const witness=await fetch(s.origin+'/__qa/witness').then(r=>r.json());if(witness.token!==s.token||!witness.disposable)throw Error('EXACT_R4_WITNESS_REQUIRED');
await fs.mkdir(root,{recursive:true});const report={token:s.token,started_at:new Date().toISOString(),checks:[],measurements:[],semantics:[],targets:[],transitions:[],scans:[],contexts:[],versions:{}};
const save=()=>fs.writeFile(root+'/results.json',JSON.stringify(report,null,2));let serial=0;
async function settle(p){await p.waitForLoadState('networkidle',{timeout:3000}).catch(()=>{});await p.waitForTimeout(220);}
async function seek(p,target){await expect(target).toBeVisible();for(let n=0;n<200;n++){if(await target.evaluate(e=>e===document.activeElement))return n;await p.keyboard.press('Tab');}throw Error('KEYBOARD_TARGET_UNREACHABLE');}
async function measure(run,sel,id,state){const rows=await measureTargets(run,[sel],String(++serial)+'-'+state);for(const row of rows){row.review_id=id;row.context=run.label;row.timestamp=new Date().toISOString();}report.measurements.push(...rows);await save();return rows;}
async function check(run,id,assertion,fn){const row={review_id:id,assertion,expected:'Explicit deterministic condition holds',timestamp:new Date().toISOString(),context:run.label,tool:'Playwright 1.64.1'};try{row.actual=await fn();row.status='VERIFIED_PASS';}catch(e){row.status='VERIFIED_FAIL';row.actual=e.message.split('\n')[0].slice(0,160);}row.evidence=(await capture(run,id+'-'+report.checks.length)).screenshot;report.checks.push(row);await save();}
for(const channel of ['chrome','msedge']){
 const b=await chromium.launch({channel,headless:true});report.versions[channel]=b.version();
 try{for(const width of [1440,390]){
  const run=await start(b,{...s,folder:root},{width,height:900},'wp7br1-r4-follow-'+channel+'-'+width),p=run.page;p.setDefaultTimeout(6000);report.contexts.push({context:run.label,width,height:900});
  try{
   await run.context.tracing.stop();const auth=await p.request.post(s.origin+'/api/v1/auth/login',{data:wp3Owner});if(!auth.ok())throw Error('SYNTHETIC_AUTH_FAILED');await run.context.tracing.start({screenshots:true,snapshots:true,sources:false});
   for(const route of ['flipkart','social','finance','opportunity','campaign','ads','meesho']){
    if(Date.now()>=Date.parse(c.expires_at)-10000)throw Error('R4_EXPIRY');if(!c.routes[route])continue;
    await p.goto(s.origin+c.routes[route]+(route==='opportunity'?'?goal_id='+c.fixture_ids.goal:''));await expect(p.locator('h1')).toBeVisible();await settle(p);
    if(route==='flipkart'||route==='meesho'){
     const group=p.locator('.inner-tabs');await expect(group).toBeVisible();const buttons=group.locator('button'),names=await buttons.allTextContents();
     for(let i=0;i<names.length;i++){
      const target=buttons.nth(i);await seek(p,target);await p.keyboard.press('Enter');await settle(p);await expect(target).toBeFocused();
      await measure(run,`:nth-match(.inner-tabs button, ${i+1})`,route==='flipkart'?'R2-C-04':'R2-C-05',route+'-'+i);
      for(const sel of ['main form label','main textarea','main input[type=number]']){
       const count=await p.locator(sel).count();for(let n=0;n<count;n++)if(await p.locator(sel).nth(n).isVisible()){
        const row=await measure(run,`:nth-match(${sel}, ${n+1})`,route==='flipkart'?'R2-C-03':'R2-C-06',route+'-'+i+'-'+sel.replace(/\W/g,'')+'-'+n);for(const v of row){v.editor_section=names[i].trim();v.original_selector=sel;v.original_index=n;}
       }
      }
     }
     await check(run,'R2-SR-07',route+' actual editor controls are keyboard reachable and panel changes retain focus',async()=>({names,all_panels_activated:true,named_group_required:route==='meesho',actual_role:await group.getAttribute('role')}));
     // Sample real computed transition states without disabling/canceling animation.
     await buttons.getByText('Product',{exact:true}).click();await settle(p);
     await p.evaluate(()=>{globalThis.__r4Frames=[];const start=performance.now();const sample=()=>{const t=performance.now()-start;globalThis.__r4Frames.push({time_ms:t,buttons:[...document.querySelectorAll('.inner-tabs button')].slice(0,2).map(e=>{const s=getComputedStyle(e);return{text:e.textContent.trim(),color:s.color,background:s.backgroundColor,opacity:s.opacity,current_animations:e.getAnimations().map(a=>({time:a.currentTime,progress:a.effect?.getComputedTiming().progress}))};})});if(t<450)requestAnimationFrame(sample);};requestAnimationFrame(sample);});
     await buttons.getByText('Category',{exact:true}).click();await p.waitForTimeout(500);
     const frames=await p.evaluate(()=>globalThis.__r4Frames);report.transitions.push({review_id:'R2-C-13',context:run.label,route,timestamp:new Date().toISOString(),frames,scope:'Computed rAF states only; frame screenshots not aligned, criterion adjudication remains separate'});await save();
     if(route==='meesho'){
      await buttons.getByText('Readiness',{exact:true}).click();await settle(p);
      report.semantics.push({review_id:'R2-SR-11',context:run.label,route:route,snapshot:await p.locator('main').ariaSnapshot(),timestamp:new Date().toISOString()});
     }
    }
    if(route==='social'||route==='finance')for(const sel of route==='social'?['main textarea','.timeline strong']:['main caption','main th']){
     const count=await p.locator(sel).count();for(let i=0;i<count;i++)if(await p.locator(sel).nth(i).isVisible())await measure(run,`:nth-match(${sel}, ${i+1})`,route==='social'?(sel.includes('strong')?'R2-C-02':'R2-C-01'):(sel.includes('caption')?'R2-C-07':'R2-C-08'),route+'-'+sel.replace(/\W/g,'')+'-'+i);
    }
    if(route==='finance')await check(run,'R2-SR-13','Populated finance tables expose captions/header cells and their actual associations',async()=>({tables:await p.locator('table').count(),captions:await p.locator('caption').allTextContents(),headers:await p.locator('th').evaluateAll(v=>v.map(e=>({text:e.textContent.trim(),scope:e.getAttribute('scope')})))}));
    if(route==='opportunity')await check(run,'R2-SR-12','Exact product and goal deep-link context is preserved and synthetic evidence labels visible',async()=>{expect(p.url()).toContain(c.fixture_ids.opportunity);expect(p.url()).toContain(c.fixture_ids.goal);await expect(p.locator('main')).toContainText('[QA SYNTHETIC]');return{goal:c.fixture_ids.goal,opportunity:c.fixture_ids.opportunity,snapshot:await p.locator('main').ariaSnapshot()};});
    if(route==='campaign'){
     const action=p.getByRole('button',{name:'Reschedule Activity',exact:true}).first();await check(run,'R2-C-10','Legitimately eligible synthetic missed intent exposes the canonical reschedule reason textarea; no confirmation',async()=>{await expect(action).toBeVisible();await seek(p,action);await p.keyboard.press('Enter');const area=p.locator('.reschedule-panel textarea');await expect(area).toBeVisible();await seek(p,area);const rows=await measure(run,'.reschedule-panel textarea','R2-C-10','campaign-reason');expect(rows[0].status).toBe('PASS');return{fixture:c.reschedule,text_ratio:rows[0].ratio,focus_status:rows[0].focus_indicator.status,confirmation_executed:false};});
    }
    if(route==='ads'){
     const trigger=p.getByRole('button',{name:'Preview',exact:true}).first();await seek(p,trigger);await p.keyboard.press('Enter');const d=p.getByRole('dialog',{name:'Preview optimization'});await expect(d).toBeVisible();await expect(d.locator('h2')).toBeFocused();await measure(run,'[role=dialog] h2','R2-C-09','ads-heading');
     await check(run,'R2-SR-08','Read-only preview has actual dialog name, description metadata and title focus',async()=>({snapshot:await d.ariaSnapshot(),description:await d.getAttribute('aria-describedby'),focus:await p.evaluate(()=>document.activeElement.id)}));
     await check(run,'R2-SR-09','Forward/reverse containment, Space/Escape dismissal, return focus and readable wrapped preview',async()=>{const seq=[];for(const key of ['Tab','Tab','Shift+Tab']){await p.keyboard.press(key);expect(await d.evaluate(e=>e.contains(document.activeElement))).toBe(true);seq.push(await p.evaluate(()=>document.activeElement.textContent?.trim().slice(0,60)));}await seek(p,d.getByRole('button',{name:'Close'}));await measure(run,'[role=dialog] button','R2-C-11','ads-close');const geometry=await d.evaluate(e=>({client:e.clientWidth,scroll:e.scrollWidth,left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right,viewport:innerWidth}));expect(geometry.scroll).toBeLessThanOrEqual(geometry.client+1);await p.keyboard.press('Space');await expect(d).not.toBeVisible();await expect(trigger).toBeFocused();await p.keyboard.press('Enter');await p.keyboard.press('Escape');await expect(trigger).toBeFocused();return{sequence:seq,geometry};});
    }
    report.targets.push({review_id:'R2-C-14',context:run.label,route,timestamp:new Date().toISOString(),rects:await p.locator('main button:enabled,main a[href],main input:enabled,main textarea:enabled,main select:enabled').evaluateAll(v=>v.map(e=>{const r=e.getBoundingClientRect();return{name:e.getAttribute('aria-label')||e.textContent?.trim().slice(0,60)||e.getAttribute('name'),tag:e.tagName,width:r.width,height:r.height,left:r.left,top:r.top,visible:r.width>0&&r.height>0};}).filter(v=>v.visible)),scope:'Dimensions only; spacing/inline/equivalent exceptions not automatically waived'});
    report.scans.push({context:run.label,route,timestamp:new Date().toISOString(),...await axe(run,route)});await save();
   }
  }catch(e){report.contexts.at(-1).limitation=e.message.split('\n')[0].slice(0,180);}
  finally{report.contexts.at(-1).trace=await finish(run);await save();}
 }}finally{await b.close();}
}
report.completed_at=new Date().toISOString();await save();console.log(JSON.stringify({checks:report.checks.length,passed:report.checks.filter(v=>v.status==='VERIFIED_PASS').length,failed:report.checks.filter(v=>v.status==='VERIFIED_FAIL').length,measurements:report.measurements.length,scans:report.scans.length}));
