import fs from 'node:fs/promises';
import {chromium,expect} from '@playwright/test';
import {start,finish} from './seller-browser-explore.mjs';
import {measureTargets} from './wp7br1-contrast.mjs';
import {wp3Owner} from './wp3-fixtures.mjs';
const c=JSON.parse(await fs.readFile('tmp/qa-wp7br4/session-control.json','utf8')),s=c.session,root='tmp/qa-wp7br4/auth-states';
if(c.status!=='READY_FOR_VERIFICATION'||Date.now()>=Date.parse(c.expires_at)-10000)throw Error('VALID_R4_REQUIRED');
const w=await fetch(s.origin+'/__qa/witness').then(r=>r.json());if(w.token!==s.token||!w.disposable)throw Error('EXACT_R4_REQUIRED');
await fs.mkdir(root,{recursive:true});const report={package:'WP7B-R4',token:s.token,checks:[],measurements:[],contexts:[]};
for(const channel of ['chrome','msedge']){
 const b=await chromium.launch({channel,headless:true});
 try{for(const width of [1440,390]){
  // Exact inherited label contract enables isMobile+hasTouch at390.
  const run=await start(b,{...s,folder:root},{width,height:900},'wp7br1-'+channel+'-'+width),p=run.page;p.setDefaultTimeout(6000);
  const row={review_id:'R2-C-11',channel,version:b.version(),width,height:900,isMobile:width===390,hasTouch:width===390,timestamp:new Date().toISOString(),assertion:'Authentic rejected-login error, keyboard focus/hover, stable layout offsets and disabled Submit protection',expected:'401 remains rejected; visible error and focus contrast >=3; no focus clipping introduced; disabled Submit not focusable'};
  try{
   await run.context.tracing.stop();await p.goto(s.origin+'/login');await p.locator('#email').fill(wp3Owner.email);await p.locator('#password').fill('[QA SYNTHETIC] INVALID PASSWORD');
   const response=p.waitForResponse(r=>r.url().endsWith('/auth/login')&&r.request().method()==='POST');await p.locator('button[type=submit]').press('Enter');expect((await response).status()).toBe(401);await expect(p.getByRole('alert')).toHaveText('Invalid email or password.');
   await p.locator('#password').fill('');await run.context.tracing.start({screenshots:true,snapshots:true,sources:false});
   const samples=[];
   for(const sel of ['#email','#password','.password-toggle']){
    const target=p.locator(sel);for(let n=0;n<40&&!await target.evaluate(e=>e===document.activeElement);n++)await p.keyboard.press('Tab');await expect(target).toBeFocused();
    const rows=await measureTargets(run,[sel],'error-'+sel.replace(/\W/g,''));for(const r of rows){r.context=run.label;r.review_id='R2-C-11';r.timestamp=new Date().toISOString();}samples.push(...rows);expect(rows[0].focus_indicator.status).toBe('PASS');
   }
   const toggle=p.locator('.password-toggle');const before=await toggle.evaluate(e=>({left:e.offsetLeft,top:e.offsetTop,width:e.offsetWidth,height:e.offsetHeight}));await toggle.hover();const hovered=await measureTargets(run,['.password-toggle'],'hover');expect(hovered[0].focus_indicator.status).toBe('PASS');const after=await toggle.evaluate(e=>({left:e.offsetLeft,top:e.offsetTop,width:e.offsetWidth,height:e.offsetHeight}));expect(after).toEqual(before);
   report.measurements.push(...samples,...hovered.map(r=>({...r,context:run.label,review_id:'R2-C-11',timestamp:new Date().toISOString()})));
   await expect(p.locator('button[type=submit]')).toBeDisabled();await p.keyboard.press('Tab');expect(await p.locator('button[type=submit]').evaluate(e=>e===document.activeElement)).toBe(false);
   row.actual={server_status:401,error:'Invalid email or password.',layout_before:before,layout_after:after,disabled_submit_skipped:true,focus_ratios:[...samples,...hovered].map(r=>r.focus_indicator.ratio)};row.status='VERIFIED_PASS';row.screenshot=run.directory+'/error-and-hover.png';await p.screenshot({path:row.screenshot});
   // Normal successful synthetic authentication clears its canonical rate counter;
   // no direct state reset or disabled rate-limit control. Password not traced.
   await run.context.tracing.stop();const good=await p.request.post(s.origin+'/api/v1/auth/login',{data:wp3Owner});expect(good.status()).toBe(200);await run.context.tracing.start({screenshots:true,snapshots:true,sources:false});
  }catch(e){row.status='VERIFIED_FAIL';row.actual=e.message.split('\n')[0].slice(0,160);}
  finally{report.checks.push(row);report.contexts.push({context:run.label,...await finish(run)});await fs.writeFile(root+'/results.json',JSON.stringify(report,null,2));}
 }}finally{await b.close();}
}
console.log(JSON.stringify({checks:report.checks.length,passed:report.checks.filter(r=>r.status==='VERIFIED_PASS').length,failed:report.checks.filter(r=>r.status==='VERIFIED_FAIL').length}));
