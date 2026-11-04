param(
  [Parameter(Mandatory=$true)][ValidateSet('Inspect','Pause','Resume')][string]$Action,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{16}$')][string]$Token
)
$ErrorActionPreference='Stop'
trap {
  $message=$_.Exception.Message
  $code='api_process_operation_failed'
  if($message -cmatch '^(api_|maintenance_|exact_|unsupported_|active_|unexpected_)[a-z_]+$'){$code=$message}
  @{status='FAIL';failure_code=$code;exception_type=$_.Exception.GetType().Name;line=$_.InvocationInfo.ScriptLineNumber}|ConvertTo-Json -Compress
  exit 1
}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$stage=Join-Path $env:LOCALAPPDATA "VAYUJIT OS\migration-stage\$Token"
$statePath=Join-Path $stage 'api-state.json'
Import-Module (Join-Path $PSScriptRoot 'pc-first-key-security.psm1') -Force
Import-Module (Join-Path $PSScriptRoot 'local-api-process-security.psm1') -Force
Assert-VayujitPrivateAcl -Path $stage -Kind Directory | Out-Null
if([IO.File]::ReadAllText((Join-Path $stage 'migration-run.marker')) -cne $Token){throw 'maintenance_run_marker_mismatch'}
if($Action -eq 'Inspect') {
  if(Test-Path -LiteralPath $statePath){throw 'api_state_already_exists'}
  $all=@(Get-CimInstance Win32_Process)
  $listeners=@(Get-NetTCPConnection -LocalPort 8000 -State Listen)
  if($listeners.Count -ne 1 -or $listeners[0].LocalAddress -cne '127.0.0.1'){throw 'exact_loopback_listener_required'}
  $target=$all | Where-Object ProcessId -EQ $listeners[0].OwningProcess | Select-Object -First 1
  if(-not $target -or $target.CommandLine -notmatch 'uvicorn\s+vayujit_api\.main:app' -or $target.CommandLine -notlike ('*'+$repo+'*')){throw 'api_process_identity_mismatch'}
  $flags=@([regex]::Matches($target.CommandLine,'--[a-z-]+') | ForEach-Object {$_.Value} | Sort-Object -Unique)
  if(@(Compare-Object $flags @('--app-dir','--host','--port','--reload')).Count -ne 0){throw 'unsupported_api_launch_flags'}
  if($target.CommandLine -notmatch '--host\s+127\.0\.0\.1' -or $target.CommandLine -notmatch '--port\s+8000'){throw 'api_binding_mismatch'}
  if(@($all | Where-Object {$_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match 'vayujit_api\.[a-z_.]*worker'}).Count){throw 'active_worker_requires_separate_review'}
  $root=$target
  while($true) {
    $parent=$all | Where-Object ProcessId -EQ $root.ParentProcessId | Select-Object -First 1
    if(-not $parent -or $parent.CommandLine -notmatch 'uvicorn\s+vayujit_api\.main:app' -or $parent.CommandLine -notlike ('*'+$repo+'*')){break}
    $root=$parent
  }
  $tree=@($root)
  for($depth=0;$depth -lt 6;$depth++) {
    $ids=@($tree | ForEach-Object {$_.ProcessId})
    $children=@($all | Where-Object {$_.ParentProcessId -in $ids -and $_.ProcessId -notin $ids})
    # Start-Process creates a private Windows console host. Do not terminate it
    # directly or mistake it for another business worker; Windows owns its exit.
    $children=@($children | Where-Object {-not (Test-VayujitPrivateConsoleChild -Process $_ -RootId $root.ProcessId)})
    if(-not $children.Count){break}
    foreach($child in $children) {
      if($child.Name -notmatch '^python(w)?\.exe$' -or ($child.CommandLine -notmatch 'uvicorn\s+vayujit_api\.main:app' -and $child.CommandLine -notmatch 'multiprocessing\.(spawn|resource_tracker)')){throw 'unexpected_api_descendant'}
    }
    $tree+=@($children)
  }
  $state=@{token=$Token;root=$root.ProcessId;processes=@($tree | ForEach-Object {@{id=$_.ProcessId;created=$_.CreationDate.ToUniversalTime().ToString('o')}});paused=$false;resumed=$false}
  [IO.File]::WriteAllText($statePath,($state|ConvertTo-Json -Depth 6))
  @{status='VERIFIED';process_count=$tree.Count;reload=$true;workers=0}|ConvertTo-Json -Compress
  exit 0
}
$state=Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
if($state.token -cne $Token){throw 'api_state_marker_mismatch'}
if($Action -eq 'Pause') {
  foreach($entry in $state.processes) {
    $live=Get-CimInstance Win32_Process -Filter ('ProcessId='+$entry.id)
    if($live -and $live.CreationDate.ToUniversalTime().ToString('o') -cne $entry.created){throw 'api_pid_reused'}
  }
  # Stop only the captured supervisor tree; no global Python termination.
  foreach($entry in $state.processes) {
    Stop-VayujitCapturedProcess -CapturedId $entry.id -Created $entry.created
  }
  for($i=0;$i -lt 40;$i++) {
    $left=@($state.processes | Where-Object {Get-Process -Id $_.id -ErrorAction SilentlyContinue})
    $port=@(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
    if(-not $left.Count -and -not $port.Count){break}
    Start-Sleep -Milliseconds 250
  }
  if($left.Count -or $port.Count){throw 'api_quiescence_not_verified'}
  $state.paused=$true
  [IO.File]::WriteAllText($statePath,($state|ConvertTo-Json -Depth 6))
  @{status='PAUSED';port_absent=$true;process_count=$state.processes.Count}|ConvertTo-Json -Compress
  exit 0
}
if(-not $state.paused -or $state.resumed){throw 'api_resume_state_invalid'}
if(@(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).Count){throw 'api_port_taken_do_not_replace'}
$python=Join-Path $repo 'apps\api\.venv\Scripts\python.exe'
$api=Join-Path $repo 'apps\api'
Initialize-VayujitApiResumeState -State $state
$process=Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','vayujit_api.main:app','--app-dir',('"'+$api+'"'),'--host','127.0.0.1','--port','8000','--reload') -WorkingDirectory $repo -WindowStyle Hidden -PassThru
$state.resumed=$true
$state.new_root=$process.Id
[IO.File]::WriteAllText($statePath,($state|ConvertTo-Json -Depth 6))
@{status='RESUME_STARTED';pid=$process.Id}|ConvertTo-Json -Compress
