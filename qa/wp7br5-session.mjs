import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';
import {chromium,expect} from '@playwright/test';
import {inspect,root,authority} from './wp7br5-preflight.mjs';
import {start,capture,finish} from './seller-browser-explore.mjs';
import {fixtures} from './wp7br4-fixtures.mjs';
const readiness=JSON.parse(await fs.readFile(root+'/human-readiness.json','utf8'));
if(readiness.package!=='WP7B-R5'||readiness.observer_ready!==true)throw Error('R5_CURRENT_HUMAN_READINESS_REQUIRED');
const destination=root+'/session-control.json';
try{await fs.access(destination);throw Error('R5_EXISTING_SESSION_RECORD_REVIEW_REQUIRED');}catch(e){if(e.code!=='ENOENT')throw e;}
const pre=JSON.parse(await fs.readFile(root+'/preflight.json','utf8')),current=inspect();
if(current.instance_id!==pre.instance_id||current.container_id!==pre.container_id||!process.env.QA_DATABASE_ADMIN_URL||!process.env.QA_POSTGRES_INSTANCE_MANIFEST)throw Error('R5_EXACT_SIGNED_AUTHORITY_REQUIRED');
if(current.processes.frontend_watchers.length||current.processes.custom_reload_includes)throw Error('BLOCKED_PROCESS_INTERRUPTION_NOT_AUTHORIZED');
const spec=await fs.readFile(authority);if(crypto.createHash('sha256').update(spec).digest('hex')!==pre.authority_sha256)throw Error('R5_AUTHORITY_CHANGED');
const record={package:'WP7B-R5',status:'STARTING',at:new Date().toISOString(),preflight:current,authority_sha256:pre.authority_sha256,compatibility_engine:'Existing WP7BR1 startup/diagnostics and WP7A7 fixture contract; R5 authority only',human_observations:[],raw_output_persisted:false};
const save=()=>fs.writeFile(destination,JSON.stringify(record,null,2));await save();
const runtime=spawn(process.execPath,['qa/seller-browser-session.mjs'],{env:{...process.env,QA_PHASE:'2',QA_MIGRATE:'1',QA_BROWSER_PHASE:'WP7A7',QA_WORK_PACKAGE:'WP7BR1',QA_DATABASE_DROP_TIMEOUT_MS:'90000'},windowsHide:true,stdio:['pipe','pipe','pipe']});
record.runtime_pid=runtime.pid;await save();let s,buffer='',ended=false,browser,run;
runtime.stdout.on('data',d=>{buffer+=d;const lines=buffer.split(/\r?\n/);buffer=lines.pop();for(const line of lines)try{const v=JSON.parse(line);if(v.status==='READY'&&v.synthetic)s=v;}catch{}});
runtime.stderr.on('data',()=>{});runtime.on('error',()=>{ended=true;});
const done=new Promise(resolve=>runtime.on('exit',code=>{ended=true;resolve(code);})),delay=ms=>new Promise(r=>setTimeout(r,ms));
try{
 for(let n=0;n<900&&!s&&!ended;n++)await delay(400);if(!s)throw Error('R5_RUNTIME_NOT_READY');
 if(s.database_scope!==`vayujit_qa${s.token}_test`||!/^[a-f0-9]{16}$/.test(s.token))throw Error('R5_DATABASE_SCOPE_DENIED');
 record.session=s;const witness=await fetch(s.origin+'/__qa/witness').then(r=>r.json());if(!witness.disposable||witness.token!==s.token)throw Error('R5_WITNESS_REQUIRED');
 await fs.writeFile(s.folder+'/wp7br5-run.json',JSON.stringify({package:'WP7B-R5',token:s.token,synthetic:true,authority_sha256:pre.authority_sha256}));await save();
 browser=await chromium.launch({channel:'chrome',headless:false,args:['--window-position=80,50','--window-size=1400,950']});
 run=await start(browser,s,null,'wp7br1-r5-manual');await run.context.tracing.stop(); // Password-bearing setup not retained.
 const f=await fixtures(run,s);record.fixture_ids={goal:f.goal.id,opportunity:f.op.id,assessment:f.assessment.id,product:f.ops.product.id,meesho:f.meesho.id,flipkart:f.reviews.flip.id,social:f.reviews.social.id};record.reschedule=f.reschedule;
 record.routes={goals:'/intelligence/business-agent',accounts:'/marketplaces/accounts',meesho:`/marketplaces/listings/${f.meesho.id}/meesho`,flipkart:`/marketplaces/listings/${f.reviews.flip.id}/flipkart`,ads:'/ads/recommendations',finance:'/marketplaces/financials',social:`/social/posts/${f.reviews.social.id}`,opportunity:`/intelligence/product-opportunities/${f.op.id}`,catalog:`/catalog/${f.ops.product.id}`,campaign:f.reschedule.campaign_id?`/campaigns/${f.reschedule.campaign_id}`:null};
 await run.context.tracing.start({screenshots:true,snapshots:true,sources:false});
 await run.page.goto(s.origin+record.routes.goals);await expect(run.page.locator('h1')).toBeVisible();
 record.original_page_title=await run.page.title();await run.page.evaluate(token=>document.title+=' - WP7BR5 SYNTHETIC '+token,s.token);
 record.browser={name:'Chrome',version:browser.version(),title_tag_is_QA_only:true};record.status='READY_FOR_VERIFICATION';record.ready_at=new Date().toISOString();record.expires_at=new Date(Date.now()+60*60*1000).toISOString();
 record.screenshot=(await capture(run,'r5-synthetic-ready')).screenshot;await save();
 const handled=new Set();
 while(Date.now()<Date.parse(record.expires_at)&&!ended&&browser.isConnected()){
  const commands=await fs.readFile(root+'/manual-requests.json','utf8').then(JSON.parse).catch(()=>[]);let stop=false;
  for(const c of commands){if(!Number.isInteger(c.id)||handled.has(c.id))continue;handled.add(c.id);if(c.action==='done'){stop=true;break;}
   if(c.action==='navigate'&&record.routes[c.route]){await run.page.goto(s.origin+record.routes[c.route]);await expect(run.page.locator('h1')).toBeVisible();await run.page.evaluate(token=>document.title+=' - WP7BR5 SYNTHETIC '+token,s.token);}
   else if(c.action!=='capture')throw Error('R5_ALLOWLISTED_MANUAL_ACTION_REQUIRED');
   record.last_capture=(await capture(run,'manual-'+c.id)).screenshot;record.last_capture_at=new Date().toISOString();record.last_manual_metrics=await run.page.evaluate(()=>({viewport:{width:innerWidth,height:innerHeight},outer:{width:outerWidth,height:outerHeight},dpr:devicePixelRatio,document_width:document.documentElement.scrollWidth,active_tag:document.activeElement?.tagName,active_role:document.activeElement?.getAttribute('role')}));await save();
  }if(stop)break;await delay(500);
 }
}catch(e){record.status='BLOCKED';record.failure_code=/^R5_[A-Z_]+$/.test(e.message)?e.message:/^WP3_FIXTURE_[0-9]{3}_[a-z-]+$/.test(e.message)?e.message:'R5_PREPARATION_INCOMPLETE';record.source_line=e.stack?.match(/wp7br5-(?:session|fixtures)\.mjs:(\d+)/)?.[1]||null;}
finally{
 if(run)try{record.trace=await finish(run);}catch{record.evidence_close='INCOMPLETE';}
 if(browser)await browser.close().catch(()=>{record.browser_close='INCOMPLETE';});
 if(s)await fs.writeFile(s.folder+'/stop.request','WP7B-R5 session complete');else runtime.stdin.end();
 record.runtime_exit=await done;
 if(s)record.cleanup=await fs.readFile(s.folder+'/session-final.json','utf8').then(JSON.parse).catch(()=>null);
 record.ended_at=new Date().toISOString();if(record.status==='READY_FOR_VERIFICATION')record.status='ENDED_VERIFICATION_INCOMPLETE';await save();
}


