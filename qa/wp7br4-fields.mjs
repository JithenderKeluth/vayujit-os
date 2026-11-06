import fs from 'node:fs/promises';
import {chromium,expect} from '@playwright/test';
import {start,finish} from './seller-browser-explore.mjs';
import {measureTargets} from './wp7br1-contrast.mjs';
import {textFragments} from './wp7br4-text-fragments.mjs';
import {wp3Owner} from './wp3-fixtures.mjs';
const c=JSON.parse(await fs.readFile('tmp/qa-wp7br4/session-control.json','utf8')),s=c.session,root='tmp/qa-wp7br4/fields';
if(c.status!=='READY_FOR_VERIFICATION'||Date.now()>=Date.parse(c.expires_at)-10000)throw Error('VALID_R4_REQUIRED');
const w=await fetch(s.origin+'/__qa/witness').then(r=>r.json());if(!w.disposable||w.token!==s.token)throw Error('EXACT_R4_REQUIRED');
await fs.mkdir(root,{recursive:true});const report={package:'WP7B-R4',token:s.token,checks:[],fragments:[],measurements:[],contexts:[],method:'Original targets retained; actual text-range visibility instead of oversized enclosing label-box visibility'};
for(const channel of ['chrome','msedge']){
 const b=await chromium.launch({channel,headless:true});
 try{for(const width of [1440,390]){
  const run=await start(b,{...s,folder:root},{width,height:900},'wp7br1-'+channel+'-'+width),p=run.page;p.setDefaultTimeout(4000);const context={label:run.label,browser:b.version(),width,isMobile:width===390};
  try{
   await run.context.tracing.stop();const auth=await p.request.post(s.origin+'/api/v1/auth/login',{data:wp3Owner});if(!auth.ok())throw Error('SYNTHETIC_AUTH_FAILED');await run.context.tracing.start({screenshots:true,snapshots:true,sources:false});
   for(const route of ['flipkart','meesho','finance']){
    await p.goto(s.origin+c.routes[route]);await expect(p.locator('h1')).toBeVisible();await p.waitForLoadState('networkidle',{timeout:4000}).catch(()=>{});
    if(route==='finance')report.fragments.push(...(await textFragments(run,'main caption','finance-caption')).map(r=>({...r,review_id:'R2-C-07'})));
    else{
     report.fragments.push(...(await textFragments(run,':nth-match(main form label, 7)',route+'-label-6')).map(r=>({...r,review_id:route==='flipkart'?'R2-C-03':'R2-C-06'})));
     if(route==='meesho'){
      await p.locator('.inner-tabs button').getByText('Pricing',{exact:true}).click();await p.waitForTimeout(240);
      const input=p.locator('main input[type=number]').nth(2);await expect(input).toBeVisible();for(let i=0;i<180&&!await input.evaluate(e=>e===document.activeElement);i++)await p.keyboard.press('Tab');await expect(input).toBeFocused();
      const rows=await measureTargets(run,[':nth-match(main input[type=number], 3)'],'mobile-number-2');report.measurements.push(...rows.map(r=>({...r,review_id:'R2-C-06',context:run.label,timestamp:new Date().toISOString()})));
      report.checks.push({review_id:'R2-C-06',context:run.label,expected:'Exact third numeric input exposes text and authored keyboard focus >=3',actual:{text:rows[0].status,focus:rows[0].focus_indicator.status},status:rows[0].status==='PASS'&&rows[0].focus_indicator.status==='PASS'?'VERIFIED_PASS':'NOT_VERIFIED',timestamp:new Date().toISOString()});
     }
    }
    await fs.writeFile(root+'/results.json',JSON.stringify(report,null,2));
   }
  }catch(e){context.limitation=e.message.split('\n')[0].slice(0,160);}
  finally{context.trace=await finish(run);report.contexts.push(context);await fs.writeFile(root+'/results.json',JSON.stringify(report,null,2));}
 }}finally{await b.close();}
}
report.completed_at=new Date().toISOString();await fs.writeFile(root+'/results.json',JSON.stringify(report,null,2));console.log(JSON.stringify({fragments:report.fragments.length,measurements:report.measurements.length,checks:report.checks.length,contexts:report.contexts.length}));
