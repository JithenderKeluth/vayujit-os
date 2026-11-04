param([string]$EvidencePath)
$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "pc-first-key-security.psm1") -Force
Import-Module (Join-Path $PSScriptRoot "pc-first-backup-artifacts.psm1") -Force
$shellPath = (Get-Process -Id $PID -ErrorAction Stop).Path
$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$runId = [guid]::NewGuid().ToString("N")
$root = Join-Path $tempBase ("vayujit-child-diagnostic-test-" + $runId)
$codeRoot = Join-Path $root "code\scripts"
$profileRoot = Join-Path $root "profile with spaces"
$reportPath = Join-Path $profileRoot "backup-rehearsal.json"
$rows = [System.Collections.Generic.List[object]]::new()
$result = [ordered]@{ scope = "non-Docker synthetic child startup/report tests only"; powershell_version = $PSVersionTable.PSVersion.ToString(); status = "RUNNING"; tests = $rows; passed = 0; failed = 0; skipped = 0; cleanup = "PENDING" }
if (-not $EvidencePath) { $EvidencePath = Join-Path $PSScriptRoot "..\tmp\pc-first-certification\child-startup-tests-$runId.json" }

function Assert-Case([bool]$Condition, [string]$Name) {
  $rows.Add([ordered]@{ name = $Name; status = $(if ($Condition) { "PASS" } else { "FAIL" }) })
  if (-not $Condition) { $result.failed++; throw "Child diagnostic regression assertion failed; inspect the safe test ledger." }
  $result.passed++
  Write-Output "PASS $Name"
}
function Write-Fixture([string]$Name, [string]$Source) {
  $file = Join-Path $codeRoot $Name
  [System.IO.File]::WriteAllText($file, $Source, [System.Text.UTF8Encoding]::new($true))
  return $file
}
function Run-Child([string]$Script, [string[]]$Extra = @()) {
  $capture = Invoke-VayujitNativeCapture -FilePath $shellPath -WorkingDirectory $root -Arguments (@("-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", $Script) + $Extra)
  $diagnostic = Get-VayujitBackupChildDiagnostic -LaunchSucceeded $true -ProcessExitCode $capture.ExitCode -ExecutablePath $shellPath -ChildScriptPath $Script -StdOut $capture.StdOut -StdErr $capture.StdErr
  return [pscustomobject]@{ Capture = $capture; Diagnostic = $diagnostic }
}

try {
  New-Item -ItemType Directory -Path $codeRoot, $profileRoot -Force | Out-Null
  $missingScript = Run-Child (Join-Path $codeRoot "not-present.ps1")
  Assert-Case ($missingScript.Capture.ExitCode -ne 0 -and $missingScript.Diagnostic.classification -eq "script_path_unavailable") "invalid child script path is diagnosed before script startup"

  $parseScript = Write-Fixture "parse-error.ps1" 'param([string]$Name) if ('
  $parse = Run-Child $parseScript
  Assert-Case ($parse.Capture.ExitCode -eq 1 -and $parse.Diagnostic.classification -eq "script_parse_failed" -and $parse.Diagnostic.powershell_error_id -eq "IfStatementMissingCondition" -and $parse.Diagnostic.source_line -ge 1 -and $parse.Diagnostic.stderr_captured -and -not $parse.Diagnostic.script_started_token_observed) "real child parse failure retains safe source location error identifier and exit"

  $bindingScript = Write-Fixture "binding.ps1" @'
[CmdletBinding()]
param([int]$Count)
[Console]::Out.WriteLine('VAYUJIT_BACKUP_CHILD_STARTED=1')
'@
  $binding = Run-Child $bindingScript @("-NotAParameter", "secret-must-not-leak")
  Assert-Case ($binding.Capture.ExitCode -eq 1 -and $binding.Diagnostic.classification -eq "argument_binding_failed" -and -not $binding.Diagnostic.script_started_token_observed) "real argument binding failure is diagnosed before body execution"
  $restricted = Invoke-VayujitNativeCapture -FilePath $shellPath -Arguments @("-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Restricted", "-File", $bindingScript)
  $restrictedDiagnostic = Get-VayujitBackupChildDiagnostic -LaunchSucceeded $true -ProcessExitCode $restricted.ExitCode -ExecutablePath $shellPath -ChildScriptPath $bindingScript -StdOut $restricted.StdOut -StdErr $restricted.StdErr
  Assert-Case ($restricted.ExitCode -ne 0 -and $restrictedDiagnostic.classification -eq "execution_policy_rejected" -and -not $restrictedDiagnostic.script_started_token_observed) "process-scoped restricted policy is diagnosed without changing machine or user policy"

  $dependencyScript = Write-Fixture "dependency.ps1" @'
$ErrorActionPreference = 'Stop'
[Console]::Out.WriteLine('VAYUJIT_BACKUP_CHILD_STARTED=1')
& '__vayujit_nonexistent_test_dependency__'
'@
  $dependency = Run-Child $dependencyScript
  Assert-Case ($dependency.Capture.ExitCode -eq 1 -and $dependency.Diagnostic.classification -eq "dependency_unavailable" -and $dependency.Diagnostic.script_started_token_observed) "missing executable dependency retains safe command classification"

  $importScript = Write-Fixture "import.ps1" @'
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'not-present-module.psm1') -Force
'@
  $import = Run-Child $importScript
  Assert-Case ($import.Capture.ExitCode -eq 1 -and $import.Diagnostic.classification -eq "module_import_failed") "missing module diagnostic excludes module paths and import text"

  $launchFailed = $false
  $missingExe = Join-Path $root "not-a-shell.exe"
  try { Invoke-VayujitNativeCapture -FilePath $missingExe -Arguments @() | Out-Null } catch { $launchFailed = $true }
  $launchDiagnostic = Get-VayujitBackupChildDiagnostic -LaunchSucceeded $false -ExecutablePath $missingExe -ChildScriptPath $bindingScript
  Assert-Case ($launchFailed -and $launchDiagnostic.classification -eq "executable_unavailable" -and $null -eq $launchDiagnostic.process_exit_code) "missing child executable is distinguished from a nonzero launched process"

  $exitScript = Write-Fixture "nonzero.ps1" "[Console]::Error.WriteLine('password=never-log-this'); exit 29"
  $nonzero = Run-Child $exitScript
  $missing = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode $nonzero.Capture.ExitCode -ReportPath $reportPath
  Assert-Case ($nonzero.Capture.ExitCode -eq 29 -and $missing.Failure.failure_code -eq "backup_subprocess_nonzero_exit" -and $missing.Failure.child_report_status -eq "MISSING" -and $nonzero.Diagnostic.classification -eq "nonzero_exit_unclassified") "genuine nonzero exit without a report remains failed with captured-stderr metadata"
  $zeroScript = Write-Fixture "zero-warning.ps1" "[Console]::Error.WriteLine('harmless warning'); exit 0"
  $zero = Run-Child $zeroScript
  $zeroMissing = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 0 -ReportPath $reportPath
  Assert-Case ($zero.Diagnostic.classification -eq "completed" -and $zero.Diagnostic.stderr_captured -and $zeroMissing.Failure.failure_code -eq "backup_report_missing") "zero exit plus warning is not a native failure but cannot pass without a child report"

  $backupId = $runId.Substring(0, 10)
  [System.IO.File]::WriteAllText((Join-Path $profileRoot "disposable-profile.marker"), "vayujit-pc-disposable-certification-v1`nproject=vayujit-pc-cert-$backupId`nvolume_prefix=vayujit_pc_cert_$backupId`n")
  Copy-Item -LiteralPath (Join-Path $PSScriptRoot "backup-pc-first.ps1") -Destination $codeRoot
  Copy-Item -LiteralPath (Join-Path $PSScriptRoot "pc-first-backup-bootstrap.ps1") -Destination $codeRoot
  $actualScript = Join-Path $codeRoot "backup-pc-first.ps1"
  $actual = Run-Child $actualScript @("-DataRoot", $profileRoot, "-DisposableCertification", "-BackupDestination", (Join-Path $root "destination"), "-BackupReportPath", $reportPath)
  $actualResolution = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode $actual.Capture.ExitCode -ReportPath $reportPath
  Assert-Case ($actual.Capture.ExitCode -eq 1 -and $actualResolution.Failure.failure_code -eq "backup_initialization_failed" -and $actual.Diagnostic.script_started_token_observed) "actual backup startup writes a structured import failure before Docker preflight"
  $repoScript = Join-Path $PSScriptRoot "backup-pc-first.ps1"
  $preflightPath = Join-Path $profileRoot "repository-preflight.json"
  $preflight = Run-Child $repoScript @("-DataRoot", $profileRoot, "-DisposableCertification", "-BackupReportPath", $preflightPath)
  $preflightResolution = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode $preflight.Capture.ExitCode -ReportPath $preflightPath
  Assert-Case ($preflight.Capture.ExitCode -eq 1 -and $preflightResolution.Failure.failure_code -eq "backup_preflight_failed" -and $preflight.Diagnostic.script_started_token_observed) "unmodified repository backup entry point reports missing disposable config before any Docker or age invocation"

  # Force failure in the formerly unguarded boundary initializer itself.
  $bootstrapCopy = Join-Path $codeRoot "pc-first-backup-bootstrap.ps1"
  $bootstrapSource = [System.IO.File]::ReadAllText($bootstrapCopy)
  [System.IO.File]::WriteAllText($bootstrapCopy, ($bootstrapSource + @'

function Initialize-VayujitBackupReportBoundary {
  param($DisposableCertification, $DataRoot, $BackupReportPath, $RepositoryRoot)
  throw 'PRIVATE-INITIALIZER-SENTINEL'
}
'@))
  $init = Run-Child $actualScript @("-DataRoot", $profileRoot, "-DisposableCertification", "-BackupReportPath", (Join-Path $profileRoot "init.json"))
  Assert-Case ($init.Capture.ExitCode -eq 1 -and $init.Diagnostic.classification -eq "initialization_failed" -and $init.Capture.StdErr -notmatch "PRIVATE-INITIALIZER-SENTINEL") "initializer failure now reaches a safe startup boundary token"
  [System.IO.File]::WriteAllText($bootstrapCopy, $bootstrapSource)

  $writeScript = Write-Fixture "write-failure.ps1" @'
param([string]$ReportPath)
. (Join-Path $PSScriptRoot 'pc-first-backup-bootstrap.ps1')
$failure = New-VayujitBootstrapFailureReport -BackupId 'test-child' -FailureCode 'backup_initialization_failed' -FailureOperation 'backup child initialization'
if (-not (Write-VayujitBootstrapFailureReport -ReportPath $ReportPath -Report $failure)) {
  [Console]::Out.WriteLine('VAYUJIT_BACKUP_CHILD_BOUNDARY=backup_evidence_report_write_failed')
  exit 1
}
exit 0
'@
  $lockedPath = Join-Path $profileRoot "locked-report.json"
  $locked = [System.IO.File]::Open($lockedPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
  try { $writeFailure = Run-Child $writeScript @("-ReportPath", $lockedPath) } finally { $locked.Dispose() }
  Assert-Case ($writeFailure.Capture.ExitCode -eq 1 -and $writeFailure.Diagnostic.classification -eq "report_write_failed") "unwritable child report produces parent diagnostic without raw filesystem error"

  $goodReport = Join-Path $profileRoot "good-failure.json"
  $good = Run-Child $writeScript @("-ReportPath", $goodReport)
  $resolved = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode $good.Capture.ExitCode -ReportPath $goodReport
  Assert-Case ($good.Capture.ExitCode -eq 0 -and $resolved.Status -eq "FAIL" -and $resolved.Failure.failure_code -eq "backup_initialization_failed") "valid structured failure report wins over process zero exit"

  $passScript = Write-Fixture "pass-contract.ps1" @'
param([string]$ReportPath)
$report = @{status='PASS'; backup_id='test-parser-only'; profile='marker_protected_disposable_only'; artifacts_are_not_business_backups=$true; artifact_manifest=@(@{name='synthetic-test.age'}); destination_independence='UNVERIFIED'; encrypted_artifact_header=$true; wrong_key_rejected=$true; corrupted_ciphertext_rejected=$true; canonical_records_restored_and_compared=$true; financial_precision_verified=$true; media_restored_and_checksums_verified=$true; source_canonical_records_unchanged=$true; backup_duration_seconds=1; restore_duration_seconds=1}
[System.IO.File]::WriteAllText($ReportPath, ($report | ConvertTo-Json -Depth 4))
'@
  $passPath = Join-Path $profileRoot "pass-contract.json"
  $pass = Run-Child $passScript @("-ReportPath", $passPath)
  $passResolved = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode $pass.Capture.ExitCode -ReportPath $passPath
  Assert-Case ($passResolved.Status -eq "PASS" -and $passResolved.Report.destination_independence -eq "UNVERIFIED") "synthetic successful child-report contract propagates without upgrading physical independence"

  $secret = "AGE-SECRET-KEY-PRIVATE-SENTINEL password=PRIVATE-PASSWORD postgresql://user:PRIVATE-DATABASE-SECRET@host/db token=PRIVATE-TOKEN customer=PRIVATE-CONTENT"
  $sanitized = Get-VayujitBackupChildDiagnostic -LaunchSucceeded $true -ProcessExitCode 1 -ExecutablePath $shellPath -ChildScriptPath $exitScript -StdOut $secret -StdErr $secret
  $sanitizedText = ConvertTo-Json -InputObject $sanitized -Depth 4
  Assert-Case ($sanitizedText -notmatch 'PRIVATE-|AGE-SECRET|postgresql|password=|token=|customer=') "unknown private keys credentials connection URLs tokens and customer text are entirely omitted"
  $malicious = @{classification='nonzero_exit_unclassified'; safe_stderr_summary=$secret; powershell_error_id=$secret; engine=$secret; source_line=$secret; StdErr=$secret; raw_output_persisted=$true; process_exit_code=19; stderr_captured=$true}
  $saved = Write-VayujitBackupChildDiagnostic -Directory (Join-Path $root "retained") -BackupId $backupId -Diagnostic $malicious
  $savedText = [System.IO.File]::ReadAllText($saved)
  $savedObject = $savedText | ConvertFrom-Json
  Assert-Case ($savedText -notmatch 'PRIVATE-|AGE-SECRET|postgresql|password=|token=|customer=' -and $null -eq $savedObject.PSObject.Properties['StdErr'] -and $savedObject.process_exit_code -eq 19) "persistent parent diagnostic revalidates every field rather than trusting supplied text"
  $persistFailed = $false
  try { Write-VayujitBackupChildDiagnostic -Directory $lockedPath -BackupId $backupId -Diagnostic $sanitized | Out-Null } catch { $persistFailed = $_.Exception.Message -eq 'backup_parent_diagnostic_write_failed' }
  Assert-Case $persistFailed "unwritable parent diagnostic destination fails with a fixed safe error"

  $argvScript = Write-Fixture ("argv-" + [char]0x03A9 + ".ps1") @'
param([string]$Value)
$expected = 'unicode-' + [char]0x03A9 + ' path with spaces\'
# Compare inside the child: PS 5.1 console encoding is not necessarily UTF-8.
# The assertion result is ASCII, so stdout transcoding cannot fake an argv loss.
[Console]::Out.Write((@{argument_exact=($Value -ceq $expected); cwd=[Environment]::CurrentDirectory} | ConvertTo-Json -Compress))
'@
  $expectedArgument = "unicode-" + [char]0x03A9 + " path with spaces\"
  $argv = Run-Child $argvScript @("-Value", $expectedArgument)
  $argvObject = $argv.Capture.StdOut | ConvertFrom-Json
  Assert-Case ($argv.Capture.ExitCode -eq 0 -and $argvObject.argument_exact -eq $true -and $argvObject.cwd -eq $root) "Windows argument quoting Unicode script path and argument trailing slash and explicit working directory survive the real child launch"

  # Simulate disposable-profile deletion only after retaining the safe record.
  $resolvedProfile = [System.IO.Path]::GetFullPath($profileRoot)
  if (-not $resolvedProfile.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe test cleanup target." }
  Remove-Item -LiteralPath $resolvedProfile -Recurse -Force
  Assert-Case ((Test-Path -LiteralPath $saved -PathType Leaf) -and -not (Test-Path -LiteralPath $resolvedProfile)) "safe diagnostic remains outside the removed disposable profile"
  $result.examples = @{parse=$parse.Diagnostic;binding=$binding.Diagnostic;policy=$restrictedDiagnostic;unwritable_child_report=$writeFailure.Diagnostic;missing_report_nonzero=$nonzero.Diagnostic;repository_preflight=$preflightResolution.Failure}
  $result.status = "PASS"
} catch {
  $result.status = "FAIL"
  $result.harness_error_category = [string]$_.CategoryInfo.Category
  $result.harness_error_line = $_.InvocationInfo.ScriptLineNumber
  if ($result.failed -eq 0) { $result.failed = 1; $rows.Add(@{name='test harness operation';status='FAIL';message='Raw diagnostic output omitted; no backup certification performed.'}) }
  throw "Non-Docker child diagnostic tests did not pass. Inspect the safe evidence file."
} finally {
  $resolvedRoot = [System.IO.Path]::GetFullPath($root)
  $expectedPrefix = $tempBase.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  if ($resolvedRoot.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase) -and [System.IO.Path]::GetFileName($resolvedRoot) -eq ("vayujit-child-diagnostic-test-" + $runId)) {
    if (Test-Path -LiteralPath $resolvedRoot) { Remove-Item -LiteralPath $resolvedRoot -Recurse -Force }
    $result.cleanup = "PASS"
  } else { $result.cleanup = "FAIL"; $result.status = "FAIL" }
  $resolvedEvidence = Resolve-VayujitEvidencePath -Path $EvidencePath
  [System.IO.File]::WriteAllText($resolvedEvidence, ((ConvertTo-Json -InputObject $result -Depth 6) + "`n"), [System.Text.UTF8Encoding]::new($false))
}
Write-Output "Child diagnostic regressions: $($result.passed) passed, $($result.failed) failed, $($result.skipped) skipped. No Docker or backup was used."
