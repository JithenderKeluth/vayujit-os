param([ValidateSet('Pause','Resume')][string]$Action='Pause')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repo
try {
 $approval=Get-Content -LiteralPath 'tmp/qa-wp7br1/owner-authorization.json' -Raw|ConvertFrom-Json
 if($approval.development_process_pause_approval -ne $true){throw 'R1 process authorization required'}
 if($Action -eq 'Pause'){
  $all=@(Get-CimInstance Win32_Process)
  $selected=@($all|Where-Object {$_.CommandLine -like ('*'+$repo+'*') -and ($_.CommandLine -match 'uvicorn\s+vayujit_api\.main:app' -or $_.CommandLine -match 'serve.*--host\s+127\.0\.0\.1.*--port\s+4200')})
  if(-not $selected.Count){throw 'Exact development process preflight required'}
  $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
  $proof=@()
  foreach($entry in $selected){
   $owner=Invoke-CimMethod -InputObject $entry -MethodName GetOwnerSid
   if($owner.ReturnValue -ne 0 -or $owner.Sid -cne $sid){throw 'Development process owner mismatch'}
   if(-not $entry.ExecutablePath -or $entry.Name -notin @('python.exe','node.exe')){throw 'Unexpected executable'}
   $proof+=@{pid=$entry.ProcessId;created=$entry.CreationDate.ToUniversalTime().ToString('o');executable=$entry.ExecutablePath;repository_command_verified=$true;current_owner_verified=$true}
  }
  $cwd=& node qa/wp7br1-process-cwd.mjs @($selected|ForEach-Object {[string]$_.ProcessId})
  if($LASTEXITCODE -ne 0 -or ($cwd|ConvertFrom-Json).status -cne 'PASS'){throw 'Working directories not verified; no pause'}
  [IO.File]::WriteAllText((Join-Path $repo 'tmp/qa-wp7br1/process-preflight.json'),(@{processes=$proof;cwd=($cwd|ConvertFrom-Json)}|ConvertTo-Json -Depth 6))
 }
 & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'qa-wp7a6-app-window.ps1') -Action $Action -Package wp7br1
 exit $LASTEXITCODE
} finally {Pop-Location}
