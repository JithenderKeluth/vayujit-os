import fs from 'node:fs/promises';
import {chromium,expect} from '@playwright/test';
import {start,finish} from './seller-browser-explore.mjs';
import {measureTargets} from './wp7br1-contrast.mjs';
import {wp3Owner} from './wp3-fixtures.mjs';
const c=JSON.parse(await fs.readFile('tmp/qa-wp7br3/session-control.json','utf8')),s=c.session,deadline=Date.parse(c.expires_at)-10000;
if(c.status!=='AWAITING_HUMAN_OBSERVATION'||Date.now()>=deadline)throw Error('VALID_R3_REQUIRED');
const witness=await fetch(s.origin+'/__qa/witness').then(r=>r.json());if(!witness.disposable||witness.token!==s.token)throw Error('EXACT_WITNESS_REQUIRED');
const report={token:s.token,started_at:new Date().toISOString(),rows:[],contexts:[],limitations:[]};
for(const channel of ['chrome','msedge']){
 if(Date.now()>=deadline)break;const b=await chromium.launch({channel,headless:true});
 try{for(const width of [1440,390]){
  if(Date.now()>=deadline)break;const run=await start(b,{...s,folder:'tmp/qa-wp7br3a'},{width,height:900},'wp7br1-r3a-extra-'+channel+'-'+width),p=run.page;p.setDefaultTimeout(2000);
  try{
   await run.context.tracing.stop();const auth=await p.request.post(s.origin+'/api/v1/auth/login',{data:wp3Owner});if(!auth.ok())throw Error('SYNTHETIC_LOGIN_FAILED');await run.context.tracing.start({screenshots:true,snapshots:true,sources:false});
   for(const [route,selectors] of [['social',['main textarea','.timeline strong']],['flipkart',['.inner-tabs button','main form label']],['finance',['main caption','main th']]]){
    if(Date.now()>=deadline)break;await p.goto(s.origin+c.routes[route]);await expect(p.locator('h1')).toBeVisible();await p.waitForLoadState('networkidle',{timeout:3000}).catch(()=>{});
    for(const sel of selectors){const count=await p.locator(sel).count();const first=route==='flipkart'?(sel.includes('button')?8:8):0;
     if(!count)report.limitations.push({channel,width,route,selector:sel,reason:'TARGET_ABSENT'});
     for(let i=first;i<count&&Date.now()<deadline;i++){
      if(!await p.locator(sel).nth(i).isVisible())continue;
      try{const rows=await measureTargets(run,[`:nth-match(${sel}, ${i+1})`],route+'-'+i+'-'+report.rows.length);report.rows.push(...rows.map(row=>({...row,channel,browser_version:b.version(),width,original_selector:sel,original_index:i,route_key:route,timestamp:new Date().toISOString()})));}
      catch{report.limitations.push({channel,width,route,selector:sel,index:i,reason:'UNSTABLE_RENDER_TARGET'});}
     }
    }
   }
  }catch{report.limitations.push({channel,width,reason:'BOUNDED_RENDER_REVIEW_INCOMPLETE'});}
  finally{report.contexts.push({channel,version:b.version(),width,...await finish(run)});await fs.writeFile('tmp/qa-wp7br3a/remaining-contrast.json',JSON.stringify(report,null,2));}
 }}finally{await b.close();}
}
report.completed_at=new Date().toISOString();await fs.writeFile('tmp/qa-wp7br3a/remaining-contrast.json',JSON.stringify(report,null,2));console.log(JSON.stringify({rows:report.rows.length,contexts:report.contexts.length,limitations:report.limitations.length}));
