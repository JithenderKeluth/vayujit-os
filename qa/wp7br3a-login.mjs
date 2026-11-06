import fs from 'node:fs/promises';
import {chromium,expect} from '@playwright/test';
const r=JSON.parse(await fs.readFile('tmp/qa-wp7br3/session-control.json','utf8'));
if(r.status!=='AWAITING_HUMAN_OBSERVATION'||Date.now()>=Date.parse(r.expires_at)-10000)throw Error('CURRENT_R3_REQUIRED');
const witness=await fetch(r.session.origin+'/__qa/witness').then(v=>v.json());
if(!witness.disposable||witness.token!==r.session.token)throw Error('OWNED_R3_REQUIRED');
const report={token:r.session.token,checks:[],speech:false,new_lifecycle_operations:0};
for(const channel of ['chrome','msedge']){
 const b=await chromium.launch({channel,headless:true});
 try{for(const width of [1440,390]){
  if(Date.now()>=Date.parse(r.expires_at)-10000)break;
  const c=await b.newContext({viewport:{width,height:900},isMobile:width===390,hasTouch:width===390,serviceWorkers:'block'});
  await c.route('**/*',route=>new URL(route.request().url()).origin===r.session.origin&&route.request().method()==='GET'?route.continue():route.abort());
  const p=await c.newPage();p.setDefaultTimeout(2000);
  const row={review_id:'R2-SR-01',channel,version:b.version(),width,timestamp:new Date().toISOString(),assertion:'Keyboard Email → Password → show/hide control, both Space states and actual focus persistence',expected:'Logical field sequence, toggle changes password type and retains control focus',steps:[]};
  try{
   await p.goto(r.session.origin+'/login');const email=p.getByRole('textbox',{name:'Email',exact:true}),password=p.locator('#password');
   await expect(email).toBeVisible();await email.focus();
   row.steps.push(await p.evaluate(()=>({id:document.activeElement.id,tag:document.activeElement.tagName})));
   await p.keyboard.press('Tab');await expect(password).toBeFocused();row.steps.push({id:'password'});
   await p.keyboard.press('Tab');
   // Name changes Show→Hide. Resolve the current focused button, never the old-name locator.
   const toggle=p.locator('button').filter({hasText:/password/i});await expect(toggle).toBeFocused();
   for(const expected of ['text','password']){
    await p.keyboard.press('Space');await expect(password).toHaveAttribute('type',expected);await expect(toggle).toBeFocused();
    row.steps.push(await toggle.evaluate(e=>({name:e.textContent.trim(),pressed:e.getAttribute('aria-pressed'),focused:e===document.activeElement,outline:getComputedStyle(e).outline,rect:{width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}})));
   }
   await p.keyboard.press('Shift+Tab');await expect(password).toBeFocused();await p.keyboard.press('Shift+Tab');await expect(email).toBeFocused();
   row.status='VERIFIED_PASS';row.actual={forward_and_reverse_order:true,both_states_and_focus:true};
  }catch(e){row.status='VERIFIED_FAIL';row.actual={safe_message:e.message.split('\n')[0],focus:await p.evaluate(()=>({id:document.activeElement?.id,tag:document.activeElement?.tagName,text:document.activeElement?.tagName==='BUTTON'?document.activeElement.textContent:null})).catch(()=>null)};}
  row.semantics=await p.locator('main').ariaSnapshot();row.screenshot=`tmp/qa-wp7br3a/login-${channel}-${width}.png`;await p.screenshot({path:row.screenshot});report.checks.push(row);await c.close();
 }}finally{await b.close();}
}
report.completed_at=new Date().toISOString();await fs.writeFile('tmp/qa-wp7br3a/login-retest.json',JSON.stringify(report,null,2));console.log(JSON.stringify({checks:report.checks.length,passed:report.checks.filter(v=>v.status==='VERIFIED_PASS').length,failed:report.checks.filter(v=>v.status==='VERIFIED_FAIL').length}));
