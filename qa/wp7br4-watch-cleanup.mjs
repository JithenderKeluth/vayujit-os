// Bounded read-only independent audit after the existing R4 lifecycle finishes.
// Never extends a session, creates/drops a database, kills a process or recovers a lock.
import fs from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {inspect} from './wp7br4-preflight.mjs';
const root='tmp/qa-wp7br4';
let current=JSON.parse(await fs.readFile(root+'/session-control.json','utf8'));
const token=current.session.token;
if(current.package!=='WP7B-R4'||!/^[a-f0-9]{16}$/.test(token))throw Error('R4_OWNED_RECEIPT_REQUIRED');
const deadline=Date.parse(current.expires_at)+180000;
await fs.writeFile(root+'/cleanup-watcher.json',JSON.stringify({pid:process.pid,token,read_only:true,deadline:new Date(deadline).toISOString(),started_at:new Date().toISOString()}));
while(!current.ended_at&&Date.now()<deadline){await new Promise(r=>setTimeout(r,1000));current=JSON.parse(await fs.readFile(root+'/session-control.json','utf8'));}
const audit={package:'WP7B-R4',token,at:new Date().toISOString(),lifecycle_mutations:0,process_control:0,raw_output_persisted:false};
try{
 const code=String.raw`
import json,sys
from sqlalchemy import text
from qa.postgres_instance import QaInstance,database_name
i=QaInstance();i.verify_server();state=i.load(sys.argv[1]);e=i.engine()
try:
 with e.connect() as c: absent=c.scalar(text('select count(*) from pg_database where datname=:name'),{'name':database_name(sys.argv[1])})==0
finally:e.dispose()
print(json.dumps({'database_absent':absent,'signed_state':state['state'],'instance_id':i.manifest['instance_id'],'endpoint':'127.0.0.1:55432','role':'vayujit_qa_admin'}))
`;
 const result=spawnSync('apps/api/.venv/Scripts/python.exe',['-c',code,token],{encoding:'utf8',windowsHide:true,timeout:60000});
 if(result.status!==0)throw Error('R4_INDEPENDENT_ABSENCE_NOT_ESTABLISHED');
 Object.assign(audit,JSON.parse(result.stdout.trim()));
 const before=JSON.parse(await fs.readFile(root+'/preflight.json','utf8')),now=inspect(),sort=rows=>rows.slice().sort((a,b)=>a.pid-b.pid);
 audit.api_worker_tree_unchanged=JSON.stringify(sort(before.processes.api_processes))===JSON.stringify(sort(now.processes.api_processes));
 audit.original_containers_unchanged=JSON.stringify(before.containers)===JSON.stringify(now.containers);
 audit.status=current.ended_at&&audit.database_absent&&audit.signed_state==='DROPPED'&&audit.api_worker_tree_unchanged&&audit.original_containers_unchanged?'PASS':'INCOMPLETE';
}catch{audit.status='INCOMPLETE';audit.safe_code='R4_INDEPENDENT_FINAL_AUDIT_NOT_ESTABLISHED';}
await fs.writeFile(root+'/final-cleanup-audit.json',JSON.stringify(audit,null,2));
// Refresh evidence-only reports; no new runtime or functional action is launched.
spawnSync(process.execPath,['qa/wp7br4-report.mjs'],{windowsHide:true,stdio:'ignore',timeout:60000});
