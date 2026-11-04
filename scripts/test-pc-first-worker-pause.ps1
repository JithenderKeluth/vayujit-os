param([string]$EvidencePath)
$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "pc-first-key-security.psm1") -Force
Import-Module (Join-Path $PSScriptRoot "pc-first-backup-artifacts.psm1") -Force
$engine = (Get-Process -Id $PID).Path
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runId = [guid]::NewGuid().ToString("N")
$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$root = Join-Path $tempBase ("vayujit-worker-pause-test-" + $runId)
$rows = [System.Collections.Generic.List[object]]::new()
$report = [ordered]@{status="RUNNING";passed=0;failed=0;skipped=0;scope="Windows PowerShell native probes and extracted production lifecycle/catch/recovery with fake Docker only";tests=$rows;scenarios=@{};cleanup="PENDING"}
if (-not $EvidencePath) { $EvidencePath = Join-Path $repo "tmp\pc-first-certification\worker-pause-tests-$runId.json" }
function Assert-Case([bool]$Condition,[string]$Name) {
  $rows.Add(@{name=$Name;status=$(if($Condition){"PASS"}else{"FAIL"})})
  if(-not $Condition){$report.failed++;throw "Worker-pause regression assertion failed."}
  $report.passed++; Write-Output "PASS $Name"
}
function Write-TestFile([string]$Path,[string]$Text){[System.IO.File]::WriteAllText($Path,$Text,[System.Text.UTF8Encoding]::new($false))}
try {
  New-Item -ItemType Directory -Path $root -Force | Out-Null
  # Reproduce the exact PS 5.1 stderr trap, independently of Docker availability.
  $warningProbe = Join-Path $root "warning.ps1"
  Write-TestFile $warningProbe '[Console]::Error.WriteLine("PRIVATE-STDERR-SENTINEL"); exit 0'
  $baselineId = $null
  try { & $engine -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $warningProbe 2>$null | Out-Null } catch { $baselineId = $_.FullyQualifiedErrorId }
  Assert-Case ($baselineId -eq "NativeCommandError") "Windows PowerShell 5.1 reproduces the old stderr/Stop failure even for exit zero"
  $captured = Invoke-VayujitNativeCapture -FilePath $engine -Arguments @("-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",$warningProbe) -TimeoutSeconds 5
  Assert-Case ($captured.ExitCode -eq 0 -and $captured.StdErr.Contains("PRIVATE-STDERR-SENTINEL")) "native capture observes successful exit despite stderr without emitting it"
  $orderedFailure = New-VayujitBackupFailureReport -BackupId probe -FailureOperation "worker pause" -FailureCode "worker_pause_failed"
  $copyId=$null;try{$null=$orderedFailure.Clone()}catch{$copyId=$_.FullyQualifiedErrorId}
  Assert-Case ($copyId -eq "MethodNotFound") "canonical ordered failure report reproduces the old Clone failure that prevented report writing"

  $timeoutProbe=Join-Path $root "timeout.ps1"
  Write-TestFile $timeoutProbe 'Start-Sleep -Seconds 10; exit 0'
  $watch=[Diagnostics.Stopwatch]::StartNew();$timedOut=$false
  try { $null=Invoke-VayujitNativeCapture -FilePath $engine -Arguments @("-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",$timeoutProbe) -TimeoutSeconds 1 } catch [TimeoutException] { $timedOut=$true }
  $watch.Stop()
  Assert-Case ($timedOut -and $watch.Elapsed.TotalSeconds -lt 8) "native timeout fails closed and terminates only the owned probe client"

  $source=[System.IO.File]::ReadAllText((Join-Path $PSScriptRoot "backup-pc-first.ps1"))
  $tokens=$null;$parseErrors=$null
  $ast=[System.Management.Automation.Language.Parser]::ParseInput($source,[ref]$tokens,[ref]$parseErrors)
  if($parseErrors.Count){throw "Production backup must parse."}
  $names=@("Write-BackupCheckpoint","Write-BackupCaughtCheckpoint","Set-BackupStage","Complete-BackupStage","Add-CleanupFailure","Assert-BackupNativeExit","Invoke-BackupDockerCaptured","Get-BackupWorkerState")
  $helpers=@($ast.FindAll({param($n)$n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -in $names},$true)|ForEach-Object{$_.Extent.Text}) -join "`n"
  $runtime=$ast.Find({param($n)$n -is [System.Management.Automation.Language.TryStatementAst] -and $n.Body.Extent.Text.Contains('Set-BackupStage -Operation "maintenance status check"')},$true)
  if(-not $runtime -or $runtime.CatchClauses.Count -ne 1 -or -not $runtime.Finally){throw "Production lifecycle boundaries unavailable."}
  $start=$source.IndexOf('  Set-BackupStage -Operation "maintenance status check"',[StringComparison]::Ordinal)
  $end=$source.IndexOf('  Set-BackupStage -Operation "PostgreSQL container lookup"',$start,[StringComparison]::Ordinal)
  $prefix=$source.Substring($start,$end-$start)
  # Only the timeout scenario shortens the extracted call site's deadline. The
  # production helper is unchanged and other scenarios retain its 90 seconds.
  $prefix=$prefix.Replace('-TimeoutSeconds 90','-TimeoutSeconds $PauseTimeout')
  $catchBody=$runtime.CatchClauses[0].Body.Extent.Text
  $finallyBody=$runtime.Finally.Extent.Text
  $trailer=$source.Substring($runtime.Extent.EndOffset)
  $fakePath=Join-Path $root "fake-docker.ps1"
  $fakeBody=@'
$ErrorActionPreference="Stop"
$root=$args[0];$cmd=@($args|Select-Object -Skip 1)
$path=Join-Path $root "state.json"
$state=Get-Content -LiteralPath $path -Raw|ConvertFrom-Json
function Save-State{[IO.File]::WriteAllText($path,($state|ConvertTo-Json -Depth 5))}
function Event([string]$Value){$state.events=@($state.events)+$Value;Save-State}
# Every lifecycle call writes progress to stderr like Compose does.
[Console]::Error.WriteLine("PRIVATE-COMPOSE-PROGRESS-SENTINEL")
if($cmd -contains "maintenance-status"){$state.maintenance|Out-Null;@{maintenance=$state.maintenance}|ConvertTo-Json -Compress;exit 0}
if($cmd -contains "maintenance-on"){Event "maintenance_on";$state.maintenance=$true;Save-State;'{"maintenance":true}';exit 0}
if($cmd -contains "maintenance-off"){
  Event "maintenance_off"
  if($state.scenario -eq "maintenance_clear_failure"){exit 41}
  $state.maintenance=$false;Save-State;'{"maintenance":false}';exit 0
}
if($cmd[0] -eq "ps"){
  if($cmd -contains "worker"){if($state.scenario -ne "missing"){"a"*64};exit 0}
  if($cmd -contains "api"){"b"*64;exit 0}
}
if($cmd[0] -eq "inspect"){
  if($cmd[-1] -eq ("b"*64)){"healthy";exit 0}
  if($cmd -contains "{{.State.Health.Status}}"){"healthy";exit 0}
  if($state.scenario -eq "inspect_failure"){exit 19}
  if($state.scenario -eq "invalid_state"){'{"Running":"false"}';exit 0}
  $status=if($state.running){"running"}else{"exited"}
  @{Running=$state.running;Paused=$state.paused;Restarting=$false;Status=$status;Health=@{Status=$state.health}}|ConvertTo-Json -Compress
  exit 0
}
if($cmd[0] -eq "stop" -and $cmd[-1] -eq "worker"){
  if($cmd.Count -ne 4 -or $cmd[1] -ne "--timeout" -or $cmd[2] -ne "45"){exit 98}
  Event "stop_worker"
  if($state.scenario -eq "stop_timeout"){Start-Sleep -Seconds 10;exit 0}
  if($state.scenario -in @("stop_failure","recovery_failure")){exit 37}
  if($state.scenario -ne "still_running"){$state.running=$false;Save-State}
  exit 0
}
if($cmd[0] -eq "stop" -and $cmd[-1] -eq "api"){if($cmd.Count -ne 4 -or $cmd[1] -ne "--timeout" -or $cmd[2] -ne "30"){exit 98};Event "stop_api";if($state.scenario -eq "api_pause_failure"){exit 43};exit 0}
if($cmd[0] -eq "start" -and $cmd[-1] -eq "worker"){
  Event "start_worker"
  if($state.scenario -eq "recovery_failure"){exit 29}
  $state.running=$true;$state.health="healthy";Save-State;exit 0
}
if($cmd[0] -eq "start" -and $cmd[-1] -eq "api"){Event "start_api";exit 0}
if($cmd[0] -eq "exec" -and $cmd -contains "rm"){Event "temporary_cleanup";exit 0}
exit 99
'@
  Write-TestFile $fakePath $fakeBody
  $driver=Join-Path $root "production-lifecycle-probe.ps1"
  $header=@'
param([string]$Root,[string]$Repository,[string]$FakePath,[int]$PauseTimeout=90)
$ErrorActionPreference="Stop"
Import-Module (Join-Path $Repository "scripts\pc-first-key-security.psm1") -Force
Import-Module (Join-Path $Repository "scripts\pc-first-backup-artifacts.psm1") -Force
$DisposableCertification=$true
$docker=[pscustomobject]@{Source=(Get-Process -Id $PID).Path}
$composeArgs=@("-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",$FakePath,$Root)
$configRoot=$Root;$backupRoot=$Root;$workRoot=Join-Path $Root "work"
New-Item -ItemType Directory -Path $workRoot -Force|Out-Null
$backupId="worker-probe";$statusPath=Join-Path $Root "last-backup-status.json"
$backupReportFullPath=Join-Path $Root "backup-rehearsal.json"
$maintenanceOwned=$false;$workerStopped=$false;$apiStopped=$false
$servicePauseTimedOut=$false
$backupCompleted=$false;$backupFailureMessage=$null;$cleanupFailure=$null
$backupCurrentOperation="backup preflight";$backupCurrentFailureCode="backup_preflight_failed"
$backupNativeExitCode=$null;$dockerFailureOperation=$null;$dockerFailureExitCode=$null
$script:backupReportWriteFailed=$false
# Fake native transport: direct docker inspect has no Compose prefix. Add the
# PowerShell fake-client launcher only in this test adapter, not in production.
function Invoke-VayujitNativeCapture {
  param([string]$FilePath,[string[]]$Arguments,[int]$TimeoutSeconds)
  if($Arguments[0] -eq "inspect"){$Arguments=@($composeArgs)+$Arguments}
  pc-first-key-security\Invoke-VayujitNativeCapture -FilePath $FilePath -Arguments $Arguments -TimeoutSeconds $TimeoutSeconds
}
# No delay needed for fake health retry probes. Fake native timeout has its own real sleep.
function Start-Sleep{param([int]$Seconds)}
'@
  $probeBody=$header+"`n"+$helpers+"`ntry {`n"+$prefix+"`nSet-BackupStage -Operation 'PostgreSQL container lookup' -FailureCode 'postgres_container_unavailable'`nthrow 'postgres_container_unavailable'`n} catch "+$catchBody+" finally "+$finallyBody+"`n"+$trailer
  Write-TestFile $driver $probeBody
  function Run-Lifecycle([string]$Scenario){
    $caseRoot=Join-Path $root $Scenario;New-Item -ItemType Directory -Path $caseRoot|Out-Null
    $state=@{scenario=$Scenario;maintenance=($Scenario -eq "maintenance_already_on");running=($Scenario -ne "stopped");paused=($Scenario -eq "paused");health=$(if($Scenario -eq "unhealthy"){"unhealthy"}else{"healthy"});events=@()}
    Write-TestFile (Join-Path $caseRoot "state.json") ($state|ConvertTo-Json -Depth 5)
    $pauseTimeout=if($Scenario -eq "stop_timeout"){2}else{90}
    $capture=Invoke-VayujitNativeCapture -FilePath $engine -Arguments @("-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",$driver,"-Root",$caseRoot,"-Repository",$repo,"-FakePath",$fakePath,"-PauseTimeout",[string]$pauseTimeout) -TimeoutSeconds 50
    $childPath=Join-Path $caseRoot "backup-rehearsal.json"
    $resolved=Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode $capture.ExitCode -ReportPath $childPath
    $diagnostic=Get-VayujitBackupChildDiagnostic -LaunchSucceeded $true -ProcessExitCode $capture.ExitCode -ExecutablePath $engine -ChildScriptPath $driver -StdOut $capture.StdOut -StdErr $capture.StdErr -ReportPath $childPath
    $state=Get-Content -LiteralPath (Join-Path $caseRoot "state.json") -Raw|ConvertFrom-Json
    $report.scenarios[$Scenario]=@{failure=$resolved.Failure;ledger=$diagnostic.stage_ledger;events=$state.events;maintenance=$state.maintenance;running=$state.running;exit_code=$capture.ExitCode}
    return [pscustomobject]@{Failure=$resolved.Failure;State=$state;ExitCode=$capture.ExitCode;Diagnostic=$diagnostic;StatusPath=(Join-Path $caseRoot "last-backup-status.json")}
  }
  $success=Run-Lifecycle "success"
  $report.first_probe=@{failure=$success.Failure;diagnostic=$success.Diagnostic;events=$success.State.events}
  Assert-Case ($success.Failure.failure_code -eq "postgres_container_unavailable" -and $success.State.events -contains "stop_api") "successful stop plus inspected exited worker permits reaching only the artificial pre-database boundary"
  Assert-Case ($success.State.running -and -not $success.State.maintenance -and $success.State.events -contains "start_worker" -and $success.State.events -contains "start_api") "production recovery restarts API/worker, confirms health and clears owned maintenance despite stderr progress"
  $status=Get-Content -LiteralPath $success.StatusPath -Raw|ConvertFrom-Json
  Assert-Case ($status.status -eq "failed" -and $success.Failure.child_report_status -eq "FAIL") "failure report is written and separate status projection no longer calls OrderedDictionary.Clone"

  foreach($scenario in @("stopped","paused","unhealthy","missing","inspect_failure","invalid_state")){
    $case=Run-Lifecycle $scenario
    $lifecycleEvents=@($case.State.events|Where-Object{$_ -ne "temporary_cleanup"})
    Assert-Case ($case.ExitCode -eq 1 -and $case.Failure.failure_operation -eq "worker state check" -and $lifecycleEvents.Count -eq 0 -and -not $case.State.maintenance) "worker $scenario is rejected before maintenance, stop or database access"
  }
  $failed=Run-Lifecycle "stop_failure"
  Assert-Case ($failed.Failure.failure_code -eq "worker_pause_failed" -and $failed.Failure.docker_exit_code -eq 37 -and $failed.State.events -notcontains "stop_api") "genuine Docker stop exit 37 is preserved and prevents API pause/database access"
  Assert-Case ($failed.State.events -contains "maintenance_on" -and $failed.State.events -contains "start_worker" -and $failed.State.events -contains "maintenance_off" -and -not $failed.State.maintenance) "failure after maintenance enable performs healthy worker recovery and maintenance restoration"
  Assert-Case ($failed.Diagnostic.stage_ledger.failed_stage -eq "worker pause" -and $failed.Diagnostic.stage_ledger.expected_report_written -ceq $true) "worker-pause failure survives recovery in both structured report and stage ledger"
  $stubborn=Run-Lifecycle "still_running"
  Assert-Case ($stubborn.Failure.failure_code -eq "worker_not_quiescent" -and $stubborn.State.events -notcontains "stop_api") "exit-zero stop cannot bypass actual worker quiescence verification"
  $timeout=Run-Lifecycle "stop_timeout"
  Assert-Case ($timeout.Failure.failure_code -eq "worker_pause_timeout" -and $null -eq $timeout.Failure.docker_exit_code -and $timeout.State.events -notcontains "stop_api") "worker stop timeout is not fabricated as Docker success or a native exit code"
  Assert-Case ($timeout.State.events -contains "start_worker" -and $timeout.State.maintenance -and $timeout.Failure.cleanup_failure -match "maintenance_marker_preserved_because_service_stop_timed_out") "timed-out stop attempts worker recovery but keeps maintenance for uncertain server-side stop completion"
  $recovery=Run-Lifecycle "recovery_failure"
  Assert-Case ($recovery.Failure.failure_code -eq "worker_pause_failed" -and $recovery.Failure.native_exit_code -eq 37 -and $recovery.Failure.cleanup_failure -match "worker_restart_failed") "original stop failure and native exit survive independent recovery failure"
  Assert-Case ($recovery.State.maintenance -and $recovery.State.events -notcontains "maintenance_off" -and $recovery.Failure.cleanup_failure -match "maintenance_marker_preserved_because_worker_is_not_healthy") "failed worker recovery preserves maintenance and is never silently reported healthy"
  $apiFailed=Run-Lifecycle "api_pause_failure"
  Assert-Case ($apiFailed.Failure.failure_code -eq "api_pause_failed" -and $apiFailed.Failure.native_exit_code -eq 43 -and $apiFailed.State.events -contains "start_api" -and -not $apiFailed.State.maintenance) "API-stop failure after worker quiescence recovers both services without losing its exit code"
  $clearFailed=Run-Lifecycle "maintenance_clear_failure"
  Assert-Case ($clearFailed.Failure.failure_code -eq "postgres_container_unavailable" -and $clearFailed.Failure.cleanup_failure -match "maintenance_clear_failed" -and $clearFailed.State.maintenance) "maintenance-clear failure is independent of the original backup error and remains visibly enabled"
  $existing=Run-Lifecycle "maintenance_already_on"
  Assert-Case ($existing.Failure.failure_code -eq "maintenance_already_enabled_or_unavailable" -and $existing.State.maintenance -and @($existing.State.events|Where-Object{$_ -ne "temporary_cleanup"}).Count -eq 0) "pre-existing maintenance is never cleared by backup"
  $safe=@{failed=$failed.Diagnostic;failure=$failed.Failure;timeout=$timeout.Failure;recovery=$recovery.Failure}
  $safeJson=$safe|ConvertTo-Json -Depth 8
  Assert-Case ($safeJson -notmatch 'PRIVATE-|"(?:StdErr|StdOut|CommandArguments)"\s*:|AGE-SECRET-KEY|postgresql://') "retained evidence excludes raw progress streams, command arguments and private material"
  $report.examples=$safe;$report.status="PASS"
}catch{
  $report.status="FAIL";if($report.failed -eq 0){$report.failed=1}
  $report.safe_error_category=[string]$_.CategoryInfo.Category;$report.safe_error_line=$_.InvocationInfo.ScriptLineNumber
  throw "Worker-pause tests failed; inspect sanitized evidence."
}finally{
  $full=[IO.Path]::GetFullPath($root)
  if($full.StartsWith($tempBase.TrimEnd('\','/')+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetFileName($full) -eq ("vayujit-worker-pause-test-"+$runId)){
    if(Test-Path -LiteralPath $full){Remove-Item -LiteralPath $full -Recurse -Force};$report.cleanup="PASS"
  }else{$report.cleanup="FAIL";$report.status="FAIL"}
  $evidenceFull=Resolve-VayujitEvidencePath -Path $EvidencePath
  Write-TestFile $evidenceFull (($report|ConvertTo-Json -Depth 9)+"`n")
}
Write-Output "Worker-pause regressions: $($report.passed) passed, $($report.failed) failed, $($report.skipped) skipped. No Docker engine or database was used."
