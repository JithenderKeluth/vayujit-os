$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$record=Get-Content -LiteralPath (Join-Path $repo 'tmp/qa-wp7b/app-window.json') -Raw|ConvertFrom-Json
if($record.token -cne 'ea276ec8392d412c' -or -not $record.frontend_was_running -or $record.api_paused){throw 'Exact partial-pause record required; no generic recovery allowed'}
$api=@(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
if($api.Count -ne 1 -or $api[0].LocalAddress -cne '127.0.0.1' -or $api[0].OwningProcess -ne 15428){throw 'Previously observed API listener changed; no app process will be replaced'}
$process=Get-CimInstance Win32_Process -Filter 'ProcessId=15428'
if($process.Name -ine 'python.exe' -or $process.CommandLine -notlike ('*'+$repo+'*') -or $process.CommandLine -notmatch 'uvicorn.*vayujit_api\.main:app'){throw 'Remaining API identity mismatch'}
$ports=@(Get-NetTCPConnection -LocalPort 4200 -State Listen -ErrorAction SilentlyContinue)
if($ports.Count){throw 'Frontend port now occupied; do not launch a duplicate or replace it'}
$node=(Get-Command node -ErrorAction Stop).Source
$npm=Join-Path (Split-Path (Get-Command npm.cmd -ErrorAction Stop).Source -Parent) 'node_modules/npm/bin/npm-cli.js'
if(-not(Test-Path -LiteralPath $npm)){throw 'Installed npm CLI missing; no download allowed'}
$env:NG_CLI_ANALYTICS='false'
$started=Start-Process -FilePath $node -ArgumentList @(('"'+$npm+'"'),'run','dev:web') -WorkingDirectory $repo -WindowStyle Hidden -PassThru
$ready=$false
for($i=0;$i -lt 60;$i++){
  try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:4200/' -TimeoutSec 2; if($r.StatusCode -eq 200){$ready=$true;break}}catch{}
  Start-Sleep -Milliseconds 500
}
$live=$false
try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/health/live' -TimeoutSec 3; $live=$r.StatusCode -eq 200}catch{}
$proof=@{package='WP7B';frontend_start_requested=$true;frontend_index_http_200=$ready;api_live_http_200=$live;api_process_untouched=$true;api_pid=15428;database_operation=$false;original_failed_pause_record_preserved=$true;frontend_launcher_pid=$started.Id}
[IO.File]::WriteAllText((Join-Path $repo 'tmp/qa-wp7b/app-restoration.json'),($proof|ConvertTo-Json))
$proof|ConvertTo-Json -Compress
if(-not $ready -or -not $live){exit 1}
