// Read-only, bounded x64 Windows CWD inspection. No environment/command memory dump.
// PEB layout is internal: validate on this process first; fail rather than guess.
import {spawnSync} from 'node:child_process';
const pids=process.argv.slice(2);
if(!pids.length || pids.some(x=>!/^\d+$/.test(x)))throw Error('EXPLICIT_PROCESS_IDS_REQUIRED');
const code=String.raw`
import ctypes as c,os,json,sys,struct
from pathlib import Path
try:
 if os.name!='nt' or c.sizeof(c.c_void_p)!=8: raise ValueError('X64_WINDOWS_REQUIRED')
 k=c.WinDLL('kernel32',use_last_error=True);n=c.WinDLL('ntdll')
 k.OpenProcess.argtypes=[c.c_uint32,c.c_int,c.c_uint32];k.OpenProcess.restype=c.c_void_p
 k.CloseHandle.argtypes=[c.c_void_p]
 k.ReadProcessMemory.argtypes=[c.c_void_p,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)]
 k.IsWow64Process.argtypes=[c.c_void_p,c.POINTER(c.c_int)]
 n.NtQueryInformationProcess.argtypes=[c.c_void_p,c.c_int,c.c_void_p,c.c_uint32,c.c_void_p]
 def cwd(pid):
  h=k.OpenProcess(0x410,False,pid)
  if not h: raise ValueError('READ_ONLY_PROCESS_OPEN_FAILED')
  try:
   wow=c.c_int()
   if not k.IsWow64Process(h,c.byref(wow)) or wow.value: raise ValueError('TARGET_ARCHITECTURE_DENIED')
   basic=(c.c_void_p*6)()
   if n.NtQueryInformationProcess(h,0,c.byref(basic),c.sizeof(basic),None)!=0: raise ValueError('BASIC_INFO_FAILED')
   def read(address,length):
    if not address or not 0<length<=2048: raise ValueError('BOUNDED_READ_REQUIRED')
    b=c.create_string_buffer(length);got=c.c_size_t()
    if not k.ReadProcessMemory(h,address,b,length,c.byref(got)) or got.value!=length: raise ValueError('BOUNDED_READ_FAILED')
    return b.raw
   params=struct.unpack('<Q',read(basic[1]+0x20,8))[0]
   length,maximum,buffer=struct.unpack('<HH4xQ',read(params+0x38,16))
   if length%2 or not 0<length<=maximum<=2048: raise ValueError('CWD_LAYOUT_DENIED')
   return read(buffer,length).decode('utf-16-le')
  finally:k.CloseHandle(h)
 if Path(cwd(os.getpid())).resolve()!=Path.cwd().resolve():raise ValueError('SELF_LAYOUT_CHECK_FAILED')
 root=Path.cwd().resolve(); allowed={root,root/'apps/api',root/'apps/web'}
 rows=[{'pid':int(pid),'working_directory':str(Path(cwd(int(pid))).resolve())} for pid in sys.argv[1:]]
 for row in rows:row['expected_repository_directory']=Path(row['working_directory']) in allowed
 print(json.dumps({'status':'PASS' if all(x['expected_repository_directory'] for x in rows) else 'STOP','read_only':True,'self_layout_check':True,'processes':rows}))
except Exception:print(json.dumps({'status':'STOP','read_only':True,'safe_error':'PROCESS_CWD_NOT_VERIFIED'}));sys.exit(1)
`;
const r=spawnSync('apps/api/.venv/Scripts/python.exe',['-c',code,...pids],{encoding:'utf8',windowsHide:true,timeout:10000});
if(r.status!==0){console.log(JSON.stringify({status:'STOP',safe_error:'PROCESS_CWD_NOT_VERIFIED'}));process.exitCode=1;}
else console.log(r.stdout.trim());
