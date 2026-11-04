param([string]$EvidencePath)
$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "pc-first-key-security.psm1") -Force
Import-Module (Join-Path $PSScriptRoot "pc-first-backup-artifacts.psm1") -Force
$shellPath = (Get-Process -Id $PID).Path
$runId = [guid]::NewGuid().ToString("N")
$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$root = Join-Path $tempBase ("vayujit-stage-ledger-test-" + $runId)
$profile = Join-Path $root "profile"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$rows = [System.Collections.Generic.List[object]]::new()
$result = [ordered]@{scope="non-Docker stage protocol, synthetic injections and guarded real preflight only";status="RUNNING";passed=0;failed=0;skipped=0;tests=$rows;cleanup="PENDING"}
if (-not $EvidencePath) { $EvidencePath = Join-Path $repo "tmp\pc-first-certification\stage-ledger-tests-$runId.json" }
function Assert-Case([bool]$Condition, [string]$Name) {
  $rows.Add(@{name=$Name;status=$(if($Condition){"PASS"}else{"FAIL"})})
  if (-not $Condition) { $result.failed++; throw "Stage-ledger assertion failed." }
  $result.passed++
  Write-Output "PASS $Name"
}
$source = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot "backup-pc-first.ps1"))
$tokens=$null;$errors=$null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($source,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw "Backup source must parse before stage tests." }
$helperSource = @($ast.FindAll({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -in @("Write-BackupCheckpoint", "Write-BackupCaughtCheckpoint")},$true) | ForEach-Object {$_.Extent.Text}) -join "`n"
if (-not $helperSource.Contains('function Write-BackupCaughtCheckpoint')) { throw "Missing stage helper source." }
$startupStages = @("bootstrap load", "report boundary initialization", "key security module import", "backup artifact module import", "profile path resolution", "profile files check", "disposable argument validation", "profile configuration", "recipient validation", "identity ACL verification", "age dependency check", "age keygen dependency check", "Docker dependency check", "staging directory creation", "destination write probe", "PostgreSQL storage evidence", "media storage evidence", "destination independence check", "runtime initialization", "runtime staging creation", "child report write", "service recovery", "backup finalization")
function Run-Probe([string]$Stage, [string]$Action) {
  $file = Join-Path $root "stage-probe.ps1"
  $body = '$ErrorActionPreference="Stop"; $DisposableCertification=$true' + "`n" + $helperSource + "`n" +
    "Write-BackupCheckpoint -Stage 'bootstrap load' -State ENTER`nWrite-BackupCheckpoint -Stage 'bootstrap load' -State COMPLETE`n" +
    "Write-BackupCheckpoint -Stage '$Stage' -State ENTER`n" + $Action
  [System.IO.File]::WriteAllText($file,$body,[System.Text.UTF8Encoding]::new($false))
  $capture = Invoke-VayujitNativeCapture -FilePath $shellPath -WorkingDirectory $repo -Arguments @("-NoLogo","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",$file)
  $diagnostic = Get-VayujitBackupChildDiagnostic -LaunchSucceeded $true -ProcessExitCode $capture.ExitCode -ExecutablePath $shellPath -ChildScriptPath $file -StdOut $capture.StdOut -StdErr $capture.StdErr -ReportPath (Join-Path $profile "not-written.json")
  return [pscustomobject]@{Capture=$capture;Diagnostic=$diagnostic}
}
try {
  New-Item -ItemType Directory -Path $root,$profile -Force | Out-Null
  # The same production emitter/catch helper executes for every startup boundary.
  # These are protocol injections, not claims that all underlying operations ran.
  foreach ($stage in $startupStages) {
    $probe = Run-Probe $stage 'try { throw "PRIVATE-ERROR-SENTINEL" } catch { Write-BackupCaughtCheckpoint -Record $_; exit 1 }'
    $ledger = $probe.Diagnostic.stage_ledger
    Assert-Case ($probe.Capture.ExitCode -eq 1 -and $ledger.failed_stage -eq $stage -and $ledger.last_entered_stage -eq $stage -and $ledger.last_completed_stage -eq "bootstrap load" -and $ledger.failure_classification -eq "powershell_error" -and $ledger.source_line -gt 0 -and $ledger.expected_report_written -ceq $false) "terminating error boundary: $stage"
  }
  $promoted = Run-Probe "profile configuration" 'try { Write-Error "PRIVATE-PROMOTED-SENTINEL" } catch { Write-BackupCaughtCheckpoint -Record $_; exit 1 }'
  Assert-Case ($promoted.Diagnostic.stage_ledger.failed_stage -eq "profile configuration" -and $promoted.Diagnostic.stage_ledger.failure_classification -eq "powershell_error") "nonterminating error promoted by Stop retains the exact boundary"
  $exit = Run-Probe "identity ACL verification" 'exit 31'
  Assert-Case ($exit.Diagnostic.stage_ledger.last_entered_stage -eq "identity ACL verification" -and $exit.Diagnostic.stage_ledger.last_completed_stage -eq "bootstrap load" -and $exit.Diagnostic.stage_ledger.failure_classification -eq "unhandled_process_exit" -and $exit.Diagnostic.stage_ledger.process_exit_code -eq 31) "explicit nonzero exit retains the last entered and completed checkpoints without a child report"
  $zeroExit = Run-Probe "recipient validation" 'exit 0'
  Assert-Case ($zeroExit.Diagnostic.stage_ledger.failure_classification -eq "unhandled_process_exit" -and $zeroExit.Diagnostic.stage_ledger.expected_report_written -ceq $false) "explicit zero exit mid-stage does not imply completion or a report"
  $nativeAction = @'
try {
  & (Get-Process -Id $PID).Path -NoLogo -NoProfile -NonInteractive -Command 'exit 23'
  $nativeCode = $LASTEXITCODE
  $errorObject = [Exception]::new('PRIVATE-NATIVE-SENTINEL')
  $errorObject.Data['native_exit_code'] = $nativeCode
  throw $errorObject
} catch { Write-BackupCaughtCheckpoint -Record $_; exit 1 }
'@
  $native = Run-Probe "Docker dependency check" $nativeAction
  Assert-Case ($native.Diagnostic.stage_ledger.failure_classification -eq "native_failure" -and $native.Diagnostic.stage_ledger.failed_stage -eq "Docker dependency check") "real native nonzero exit plus existing exception lineage remains a native failure"
  $reportFailure = Run-Probe "child report write" 'Write-BackupCheckpoint -Stage "child report write" -State FAIL -Classification report_write_failed; exit 1'
  Assert-Case ($reportFailure.Diagnostic.stage_ledger.failure_classification -eq "report_write_failed" -and $reportFailure.Diagnostic.stage_ledger.expected_report_written -ceq $false) "report-writing failure remains visible without the report"

  $runtimeAction = "Import-Module '" + (Join-Path $PSScriptRoot "pc-first-backup-artifacts.psm1").Replace("'","''") + "' -Force`nWrite-BackupCheckpoint -Stage 'database encryption' -State ENTER`nexit 17"
  $runtime = Run-Probe "runtime initialization" $runtimeAction
  Assert-Case ($runtime.Diagnostic.stage_ledger.last_entered_stage -eq "database encryption" -and $runtime.Diagnostic.stage_ledger.process_exit_code -eq 17) "existing runtime operation allowlist is reused without a second stage authority"
  $unknownAction = 'Write-BackupCheckpoint -Stage "PRIVATE-UNKNOWN-STAGE" -State ENTER; [Console]::Out.WriteLine("VAYUJIT_BACKUP_STAGE=ENTER|PRIVATE-SPOOFED-STAGE|none|12|backup-pc-first.ps1"); exit 1'
  $unknown = Run-Probe "runtime initialization" $unknownAction
  Assert-Case ($unknown.Diagnostic.stage_ledger.last_entered_stage -eq "runtime initialization" -and ($unknown.Diagnostic | ConvertTo-Json -Depth 6) -notmatch 'PRIVATE-') "unknown stages are rejected by emitter and parent before persistence"

  $backupId=$runId.Substring(0,10)
  [System.IO.File]::WriteAllText((Join-Path $profile "disposable-profile.marker"),"vayujit-pc-disposable-certification-v1`nproject=vayujit-pc-cert-$backupId`nvolume_prefix=vayujit_pc_cert_$backupId`n")
  $actualReport = Join-Path $profile "backup-rehearsal.json"
  $scriptPath=Join-Path $PSScriptRoot "backup-pc-first.ps1"
  $actualCapture=Invoke-VayujitNativeCapture -FilePath $shellPath -WorkingDirectory $repo -Arguments @("-NoLogo","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",$scriptPath,"-DataRoot",$profile,"-DisposableCertification","-BackupReportPath",$actualReport)
  $actual=Get-VayujitBackupChildDiagnostic -LaunchSucceeded $true -ProcessExitCode $actualCapture.ExitCode -ExecutablePath $shellPath -ChildScriptPath $scriptPath -StdOut $actualCapture.StdOut -StdErr $actualCapture.StdErr -ReportPath $actualReport
  Assert-Case ($actual.stage_ledger.failed_stage -eq "profile files check" -and $actual.stage_ledger.last_entered_stage -eq "child report write" -and $actual.stage_ledger.last_completed_stage -eq "child report write" -and $actual.stage_ledger.expected_report_written -ceq $true) "real repository entry point pinpoints missing config then confirms bootstrap report writing before any Docker command"
  $resolved=Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode $actualCapture.ExitCode -ReportPath $actualReport
  Assert-Case ($resolved.Failure.failure_code -eq "backup_preflight_failed") "stage ledger does not replace the existing structured failure authority"

  $poison=@{classification='nonzero_exit_unclassified';stage_ledger=@{last_entered_stage='PRIVATE-KEY';last_completed_stage='PRIVATE-PASSWORD';failed_stage='PRIVATE-TOKEN';failure_classification='PRIVATE-CUSTOMER';source_file='PRIVATE-DATABASE-URL';source_line='PRIVATE-KEY';process_exit_code='PRIVATE-KEY';expected_report_written='PRIVATE-KEY';raw_stderr='PRIVATE-KEY'}}
  $saved=Write-VayujitBackupChildDiagnostic -Directory (Join-Path $root "retained") -BackupId $backupId -Diagnostic $poison
  $savedText=[System.IO.File]::ReadAllText($saved)
  Assert-Case ($savedText -notmatch 'PRIVATE-|raw_stderr') "nested ledger fields are re-allowlisted and raw data is never copied"
  $failureSaved=Write-VayujitBackupChildDiagnostic -Directory (Join-Path $root "retained-real") -BackupId $backupId -Diagnostic $exit.Diagnostic
  $profileFull=[System.IO.Path]::GetFullPath($profile)
  if (-not $profileFull.StartsWith($root+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw "Unsafe test cleanup target"}
  Remove-Item -LiteralPath $profileFull -Recurse -Force
  $persisted=Get-Content -LiteralPath $failureSaved -Raw|ConvertFrom-Json
  Assert-Case ($persisted.stage_ledger.last_entered_stage -eq "identity ACL verification" -and $persisted.stage_ledger.process_exit_code -eq 31 -and -not (Test-Path -LiteralPath $profileFull)) "parent-owned ledger survives complete disposable-profile removal"
  $result.examples=@{explicit_exit=$exit.Diagnostic;real_preflight=$actual;promoted_error=$promoted.Diagnostic;native_failure=$native.Diagnostic}
  $result.status="PASS"
} catch {
  $result.status="FAIL"
  $result.safe_error_category=[string]$_.CategoryInfo.Category
  $result.safe_error_line=$_.InvocationInfo.ScriptLineNumber
  if($result.failed -eq 0){$result.failed=1}
  throw "Stage ledger tests did not pass; inspect the sanitized test report."
} finally {
  $full=[System.IO.Path]::GetFullPath($root)
  if($full.StartsWith($tempBase.TrimEnd('\','/')+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -and [System.IO.Path]::GetFileName($full) -eq ("vayujit-stage-ledger-test-"+$runId)){
    if(Test-Path -LiteralPath $full){Remove-Item -LiteralPath $full -Recurse -Force}
    $result.cleanup="PASS"
  }else{$result.cleanup="FAIL";$result.status="FAIL"}
  $evidenceFull=Resolve-VayujitEvidencePath -Path $EvidencePath
  [System.IO.File]::WriteAllText($evidenceFull,((ConvertTo-Json -InputObject $result -Depth 9)+"`n"),[System.Text.UTF8Encoding]::new($false))
}
Write-Output "Stage ledger tests: $($result.passed) passed, $($result.failed) failed, $($result.skipped) skipped. No Docker or backup ran."
