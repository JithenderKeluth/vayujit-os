// Health-only verification after the approved existing process resume wrapper.
import fs from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
const approval=JSON.parse(await fs.readFile('tmp/qa-wp7br1/owner-authorization.json','utf8'));
const state=JSON.parse(await fs.readFile('tmp/qa-wp7br1/app-window.json','utf8'));
if(!approval.development_process_pause_approval || !state.restored)throw Error('RECORDED_R1_RESUME_REQUIRED');
const preflight=spawnSync('apps/api/.venv/Scripts/python.exe',['scripts/wp7a7-resume-preflight.py'],{encoding:'utf8',windowsHide:true,timeout:30000});
let proof=null;try{proof=JSON.parse((preflight.stdout||'').trim().split(/\r?\n/).at(-1));}catch{/* no raw output */}
if(preflight.status!==0 || proof?.status!=='PASS' || proof.incomplete_campaign_waits!==0)throw Error('READ_ONLY_RESTORATION_CHECK_BLOCKED');
const targets=[['frontend','http://127.0.0.1:4200/'],['api_health','http://127.0.0.1:8000/health'],['api_liveness','http://127.0.0.1:8000/health/live'],['api_readiness','http://127.0.0.1:8000/health/ready']];
const results=new Map(),began=Date.now();
while(Date.now()-began<90000 && results.size<targets.length){
 for(const[id,url]of targets){if(results.has(id))continue;try{const r=await fetch(url,{signal:AbortSignal.timeout(2000)});if(!r.ok)continue;const data=id==='frontend'?await r.text():await r.json();const valid=id==='frontend'?data.includes('<app-root'):id==='api_readiness'?Array.isArray(data?.components):data?.service==='vayujit-api' && data?.status===(id==='api_liveness'?'alive':'ok');if(valid)results.set(id,{id,http_status:r.status,body_valid:true});}catch{/* no raw connection/process output */}}
 if(results.size<targets.length)await new Promise(r=>setTimeout(r,500));
}
const record={package:'WP7B-R1',status:results.size===targets.length?'PASS':'BLOCKED',recorded_resume_token:state.token,checks:targets.map(([id])=>results.get(id)||{id,status:'NOT_VERIFIED'}),post_resume_read_only_startup_check:proof,checked_at:new Date().toISOString(),health_only:true,raw_output_persisted:false};
await fs.writeFile('tmp/qa-wp7br1/process-restoration.json',JSON.stringify(record,null,2));console.log(JSON.stringify(record));process.exitCode=record.status==='PASS'?0:1;
