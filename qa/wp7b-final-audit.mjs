// Read-only evidence audit; NEVER creates/drops/recovers a database.
import {spawnSync} from 'node:child_process';
const code=String.raw`
import hashlib,json,zipfile,datetime
def safe_action(value):
 verb=str(value).split(':',1)[0]
 return verb if verb in {'start','restart','die','stop','pause','unpause','create','destroy','exec_create','exec_start','exec_die','health_status'} else 'UNCLASSIFIED'
assert safe_action('exec_create: SECRET_COMMAND_ARGUMENT') == 'exec_create'
assert safe_action('secret_token') == 'UNCLASSIFIED'
assert safe_action('restart') == 'restart'
from sqlalchemy import text
from qa.postgres_instance import ROOT,PRIVATE,QaInstance,database_name
from qa.wp7a3_final_audit import observed_preservation
from urllib.parse import quote,quote_plus
i=QaInstance();i.verify_server()
folders=[p for p in (ROOT/'tmp/qa-seller-browser').iterdir() if (p/'wp7b-run.json').exists()]
backend=ROOT/'tmp/qa-wp7b-backend'
tokens=sorted({p.name for p in folders+(list(backend.iterdir()) if backend.exists() else [])})
rows=[];e=i.engine()
with e.connect() as c:
 for token in tokens:
  r=i.load(token)
  rows.append({'token':token,'signed_state':r['state'],'absent':c.scalar(text('select count(*) from pg_database where datname=:n'),{'n':database_name(token)})==0})
e.dispose()
traces=[];leaks=0;files=0
needles={v.encode() for n in ['qa-password','bootstrap-password','guard-key'] for s in [(PRIVATE/n).read_text().strip()] for v in [s,quote(s,safe=''),quote_plus(s)]}
roots=folders+[ROOT/'tmp/qa-wp7b',ROOT/'docs/qa/seller-experience']
if backend.exists(): roots.append(backend)
for root in roots:
 for p in root.rglob('*'):
  if not p.is_file():continue
  if p.suffix.lower() in {'.json','.md','.xml','.mjs','.ps1'}:
   files+=1;leaks+=int(any(n in p.read_bytes() for n in needles))
  if p.name=='trace.zip':
   with zipfile.ZipFile(p) as z:
    ok=z.testzip() is None
    for name in z.namelist(): leaks+=int(any(n in z.read(name) for n in needles))
   traces.append({'file':p.relative_to(ROOT).as_posix(),'crc':'PASS' if ok else 'FAIL'})
provenance=json.loads((ROOT/'tmp/qa-wp7b/provenance.json').read_text())
preserved=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in provenance['manifest'].items())
docker=observed_preservation(i)
baseline=json.loads((ROOT/'tmp/qa-postgres/preflight.json').read_text(encoding='utf-8-sig')) if (ROOT/'tmp/qa-postgres/preflight.json').exists() else None
events={'retained_event_count':None,'attribution':'UNATTRIBUTED'}
try:
 raw=i.docker('events','--since','2026-10-24T00:00:00Z','--until',datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'--filter','container=infrastructure-postgres-1','--format','{{json .}}')
 entries=[json.loads(line) for line in raw.splitlines() if line.strip()]
 events={'retained_event_count':len(entries),'actions':sorted({safe_action(x.get('Action','UNKNOWN')) for x in entries}),'command_arguments_persisted':False,'redaction_self_checks_passed':3,'attribution':'UNATTRIBUTED; retained events do not identify an authorized actor'}
except Exception:events={'retained_event_count':None,'attribution':'UNAVAILABLE; no lifecycle action attempted'}
result={'package':'WP7B','read_only':True,'database_cleanup':'PASS' if rows and all(x['absent'] and x['signed_state']=='DROPPED' for x in rows) else 'FAIL','databases':rows,'traces':traces,'text_files_scanned':files,'protected_secret_matches':leaks,'wp7a7_sources_unchanged':preserved,'docker_preservation':docker,'historical_docker_events':events,'permanent_database_accessed':False}
(ROOT/'tmp/qa-wp7b/final-audit.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'cleanup':result['database_cleanup'],'databases':len(rows),'traces':len(traces),'secret_matches':leaks,'wp7a7_unchanged':preserved,'docker_structural_identity_unchanged':docker.get('structural_identity_unchanged',docker.get('status')=='PASS')}))
`;
const r=spawnSync('apps/api/.venv/Scripts/python.exe',['-c',code],{encoding:'utf8',windowsHide:true,timeout:120000,maxBuffer:2*1024*1024});
if(r.status!==0){console.log(JSON.stringify({status:'BLOCKED',raw_output_persisted:false}));process.exitCode=1;}else console.log(r.stdout.trim().split(/\r?\n/).at(-1));
