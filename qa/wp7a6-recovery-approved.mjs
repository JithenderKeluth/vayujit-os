// One exact HUMAN-approved recovery. No parameters can select another database.
import {spawn} from 'node:child_process';
const mode=process.argv[2];
if(!['verify','recover'].includes(mode))throw Error('EXACT_RECOVERY_MODE_REQUIRED');
const code=String.raw`
import hashlib, json, shutil, subprocess, sys, time
from datetime import UTC, datetime
from pathlib import Path
from sqlalchemy import text
from qa.postgres_instance import ROOT, ROLE, QaInstance, database_name

token = '0e63cd34fede26e1'
target = ROOT / 'tmp/qa-wp7a6/recovery-0e63cd34fede26e1.json'
result = {'token':token, 'database':database_name(token), 'oid':13516456,
          'human_approval':'Exact recovery approved in conversation on 2026-11-04 Asia/Calcutta',
          'non_force':True, 'raw_output_persisted':False}
stage = 'instance verification'
try:
    instance = QaInstance()
    instance.verify_server()
    if (instance.manifest['instance_id'] != '389b97d2-a4cd-4d9b-972e-6bb2bf5785eb' or
        instance.manifest['container_id'] != 'a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23'):
        raise ValueError('QA_EXACT_INSTANCE_REQUIRED')
    record = instance.load(token)
    if record['state'] != 'DROPPING' or record['oid'] != 13516456 or not record.get('creation_id'):
        raise ValueError('QA_EXACT_SIGNED_LIFECYCLE_REQUIRED')
    final = json.loads((ROOT / 'tmp/qa-seller-browser' / token / 'session-final.json').read_text())
    if (final['token'] != token or final['database_scope'] != database_name(token) or
        final['child_exit'] != 1 or final['status'] != 'CLEANUP_BLOCKED'):
        raise ValueError('QA_EXITED_CHILD_EVIDENCE_REQUIRED')
    stage = 'active operation verification'
    check = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
        "$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.Name -in @('python.exe','node.exe','powershell.exe') -and ($_.CommandLine -like '*0e63cd34fede26e1*' -or $_.CommandLine -match 'qa[.]fixture_server|fixture_server[.]py|seller-browser-session[.]mjs|wp7-run[.]mjs|test-seller-wp7a6[.]ps1') }).Count"],
        capture_output=True,text=True,timeout=25,check=False,creationflags=subprocess.CREATE_NO_WINDOW)
    # The check explicitly excludes only its own $PID, never another process.
    result['process_check']={'exit_code':check.returncode,'matching_count':int(check.stdout.strip()) if check.stdout.strip().isdigit() else None,'stderr_bytes':len(check.stderr),'raw_output_persisted':False}
    if check.returncode != 0 or check.stdout.strip() != '0':
        raise ValueError('QA_NO_ACTIVE_OPERATION_REQUIRED')
    stage = 'database identity verification'
    engine = instance.engine()
    try:
        with engine.connect() as db:
            row = db.execute(text('SELECT d.oid::bigint,r.rolname,d.datconnlimit FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba WHERE d.datname=:n'),{'n':database_name(token)}).one()
            if tuple(row) != (13516456,ROLE,-2):
                raise ValueError('QA_EXACT_OWNER_OID_TOMBSTONE_REQUIRED')
            if db.scalar(text('SELECT count(*) FROM pg_stat_activity WHERE datname=:n'),{'n':database_name(token)}) != 0:
                raise ValueError('QA_ZERO_SESSIONS_REQUIRED')
    finally:
        engine.dispose()
    result.update({'preflight':'PASS','matching_qa_processes':0,'sessions':0,'signed_state':'DROPPING'})
    if sys.argv[1] == 'verify':
        print(json.dumps({**result,'status':'VERIFIED_READ_ONLY'}))
        sys.exit(0)
    stage = 'failure evidence preservation'
    archive = target.parent / ('before-approved-recovery-' + datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ'))
    archive.mkdir(exist_ok=False)
    files = [ROOT / 'docs/qa/seller-experience' / name for name in
             ('wp7a6-closure-report.md','wp7a6-defect-register.md','wp7a6-gate.json','wp7a6-coverage-ledger.json')]
    files.append(ROOT / 'tmp/qa-wp7a6-final-audit.json')
    manifest=[]
    for file in files:
        shutil.copyfile(file,archive/file.name)
        manifest.append({'file':str(file.relative_to(ROOT)), 'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    (archive/'manifest.json').write_text(json.dumps(manifest,indent=2))
    result['previous_evidence_archive']=str(archive.relative_to(ROOT))
    stage = 'guarded resume_drop'
    started=time.monotonic()
    instance.resume_drop(token,timeout_ms=90000)
    record=instance.load(token)
    if record['state']!='DROPPED' or record['oid']!=13516456:
        raise ValueError('QA_DROPPED_RECORD_REQUIRED')
    result.update({'status':'DROPPED','seconds':round(time.monotonic()-started,3),
                   'completed_at':datetime.now(UTC).isoformat(), 'state':record['state']})
    target.write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
except Exception as error:
    # No exception text, DSNs, SQL or raw child output may leave this boundary.
    result.update({'status':'FAILED','stage':stage,'exception_type':type(error).__name__})
    if sys.argv[1]=='recover':
        target.write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
    sys.exit(1)
`;
const child=spawn('apps/api/.venv/Scripts/python.exe',['-',mode],{windowsHide:true,stdio:['pipe','pipe','pipe']});
let output='',stderrBytes=0,overflow=false;
child.stdout.on('data',d=>{if(output.length+d.length>16000)overflow=true;else output+=d;});
child.stderr.on('data',d=>stderrBytes+=d.length);
child.on('error',()=>{console.log(JSON.stringify({status:'LAUNCH_FAILED',raw_output_persisted:false}));process.exitCode=1;});
child.on('exit',code=>{
 let validReport=false;
 try {const result=JSON.parse(output.trim());if(overflow||result.token!=='0e63cd34fede26e1')throw Error();console.log(JSON.stringify(result));validReport=true;}
 catch {console.log(JSON.stringify({status:'INVALID_SAFE_REPORT',exit_code:code,stderr_bytes:stderrBytes,raw_output_persisted:false}));}
 process.exitCode=code===0&&validReport?0:1;
});
child.stdin.end(code);
child.stdin.on('error',()=>{/* Report only launch/exit metadata, never raw output. */});
