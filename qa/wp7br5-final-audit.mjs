// R5 read-only independent preservation and offline evidence audit.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {inspect,canonicalContainers} from './wp7br5-preflight.mjs';
import {wp3Owner} from './wp3-fixtures.mjs';
const root='tmp/qa-wp7br5/',read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const pre=await read(root+'preflight.json'),checks=[];
const add=(id,ok,details={})=>checks.push({id,status:ok?'PASS':'FAIL',...details});
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const changed=[];for(const [p,v]of Object.entries(pre.preserved_reports))if(hash(await fs.readFile(p))!==v)changed.push(p);
add('prior_reports_preserved',changed.length===0,{count:Object.keys(pre.preserved_reports).length,changed});
const changedSources=[];for(const [p,v]of Object.entries(pre.preserved_sources))if(hash(await fs.readFile(p))!==v)changedSources.push(p);
add('unrelated_authorities_preserved',changedSources.length===0,{count:Object.keys(pre.preserved_sources).length,changed:changedSources});
const css=await fs.readFile('apps/web/src/app/campaigns/campaigns.css','utf8');
add('only_one_local_production_declaration',hash(css.replace(/  --vj-focus: var\(--vj-color-brand-strong\);\r?\n/,''))===pre.original_campaign_css_sha256);
for(const file of (await fs.readdir('qa')).filter(p=>/^wp7br5.*\.mjs$/.test(p)).map(p=>'qa/'+p).concat(['qa/unit/wp7br5.test.mjs'])){
 const r=spawnSync(process.execPath,['--check',file],{windowsHide:true,stdio:'pipe'});add('syntax:'+file,r.status===0,{exit:r.status});
}
const ps=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',"$t=$null;$e=$null;[void][System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'scripts/test-seller-wp7br5.ps1'),[ref]$t,[ref]$e);if($e.Count){exit 1}"],{windowsHide:true,stdio:'pipe'});
add('powershell_parser',ps.status===0,{exit:ps.status});
const prior=await read('docs/qa/seller-experience/wp7b-r4-gate.json'),gate=await read('docs/qa/seller-experience/wp7b-r5-gate.json');
const original=r=>JSON.stringify([r.id,r.criteria,r.expected,r.acceptance_source]);
add('original_40_acceptance_groups_preserved',gate.groups.length===40&&gate.groups.every((r,i)=>original(r)===original(prior.groups[i]))&&new Set(gate.groups.map(g=>g.id)).size===40);
add('no_style_fixture_promoted_to_canonical_certification',gate.tests.component_style_browser.canonical_app===false&&gate.overall_WP7B==='INCOMPLETE'&&gate.human.no_actual_speech_inferred_from_DOM===true);
let now;try{now=inspect();const sort=r=>r.slice().sort((a,b)=>a.pid-b.pid);add('normal_API_tree_unchanged',JSON.stringify(sort(pre.processes.api_processes))===JSON.stringify(sort(now.processes.api_processes)));add('frontend_watchers_unchanged',JSON.stringify(pre.processes.frontend_watchers)===JSON.stringify(now.processes.frontend_watchers));add('original_Docker_metadata_unchanged',JSON.stringify(canonicalContainers(pre.containers))===JSON.stringify(canonicalContainers(now.containers)),{before:pre.containers,after:now.containers,comparison:'Identity/all fields preserved; unordered inventories canonicalized only'});}catch{add('independent_process_container_inspection',false,{safe_code:'R5_PRESERVATION_NOT_ESTABLISHED'});}
const code=String.raw`
import os,json,pathlib,zipfile,re
private=pathlib.Path('tmp/qa-postgres-private')
secrets=[os.environ['R5_FIXTURE_PASSWORD'].encode()]
for n in ('qa-password','bootstrap-password','guard-key'):
 secrets.append((private/n).read_bytes().strip())
roots=[pathlib.Path('tmp/qa-wp7br5')]
roots.extend([p for p in pathlib.Path('docs/qa/seller-experience').glob('wp7b-r5-*')])
receipt=pathlib.Path('tmp/qa-wp7br5/session-control.json')
if receipt.exists():
 session=json.loads(receipt.read_text())
 token=session.get('session',{}).get('token','')
 if session.get('package')!='WP7B-R5' or not re.fullmatch('[a-f0-9]{16}',token):raise ValueError('R5_OWNED_EVIDENCE_SCOPE_REQUIRED')
 roots.append(pathlib.Path('tmp/qa-seller-browser')/token)
files=0;matches=0;zips=0;bad_crc=0
for root in roots:
 paths=root.rglob('*') if root.is_dir() else [root]
 for p in paths:
  if not p.is_file():continue
  if p.suffix=='.zip':
   zips+=1
   with zipfile.ZipFile(p) as z:
    if z.testzip() is not None:bad_crc+=1
    data=[z.read(n) for n in z.namelist()]
  elif p.suffix in ('.json','.md','.txt','.log'):data=[p.read_bytes()]
  else:continue
  files+=1
  for b in data:
   if any(s and s in b for s in secrets) or b'AGE-SECRET-KEY-' in b or re.search(rb'postgres(?:ql)?(?:\+psycopg)?://[^\s"<>]+:[^\s"<>]+@',b):matches+=1
print(json.dumps({'files_scanned':files,'sensitive_matches':matches,'trace_zips':zips,'crc_failures':bad_crc}))
`;
const security=spawnSync('apps/api/.venv/Scripts/python.exe',['-c',code],{windowsHide:true,encoding:'utf8',timeout:60000,env:{...process.env,R5_FIXTURE_PASSWORD:wp3Owner.password}});
let data;try{data=JSON.parse(security.stdout);}catch{data={safe_code:'R5_SECURITY_AUDIT_NOT_ESTABLISHED'};}
add('protected_secret_and_evidence_scan',security.status===0&&data.sensitive_matches===0&&data.crc_failures===0,data);
const diff=spawnSync('git',['-c','safe.directory=C:/Users/jithe/Documents/vayujit-os','diff','--check'],{windowsHide:true,stdio:'pipe'});add('git_diff_check',diff.status===0,{exit:diff.status});
const report={package:'WP7B-R5',at:new Date().toISOString(),read_only:true,lifecycle_operations:0,process_control:0,raw_output_persisted:false,checks,passed:checks.filter(c=>c.status==='PASS').length,failed:checks.filter(c=>c.status==='FAIL').length,application_cleanup:gate.environment.cleanup};
const previous=await read(root+'final-audit.json').catch(()=>null);
if(previous?.failed)await fs.writeFile(root+'audit-history-'+previous.at.replace(/[^a-z0-9]/gi,'')+'.json',JSON.stringify(previous,null,2));
await fs.writeFile(root+'final-audit.json',JSON.stringify(report,null,2));console.log(JSON.stringify({package:report.package,at:report.at,passed:report.passed,failed:report.failed,checks:report.checks.map(({id,status})=>({id,status}))}));process.exitCode=report.failed?1:0;
