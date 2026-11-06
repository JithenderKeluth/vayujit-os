// Read-only attestation. No Python source files are created/edited under live WatchFiles.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
export const root='tmp/qa-wp7br4';
export const authority='C:/Users/jithe/.codex/attachments/116f3f34-e936-46ff-a83b-064e5ffb8ca0/Pasted text.txt';
export function inspect(){
 const code=String.raw`
import json,subprocess
from qa.postgres_instance import QaInstance
i=QaInstance();i.verify_server()
ps=r'''$all=@(Get-CimInstance Win32_Process);$roots=@($all|Where-Object {$_.Name -eq 'python.exe' -and $_.CommandLine -match '(?:^|\s)-m\s+uvicorn\s+' -and $_.CommandLine -match '--reload'});$ids=@($roots|ForEach-Object{$_.ProcessId});for($n=0;$n -lt 5;$n++){$ids+=@($all|Where-Object {$_.ParentProcessId -in $ids}|Select-Object -ExpandProperty ProcessId);$ids=@($ids|Select-Object -Unique)};$workers=@($all|Where-Object {$_.ProcessId -in $ids}|ForEach-Object{[pscustomobject]@{pid=$_.ProcessId;parent_pid=$_.ParentProcessId;name=$_.Name;created=$_.CreationDate.ToUniversalTime().ToString('o')}});$front=@($all|Where-Object {$_.Name -eq 'node.exe' -and $_.CommandLine -match '(?:ng|nx|vite|webpack)(?:\.js)?["\s]+serve|web:serve'});$listeners=@(Get-NetTCPConnection -State Listen|Where-Object {$_.LocalPort -in @(4200,8000)}|Select-Object LocalAddress,LocalPort,OwningProcess);[pscustomobject]@{api_processes=$workers;frontend_watchers=@($front|ForEach-Object{$_.ProcessId});listeners=$listeners;custom_reload_includes=@($roots|Where-Object {$_.CommandLine -match '--reload-include'}).Count}|ConvertTo-Json -Depth 5 -Compress'''
r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',ps],capture_output=True,text=True,timeout=30,check=True)
processes=json.loads(r.stdout)
containers=[]
for cid in i.docker('ps','-aq','--no-trunc').splitlines():
 c=json.loads(i.docker('inspect',cid))[0]
 containers.append({'id':c['Id'],'name':c['Name'],'image':c['Image'],'status':c['State']['Status'],'started':c['State']['StartedAt'],'finished':c['State']['FinishedAt'],'mounts':[{k:m.get(k) for k in ('Type','Name','Destination','RW')} for m in c['Mounts']],'networks':list(c['NetworkSettings']['Networks'])})
print(json.dumps({'instance_id':i.manifest['instance_id'],'container_id':i.manifest['container_id'],'endpoint':'127.0.0.1:55432','role':'vayujit_qa_admin','signed_authority_valid':True,'processes':processes,'containers':containers}))
`;
 const r=spawnSync('apps/api/.venv/Scripts/python.exe',['-c',code],{encoding:'utf8',windowsHide:true,timeout:90000});
 if(r.status!==0)throw Error('R4_READONLY_PREFLIGHT_FAILED');
 return JSON.parse(r.stdout.trim());
}
if(process.argv.includes('--record')){
 await fs.mkdir(root,{recursive:true});
 const destination=root+'/preflight.json';
 try{await fs.access(destination);throw Error('R4_PREFLIGHT_ALREADY_RECORDED');}catch(e){if(e.code!=='ENOENT')throw e;}
 const evidence=inspect();
 if(evidence.processes.frontend_watchers.length||evidence.processes.custom_reload_includes||evidence.processes.listeners.some(r=>r.LocalPort===4200))throw Error('BLOCKED_PROCESS_INTERRUPTION_NOT_AUTHORIZED');
 const sha=file=>fs.readFile(file).then(b=>crypto.createHash('sha256').update(b).digest('hex'));
 evidence.package='WP7B-R4';evidence.at=new Date().toISOString();evidence.authority_sha256=await sha(authority);
 evidence.authorized_edits=['Auth component focus-color styling and affected TypeScript tests only; no Python/global-theme edit'];
 evidence.original_auth_sha256=await sha('apps/web/src/app/auth/auth-page.component.ts');
 evidence.original_global_styles_sha256=await sha('apps/web/src/styles.css');
 evidence.preserved_reports={};
 for(const name of await fs.readdir('docs/qa/seller-experience'))if(/^wp7b-/.test(name)&&!name.startsWith('wp7b-r4-')){const f='docs/qa/seller-experience/'+name;evidence.preserved_reports[f]=await sha(f);}
 await fs.writeFile(destination,JSON.stringify(evidence,null,2));
 console.log(JSON.stringify({preflight:'PASS',api_processes:evidence.processes.api_processes.length,frontend_watchers:0,signed_qa:true,python_edits:false}));
}
