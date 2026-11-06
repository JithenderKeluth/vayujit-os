// Offline source/evidence audit. No runtime, lifecycle, or normal app control.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {wp3Owner} from './wp3-fixtures.mjs';
const out='tmp/qa-wp7br4/',checks=[];
const add=(id,ok,details)=>checks.push({id,status:ok?'PASS':'FAIL',...details});
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const pre=JSON.parse(await fs.readFile(out+'preflight.json','utf8'));
const changed=[];for(const [file,hash]of Object.entries(pre.preserved_reports))if(sha(await fs.readFile(file))!==hash)changed.push(file);
add('prior_reports_unchanged',changed.length===0,{count:Object.keys(pre.preserved_reports).length,changed});
const files=(await fs.readdir('qa')).filter(f=>/^wp7br4.*\.mjs$/.test(f)).map(f=>'qa/'+f).concat(['qa/unit/wp7br4.test.mjs']);
for(const f of files){const r=spawnSync(process.execPath,['--check',f],{windowsHide:true,stdio:'pipe'});add('syntax:'+f,r.status===0,{exit:r.status});}
const ps=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',"$t=$null;$e=$null;[void][System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'scripts/test-seller-wp7br4.ps1'),[ref]$t,[ref]$e);if($e.Count){exit 1}"],{windowsHide:true,stdio:'pipe'});
add('powershell_parser',ps.status===0,{exit:ps.status});
const prettier=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-Command','npx.cmd --no-install prettier --check apps/web/src/app/auth/auth-page.component.ts apps/web/src/app/auth/auth-focus-r4.spec.ts'],{windowsHide:true,stdio:'pipe',timeout:60000});
add('prettier_after_fix',prettier.status===0,{exit:prettier.status});
const diff=spawnSync('git',['-c','safe.directory=C:/Users/jithe/Documents/vayujit-os','diff','--check'],{windowsHide:true,stdio:'pipe',timeout:60000});add('diff_check',diff.status===0,{exit:diff.status});
const code=String.raw`
import os,json,zipfile,pathlib,re
from urllib.parse import urlparse,unquote
roots=[pathlib.Path('tmp/qa-wp7br4'),pathlib.Path('tmp/qa-seller-browser/208c03c2118d62af')]
secrets=[os.environ['R4_FIXTURE_PASSWORD'].encode()]
url=os.environ.get('QA_DATABASE_ADMIN_URL','')
if url:
 password=urlparse(url).password
 if password:secrets.append(unquote(password).encode())
files=0;zips=0;matches=0;crc=0
for root in roots:
 for p in root.rglob('*'):
  if not p.is_file():continue
  if p.suffix=='.zip':
   zips+=1
   with zipfile.ZipFile(p) as z:
    if z.testzip() is not None:crc+=1
    data=[z.read(n) for n in z.namelist()]
  elif p.suffix in ('.json','.md','.txt','.log','.trace','.network'):data=[p.read_bytes()]
  else:continue
  files+=1
  for b in data:
   if any(s and s in b for s in secrets) or b'AGE-SECRET-KEY-' in b or re.search(rb'postgres(?:ql)?(?:\+psycopg)?://[^\s"<>]+:[^\s"<>]+@',b):matches+=1
print(json.dumps({'files':files,'trace_zips':zips,'crc_failures':crc,'sensitive_matches':matches}))
`;
const security=spawnSync('apps/api/.venv/Scripts/python.exe',['-c',code],{windowsHide:true,encoding:'utf8',timeout:60000,env:{...process.env,R4_FIXTURE_PASSWORD:wp3Owner.password}});
let data;try{data=JSON.parse(security.stdout);}catch{data={safe_code:'OFFLINE_EVIDENCE_AUDIT_FAILED'};}
add('evidence_security_and_zip_crc',security.status===0&&data.sensitive_matches===0&&data.crc_failures===0,data);
const gate=JSON.parse(await fs.readFile('docs/qa/seller-experience/wp7b-r4-gate.json','utf8'));
const prior=JSON.parse(await fs.readFile('docs/qa/seller-experience/wp7b-r3a-gate.json','utf8'));
const original=g=>JSON.stringify([g.id,g.criteria,g.expected,g.acceptance_source]);
add('gate_preserves_40_original_acceptance_ids',gate.groups.length===40&&new Set(gate.groups.map(g=>g.id)).size===40&&gate.groups.every((g,i)=>original(g)===original(prior.groups[i]))&&gate.gate_B==='FAIL'&&gate.overall_WP7B==='INCOMPLETE');
const receipt={package:'WP7B-R4',at:new Date().toISOString(),raw_output_persisted:false,checks,passed:checks.filter(c=>c.status==='PASS').length,failed:checks.filter(c=>c.status==='FAIL').length};
await fs.writeFile(out+'final-validation.json',JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
process.exitCode=receipt.failed?1:0;
