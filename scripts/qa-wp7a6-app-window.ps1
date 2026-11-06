param(
  [ValidateSet('Pause','Resume')][string]$Action='Pause',
  [ValidateSet('wp7a6','wp7a7','wp7b','wp7br1')][string]$Package='wp7a6'
)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$recordDirectory=Join-Path $repo ('tmp/qa-'+$Package)
$null=New-Item -ItemType Directory -Path $recordDirectory -Force
$record=Join-Path $recordDirectory 'app-window.json'
if($Action -eq 'Pause') {
  if(Test-Path -LiteralPath $record){throw 'QA app window already recorded; inspect before reuse'}
  $token=[guid]::NewGuid().ToString('N').Substring(0,16)
  $private=& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'local-reconciliation-private.ps1') -Token $token
  if($LASTEXITCODE){throw 'Private process-state preparation failed'}
  $before=& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'local-api-maintenance.ps1') -Action Inspect -Token $token
  if($LASTEXITCODE){throw 'Exact API inspection failed; no pause attempted'}
  $ports=@(Get-NetTCPConnection -LocalPort 4200 -State Listen -ErrorAction SilentlyContinue)
  if($ports.Count -gt 1){throw 'Ambiguous frontend listener'}
  $front=$null
  if($ports.Count) {
    if($ports[0].LocalAddress -cne '127.0.0.1'){throw 'Non-loopback frontend denied'}
    $front=Get-CimInstance Win32_Process -Filter ('ProcessId='+$ports[0].OwningProcess)
    if($front.Name -ine 'node.exe' -or $front.CommandLine -notlike ('*'+$repo+'*') -or $front.CommandLine -notmatch 'serve.*--host\s+127\.0\.0\.1.*--port\s+4200'){throw 'Frontend process identity mismatch'}
  }
  $state=@{token=$token;api_before=($before|ConvertFrom-Json);frontend_was_running=[bool]$front;api_paused=$false;frontend_paused=$false;restored=$false;database_modified=$false}
  [IO.File]::WriteAllText($record,($state|ConvertTo-Json -Depth 6))
  $paused=& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'local-api-maintenance.ps1') -Action Pause -Token $token
  if($LASTEXITCODE){throw 'API pause incomplete; retain exact state for recovery'}
  $state.api_paused=$true
  [IO.File]::WriteAllText($record,($state|ConvertTo-Json -Depth 6))
  if($front) {
    Import-Module (Join-Path $PSScriptRoot 'local-api-process-security.psm1') -Force
    Stop-VayujitCapturedProcess -CapturedId $front.ProcessId -Created ($front.CreationDate.ToUniversalTime().ToString('o'))
    $state.frontend_paused=$true
  }
  for($i=0;$i -lt 30;$i++) {
    $left=@(Get-NetTCPConnection -LocalPort 8000,4200 -State Listen -ErrorAction SilentlyContinue)
    if(-not $left.Count){break}
    Start-Sleep -Milliseconds 200
  }
  if($left.Count){throw 'Normal app ports did not quiesce; no database operation authorized'}
  [IO.File]::WriteAllText($record,($state|ConvertTo-Json -Depth 6))
  @{status='PAUSED';api=$true;frontend=$state.frontend_paused;database_modified=$false}|ConvertTo-Json -Compress
  exit 0
}
$state=Get-Content -LiteralPath $record -Raw|ConvertFrom-Json
if($state.restored -or -not $state.api_paused){throw 'Invalid app recovery state'}
$env:VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP='true'
$env:VAYUJIT_LIVE_MUTATIONS_ENABLED='false'
$result=& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'local-api-maintenance.ps1') -Action Resume -Token $state.token
if($LASTEXITCODE){throw 'API recovery failed; exact state retained'}
if($state.frontend_was_running) {
  if(@(Get-NetTCPConnection -LocalPort 4200 -State Listen -ErrorAction SilentlyContinue).Count){throw 'Frontend port occupied; do not replace'}
  $node=(Get-Command node -ErrorAction Stop).Source
  $npm=Join-Path (Split-Path (Get-Command npm.cmd -ErrorAction Stop).Source -Parent) 'node_modules/npm/bin/npm-cli.js'
  if(-not(Test-Path -LiteralPath $npm)){throw 'Installed npm CLI missing; no download permitted'}
  $env:NG_CLI_ANALYTICS='false'
  $null=Start-Process -FilePath $node -ArgumentList @(('"'+$npm+'"'),'run','dev:web') -WorkingDirectory $repo -WindowStyle Hidden -PassThru
}
$state.restored=$true
[IO.File]::WriteAllText($record,($state|ConvertTo-Json -Depth 6))
@{status='RESTORE_STARTED';database_modified=$false}|ConvertTo-Json -Compress
