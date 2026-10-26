$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "pc-first-backup-artifacts.psm1") -Force
Import-Module (Join-Path $PSScriptRoot "pc-first-key-security.psm1") -Force
. (Join-Path $PSScriptRoot "pc-first-backup-bootstrap.ps1")
$passed = 0
$root = Join-Path ([System.IO.Path]::GetTempPath()) ("vayujit-backup-artifact-test-" + [guid]::NewGuid().ToString("N"))
$bootstrapProfile = $null
$bootstrapMissingMarkerProfile = $null
$bootstrapScriptBase = $null
$actual = Join-Path $root "actual"
$wrong = Join-Path $root "wrong"
New-Item -ItemType Directory -Path $actual, $wrong -Force | Out-Null

function Assert-Regression([bool]$Condition, [string]$Name) {
  if (-not $Condition) { throw "FAIL $Name" }
  $script:passed++
  Write-Output "PASS $Name"
}

function Assert-FailsWith([scriptblock]$Action, [string]$ExpectedCode, [string]$Name) {
  $caught = $null
  try { & $Action | Out-Null } catch { $caught = $_.Exception.Message }
  Assert-Regression ($caught -eq $ExpectedCode) $Name
}

try {
  $archivePath = Join-Path $actual "media.zip"
  $manifestPath = Join-Path $actual "media.json"
  [System.IO.File]::WriteAllBytes($archivePath, [byte[]](80, 75, 3, 4, 1))
  [System.IO.File]::WriteAllText($manifestPath, '{"files":[{"path":"image.png"}]}')

  $artifacts = Get-VayujitMediaBackupArtifacts -OutputDirectory $actual
  Assert-Regression ($artifacts.ArchivePath -eq [System.IO.Path]::GetFullPath($archivePath)) "stable CLI media.zip/media.json contract resolves"
  Assert-Regression ($artifacts.ArchiveLength -gt 0 -and $artifacts.ManifestLength -gt 0) "media archive and manifest must be nonempty"

  Assert-FailsWith { Get-VayujitMediaBackupArtifacts -OutputDirectory $wrong } "media_backup_archive_missing" "incorrect output directory is rejected"
  Remove-Item -LiteralPath $archivePath -Force
  Assert-FailsWith { Get-VayujitMediaBackupArtifacts -OutputDirectory $actual } "media_backup_archive_missing" "missing media archive fails closed"

  [System.IO.File]::WriteAllBytes($archivePath, [byte[]]@())
  Assert-FailsWith { Get-VayujitMediaBackupArtifacts -OutputDirectory $actual } "media_backup_archive_empty" "empty media archive fails closed"

  [System.IO.File]::WriteAllBytes($archivePath, [byte[]](80, 75, 3, 4, 1))
  Remove-Item -LiteralPath $manifestPath -Force
  Assert-FailsWith { Get-VayujitMediaBackupArtifacts -OutputDirectory $actual } "media_backup_manifest_missing" "missing media manifest fails closed"

  [System.IO.File]::WriteAllText($manifestPath, "")
  Assert-FailsWith { Get-VayujitMediaBackupArtifacts -OutputDirectory $actual } "media_backup_manifest_empty" "empty media manifest fails closed"

  $dumpPath = Join-Path $actual "database.dump"
  Assert-FailsWith { Assert-VayujitBackupArtifact -Path $dumpPath -MissingFailureCode "database_dump_artifact_missing" -EmptyFailureCode "database_dump_artifact_empty" } "database_dump_artifact_missing" "missing database dump fails closed"
  [System.IO.File]::WriteAllBytes($dumpPath, [byte[]]@())
  Assert-FailsWith { Assert-VayujitBackupArtifact -Path $dumpPath -MissingFailureCode "database_dump_artifact_missing" -EmptyFailureCode "database_dump_artifact_empty" } "database_dump_artifact_empty" "empty database dump fails closed"

  $encryptionFailure = $null
  try {
    Invoke-VayujitBackupStage -Operation "database encryption" -FailureCode "database_encryption_failed" -Action {
      throw "AGE-SECRET-KEY-TEST-PRIVATE customer-sensitive-encryption-detail"
    } | Out-Null
  } catch { $encryptionFailure = $_.Exception }
  Assert-Regression ($encryptionFailure.Message -eq "database_encryption_failed") "encryption exception is reduced to safe stage code"
  Assert-Regression ($encryptionFailure.Data["failure_operation"] -eq "database encryption" -and $encryptionFailure.Data["failure_code"] -eq "database_encryption_failed") "encryption exception retains operation and code"
  Assert-Regression ($encryptionFailure.Message -notmatch "AGE-SECRET|customer-sensitive") "encryption exception excludes secrets and sensitive output"

  $verificationFailure = $null
  try {
    Invoke-VayujitBackupStage -Operation "media decryption verification" -FailureCode "media_decryption_verification_failed" -Action {
      [pscustomobject]@{ ExitCode = 41; StdErr = "private-output-sentinel"; StdOut = "customer-content-sentinel" }
    } | Out-Null
  } catch { $verificationFailure = $_.Exception }
  Assert-Regression ($verificationFailure.Data["failure_operation"] -eq "media decryption verification") "verification exception retains operation"
  Assert-Regression ($verificationFailure.Data["native_exit_code"] -eq 41) "verification exception retains native exit code"
  Assert-Regression ($verificationFailure.Message -eq "media_decryption_verification_failed") "verification exception reports only its safe code"

  $verificationThrownException = $null
  try {
    Invoke-VayujitBackupStage -Operation "independent restore report parsing" -FailureCode "restore_report_invalid" -Action {
      throw "customer-restore-payload AGE-SECRET-KEY-DO-NOT-REPORT"
    } | Out-Null
  } catch { $verificationThrownException = $_.Exception }
  Assert-Regression ($verificationThrownException.Message -eq "restore_report_invalid") "verification exception is reduced to its safe stage code"
  Assert-Regression ($verificationThrownException.Data["failure_operation"] -eq "independent restore report parsing") "verification exception retains its operation"
  Assert-Regression ($verificationThrownException.Message -notmatch "customer-restore|AGE-SECRET") "verification exception excludes sensitive data"

  $failureReport = New-VayujitBackupFailureReport -BackupId "disposable-test" -FailureOperation $verificationFailure.Data["failure_operation"] -FailureCode $verificationFailure.Data["failure_code"] -NativeExitCode $verificationFailure.Data["native_exit_code"]
  $failureReport = ($failureReport | ConvertTo-Json -Depth 5) | ConvertFrom-Json
  $certification = [ordered]@{ backup_restore = [ordered]@{ status = "NOT_RUN" }; error = $null }
  Set-VayujitDisposableBackupFailure -Certification $certification -BackupFailure $failureReport
  $reportJson = $certification | ConvertTo-Json -Depth 5
  Assert-Regression ($certification.backup_restore.failure_code -eq "media_decryption_verification_failed" -and $certification.backup_restore.native_exit_code -eq 41) "structured backup failure reaches disposable certification"
  Assert-Regression ($certification.error -match "media decryption verification.*native exit code 41") "certification error identifies safe failing operation and exit"
  Assert-Regression ($reportJson -notmatch "private-output-sentinel|customer-content-sentinel|AGE-SECRET-KEY") "failure report excludes stderr, customer content, and private keys"

  $dockerFailure = New-VayujitBackupFailureReport -BackupId "disposable-test" -FailureOperation "PostgreSQL dump creation" -FailureCode "database_dump_failed" -NativeExitCode 23 -DockerExitCode 23
  $dockerFailureJson = $dockerFailure | ConvertTo-Json -Depth 5
  Assert-Regression ($dockerFailure.docker_exit_code -eq 23 -and $dockerFailure.failure_code -eq "database_dump_failed") "Docker failure keeps the stage-specific code and Docker exit code"
  Assert-Regression ($dockerFailureJson -notmatch "stderr|stdout|secret|customer") "Docker failure report contains no raw process output"
  $dockerCertification = [ordered]@{ backup_restore = $null; error = $null }
  Set-VayujitDisposableBackupFailure -Certification $dockerCertification -BackupFailure $dockerFailure
  Assert-Regression ($dockerCertification.error -match "PostgreSQL dump creation.*Docker exit code 23") "disposable error identifies the Docker exit code distinctly"

  $untrustedFailure = [pscustomobject]@{
    backup_id = "C:\sensitive\AGE-SECRET-KEY-DO-NOT-REPORT"
    status = "FAIL"
    failure_operation = "age output AGE-SECRET-KEY-DO-NOT-REPORT"
    failure_code = "database_encryption_failed"
    native_exit_code = 7
    docker_exit_code = $null
    stderr = "customer-content-DO-NOT-REPORT"
    stdout = "private-output-DO-NOT-REPORT"
    credential = "credential-DO-NOT-REPORT"
  }
  $sanitizedCertification = [ordered]@{ backup_restore = $null; error = $null }
  Set-VayujitDisposableBackupFailure -Certification $sanitizedCertification -BackupFailure $untrustedFailure
  $sanitizedJson = $sanitizedCertification | ConvertTo-Json -Depth 5
  Assert-Regression ($sanitizedCertification.backup_restore.failure_operation -eq "backup stage unclassified" -and $sanitizedCertification.backup_restore.backup_id -eq "unavailable") "parent report whitelists safe structured fields"
  Assert-Regression ($sanitizedJson -notmatch "AGE-SECRET|customer-content|private-output|credential-DO-NOT-REPORT|C:\\\\sensitive") "untrusted backup report text cannot leak into certification"

  $childReports = Join-Path $root "child-reports"
  New-Item -ItemType Directory -Path $childReports -Force | Out-Null
  $childReportPath = Join-Path $childReports "backup.json"
  $childFailure = New-VayujitBackupFailureReport -BackupId "20261022T120000Z-ab12cd34ef56" -FailureOperation "database encryption" -FailureCode "database_encryption_failed" -NativeExitCode 37 -CleanupFailure "worker_restart_not_healthy"
  [System.IO.File]::WriteAllText($childReportPath, (($childFailure | ConvertTo-Json -Depth 5) + "`n"))
  $childResolution = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 1 -ReportPath $childReportPath
  Assert-Regression ($childResolution.Status -eq "FAIL" -and $childResolution.Failure.failure_code -eq "database_encryption_failed" -and $childResolution.Failure.failure_operation -eq "database encryption") "valid child failure stage is preserved across nonzero process exit"
  Assert-Regression ($childResolution.Failure.native_exit_code -eq 37 -and $childResolution.Failure.subprocess_exit_code -eq 1 -and $childResolution.Failure.cleanup_failure -eq "worker_restart_not_healthy") "child native exit, process exit, and recovery failure all propagate"
  $reportFinalizeFailure = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 1 -ReportPath $childReportPath -BootstrapFailureCode "backup_evidence_report_write_failed"
  Assert-Regression ($reportFinalizeFailure.Failure.failure_code -eq "database_encryption_failed" -and $reportFinalizeFailure.Failure.cleanup_failure -match "backup_evidence_report_write_failed") "report finalization failure does not erase a valid stage-specific child failure"
  $childCertification = [ordered]@{ backup_restore = $null; error = $null }
  Set-VayujitDisposableBackupFailure -Certification $childCertification -BackupFailure $childResolution.Failure
  Assert-Regression ($childCertification.backup_restore.failure_code -eq "database_encryption_failed" -and $childCertification.backup_restore.native_exit_code -eq 37 -and $childCertification.backup_restore.subprocess_exit_code -eq 1) "parent certification keeps child failure lineage"
  Assert-Regression ($childCertification.error -match "Recovery failure: worker_restart_not_healthy") "parent error summary calls out failed service recovery"

  $missingChildPath = Join-Path $childReports "missing.json"
  $missingAfterExit = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 9 -ReportPath $missingChildPath
  Assert-Regression ($missingAfterExit.Failure.failure_code -eq "backup_subprocess_nonzero_exit" -and $missingAfterExit.Failure.child_report_status -eq "MISSING" -and $missingAfterExit.Failure.subprocess_exit_code -eq 9) "nonzero child exit without a report is distinguished"
  $missingAfterSuccess = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 0 -ReportPath $missingChildPath
  Assert-Regression ($missingAfterSuccess.Failure.failure_code -eq "backup_report_missing") "zero-exit child with no report is distinguished"
  $launchFailure = Resolve-VayujitBackupChildReport -LaunchSucceeded $false -ProcessExitCode $null -ReportPath $missingChildPath
  Assert-Regression ($launchFailure.Failure.failure_code -eq "backup_subprocess_launch_failed") "child process launch failure is distinguished"

  $invalidJsonPath = Join-Path $childReports "invalid.json"
  [System.IO.File]::WriteAllText($invalidJsonPath, '{invalid-json AGE-SECRET-KEY-DO-NOT-REPORT')
  $invalidJson = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 1 -ReportPath $invalidJsonPath
  Assert-Regression ($invalidJson.Failure.failure_code -eq "backup_report_invalid_json" -and $invalidJson.Failure.child_report_status -eq "INVALID_JSON") "invalid child JSON is distinguished without exposing its content"

  $invalidSchemaPath = Join-Path $childReports "schema.json"
  [System.IO.File]::WriteAllText($invalidSchemaPath, '{"status":"FAIL","backup_id":"unsafe/path","failure_code":"not_allowlisted","failure_operation":"secret output"}')
  $invalidSchema = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 1 -ReportPath $invalidSchemaPath
  Assert-Regression ($invalidSchema.Failure.failure_code -eq "backup_report_schema_invalid" -and $invalidSchema.Failure.child_report_status -eq "SCHEMA_INVALID") "unsafe or incomplete child schema is rejected with a safe code"

  $validPassPath = Join-Path $childReports "pass.json"
  $validPass = [ordered]@{
    status = "PASS"; profile = "marker_protected_disposable_only"; artifacts_are_not_business_backups = $true
    backup_id = "20261022T120000Z-ab12cd34ef56"; artifact_manifest = @(@{ name = "database.age" })
    destination_independence = "UNVERIFIED"; encrypted_artifact_header = $true; wrong_key_rejected = $true
    corrupted_ciphertext_rejected = $true; canonical_records_restored_and_compared = $true
    financial_precision_verified = $true; media_restored_and_checksums_verified = $true
    source_canonical_records_unchanged = $true; backup_duration_seconds = 5.25; restore_duration_seconds = 3.5
  }
  [System.IO.File]::WriteAllText($validPassPath, (($validPass | ConvertTo-Json -Depth 5) + "`n"))
  $passResolution = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 0 -ReportPath $validPassPath
  Assert-Regression ($passResolution.Status -eq "PASS" -and $passResolution.Report.backup_id -eq $validPass.backup_id) "valid completed child rehearsal report is accepted"
  $recoveryFailedPass = $validPass | ConvertTo-Json -Depth 5 | ConvertFrom-Json
  $recoveryFailedPass = Set-VayujitBackupRecoveryFailure -Report $recoveryFailedPass -CleanupFailure "worker_restart_not_healthy"
  $recoveryFailedPath = Join-Path $childReports "recovery-failed-after-backup.json"
  [System.IO.File]::WriteAllText($recoveryFailedPath, (($recoveryFailedPass | ConvertTo-Json -Depth 6) + "`n"))
  $recoveryFailedResolution = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 1 -ReportPath $recoveryFailedPath
  Assert-Regression ($recoveryFailedPass.status -eq "FAIL" -and $recoveryFailedPass.failure_code -eq "service_recovery_failed" -and $recoveryFailedPass.failure_operation -eq "application service recovery") "post-backup recovery failure receives an explicit canonical failure stage"
  Assert-Regression ($recoveryFailedResolution.Failure.failure_code -eq "service_recovery_failed" -and $recoveryFailedResolution.Failure.cleanup_failure -eq "worker_restart_not_healthy" -and $recoveryFailedResolution.Failure.destination_independence -eq "UNVERIFIED") "post-backup recovery failure is schema-valid and retains cleanup and destination evidence"
  $sameDiskPass = [ordered]@{}
  foreach ($entry in $validPass.GetEnumerator()) { $sameDiskPass[$entry.Key] = $entry.Value }
  $sameDiskPass.destination_independence = "SAME_PHYSICAL_DISK"
  $sameDiskPassPath = Join-Path $childReports "same-disk-pass.json"
  [System.IO.File]::WriteAllText($sameDiskPassPath, (($sameDiskPass | ConvertTo-Json -Depth 5) + "`n"))
  $sameDiskResolution = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 0 -ReportPath $sameDiskPassPath
  Assert-Regression ($sameDiskResolution.Status -eq "PASS" -and $sameDiskResolution.Report.destination_independence -eq "SAME_PHYSICAL_DISK") "completed disposable rehearsal remains valid when disk independence is not established"
  $passWithErrorExit = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 1 -ReportPath $validPassPath
  Assert-Regression ($passWithErrorExit.Failure.failure_code -eq "backup_subprocess_nonzero_exit") "child PASS report cannot override a nonzero process exit"
  $passWithReportWriteFailure = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 1 -ReportPath $validPassPath -BootstrapFailureCode "backup_evidence_report_write_failed"
  Assert-Regression ($passWithReportWriteFailure.Status -eq "FAIL" -and $passWithReportWriteFailure.Failure.failure_code -eq "backup_evidence_report_write_failed" -and $passWithReportWriteFailure.Failure.child_report_status -eq "PASS") "stale PASS report cannot override a report-finalization failure"

  $testPowerShellPath = (Get-Process -Id $PID -ErrorAction Stop).Path
  $nativeCapture = Invoke-VayujitNativeCapture -FilePath $testPowerShellPath -Arguments @(
    "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
    "[Console]::Error.WriteLine('native-warning-sentinel'); [Console]::Out.WriteLine('native-output-sentinel'); exit 0"
  )
  Assert-Regression ($nativeCapture.ExitCode -eq 0 -and $nativeCapture.StdErr -match "native-warning-sentinel" -and $nativeCapture.StdOut -match "native-output-sentinel") "isolated child invocation captures stderr/stdout without making successful warning output fatal"
  $nativeNonzero = Invoke-VayujitNativeCapture -FilePath $testPowerShellPath -Arguments @("-NoLogo", "-NoProfile", "-NonInteractive", "-Command", "[Console]::Error.WriteLine('safe-test-warning'); exit 29")
  Assert-Regression ($nativeNonzero.ExitCode -eq 29 -and $nativeNonzero.StdErr -match "safe-test-warning") "isolated child invocation retains a genuine nonzero process exit"
  $testSecretVariable = "VAYUJIT_PC_CERT_TEST_SECRET"
  $priorTestSecret = [Environment]::GetEnvironmentVariable($testSecretVariable, "Process")
  try {
    [Environment]::SetEnvironmentVariable($testSecretVariable, "DO-NOT-INHERIT-SENTINEL", "Process")
    $environmentCheck = Invoke-VayujitNativeCapture -FilePath $testPowerShellPath -Arguments @(
      "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
      "if ([Environment]::GetEnvironmentVariable('VAYUJIT_PC_CERT_TEST_SECRET')) { [Console]::Out.Write('present') } else { [Console]::Out.Write('absent') }"
    ) -RemoveEnvironmentVariables @($testSecretVariable)
    Assert-Regression ($environmentCheck.ExitCode -eq 0 -and $environmentCheck.StdOut -eq "absent") "sensitive parent environment values can be excluded from child processes"
  } finally {
    [Environment]::SetEnvironmentVariable($testSecretVariable, $priorTestSecret, "Process")
  }

  $childFixtureScript = Join-Path $childReports "child-fixture.ps1"
  $childFixtureSource = @'
param([string]$ReportPath)
$childReport = [ordered]@{ status = "FAIL"; backup_id = "child-fixture-01"; failure_code = "database_encryption_failed"; failure_operation = "database encryption"; native_exit_code = 31; docker_exit_code = $null; cleanup_failure = "worker_restart_failed"; destination_independence = "UNVERIFIED"; recovery_hint = "safe" }
[System.IO.File]::WriteAllText($ReportPath, (($childReport | ConvertTo-Json -Depth 5) + "`n"))
[Console]::Error.WriteLine("AGE-SECRET-KEY-CHILD-OUTPUT-MUST-NOT-PROPAGATE")
exit 19
'@
  [System.IO.File]::WriteAllText($childFixtureScript, $childFixtureSource)
  $fixtureReportPath = Join-Path $childReports "child-result.json"
  $childProcess = Invoke-VayujitNativeCapture -FilePath $testPowerShellPath -Arguments @("-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", $childFixtureScript, $fixtureReportPath)
  $fixtureResolution = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode $childProcess.ExitCode -ReportPath $fixtureReportPath
  $fixtureCertification = [ordered]@{ backup_restore = $null; error = $null }
  Set-VayujitDisposableBackupFailure -Certification $fixtureCertification -BackupFailure $fixtureResolution.Failure
  $fixtureCertificationJson = $fixtureCertification | ConvertTo-Json -Depth 5
  $fixtureProcessExit = $fixtureCertification.backup_restore.subprocess_exit_code
  Assert-Regression ($childProcess.ExitCode -eq 19 -and $fixtureResolution.Failure.failure_code -eq "database_encryption_failed" -and $fixtureResolution.Failure.native_exit_code -eq 31) "child process report reaches parent with stage code despite a nonzero child exit"
  Assert-Regression ($fixtureProcessExit -eq 19 -and $fixtureCertification.backup_restore.cleanup_failure -eq "worker_restart_failed") "child process exit and worker recovery failure reach certification"
  Assert-Regression ($childProcess.StdErr -match "AGE-SECRET-KEY-CHILD-OUTPUT-MUST-NOT-PROPAGATE" -and $fixtureCertificationJson -notmatch "AGE-SECRET-KEY-CHILD-OUTPUT-MUST-NOT-PROPAGATE") "captured sensitive-looking stderr is not copied into certification"

  $bootstrapId = [guid]::NewGuid().ToString("N").Substring(0, 10)
  $bootstrapProfile = Join-Path ([System.IO.Path]::GetTempPath()) ("vayujit-backup-bootstrap-profile-" + $bootstrapId)
  $bootstrapScriptBase = Join-Path ([System.IO.Path]::GetTempPath()) ("vayujit-backup-bootstrap-scripts-" + $bootstrapId)
  $bootstrapScripts = Join-Path $bootstrapScriptBase "scripts"
  $bootstrapConfig = Join-Path $bootstrapProfile "config"
  New-Item -ItemType Directory -Path $bootstrapConfig, $bootstrapScripts -Force | Out-Null
  $bootstrapProject = "vayujit-pc-cert-$bootstrapId"
  $bootstrapVolumePrefix = "vayujit_pc_cert_$bootstrapId"
  [System.IO.File]::WriteAllText((Join-Path $bootstrapProfile "disposable-profile.marker"), "vayujit-pc-disposable-certification-v1`nproject=$bootstrapProject`nvolume_prefix=$bootstrapVolumePrefix`n")
  [System.IO.File]::WriteAllText((Join-Path $bootstrapConfig "compose.env"), "")
  Copy-Item -LiteralPath (Join-Path $PSScriptRoot "pc-first-backup-bootstrap.ps1") -Destination $bootstrapScripts
  Copy-Item -LiteralPath (Join-Path $PSScriptRoot "pc-first-key-security.psm1") -Destination $bootstrapScripts
  Copy-Item -LiteralPath (Join-Path $PSScriptRoot "pc-first-backup-artifacts.psm1") -Destination $bootstrapScripts
  $backupScriptSource = Get-Content -LiteralPath (Join-Path $PSScriptRoot "backup-pc-first.ps1") -Raw
  $backupScriptCopy = Join-Path $bootstrapScripts "backup-pc-first.ps1"
  [System.IO.File]::WriteAllText($backupScriptCopy, $backupScriptSource)
  $testPowerShellPath = (Get-Process -Id $PID -ErrorAction Stop).Path

  $invalidArgumentsReport = Join-Path $bootstrapProfile "invalid-arguments.json"
  $invalidArgumentsRun = Invoke-VayujitNativeCapture -FilePath $testPowerShellPath -Arguments @(
    "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", $backupScriptCopy,
    "-DataRoot", $bootstrapProfile, "-DisposableCertification", "-BackupDestination", "", "-BackupReportPath", $invalidArgumentsReport
  )
  $invalidArgumentsJson = Get-Content -LiteralPath $invalidArgumentsReport -Raw | ConvertFrom-Json
  Assert-Regression ($invalidArgumentsRun.ExitCode -eq 1 -and $invalidArgumentsJson.failure_code -eq "backup_arguments_invalid" -and $invalidArgumentsJson.failure_operation -eq "backup child argument validation") "invalid disposable arguments are reported before backup operations"

  $importFailureScript = Join-Path $bootstrapScripts "backup-import-failure.ps1"
  $importFailureSource = $backupScriptSource.Replace('Import-Module (Join-Path $PSScriptRoot "pc-first-key-security.psm1") -Force', 'Import-Module (Join-Path $PSScriptRoot "missing-key-security-module.psm1") -Force')
  [System.IO.File]::WriteAllText($importFailureScript, $importFailureSource)
  $importFailureReport = Join-Path $bootstrapProfile "import-failure.json"
  $importFailureRun = Invoke-VayujitNativeCapture -FilePath $testPowerShellPath -Arguments @(
    "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", $importFailureScript,
    "-DataRoot", $bootstrapProfile, "-DisposableCertification", "-BackupDestination", (Join-Path $bootstrapProfile "backup-destination"), "-BackupReportPath", $importFailureReport
  )
  $importFailureJson = Get-Content -LiteralPath $importFailureReport -Raw | ConvertFrom-Json
  Assert-Regression ($importFailureRun.ExitCode -eq 1 -and $importFailureJson.failure_code -eq "backup_initialization_failed" -and $importFailureJson.failure_operation -eq "backup child initialization" -and (($importFailureJson | ConvertTo-Json -Depth 5) -notmatch "missing-key-security-module")) "an early module import failure produces a safe structured child report"

  $bootstrapMissingScripts = Join-Path $bootstrapScriptBase "without-bootstrap"
  New-Item -ItemType Directory -Path $bootstrapMissingScripts -Force | Out-Null
  $bootstrapLoadFailureScript = Join-Path $bootstrapMissingScripts "backup-pc-first.ps1"
  Copy-Item -LiteralPath (Join-Path $PSScriptRoot "backup-pc-first.ps1") -Destination $bootstrapLoadFailureScript
  $bootstrapLoadFailureReport = Join-Path $bootstrapProfile "bootstrap-load-failure.json"
  $bootstrapLoadFailureRun = Invoke-VayujitNativeCapture -FilePath $testPowerShellPath -Arguments @(
    "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", $bootstrapLoadFailureScript,
    "-DataRoot", $bootstrapProfile, "-DisposableCertification", "-BackupDestination", (Join-Path $bootstrapProfile "backup-destination"), "-BackupReportPath", $bootstrapLoadFailureReport
  )
  $bootstrapLoadFailureCode = [regex]::Match([string]$bootstrapLoadFailureRun.StdOut, '(?m)^VAYUJIT_BACKUP_CHILD_BOUNDARY=(backup_evidence_report_write_failed|backup_initialization_failed|backup_arguments_invalid|backup_preflight_failed)\s*$').Groups[1].Value
  $bootstrapLoadResolution = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode $bootstrapLoadFailureRun.ExitCode -ReportPath $bootstrapLoadFailureReport -BootstrapFailureCode $bootstrapLoadFailureCode
  Assert-Regression ($bootstrapLoadFailureRun.ExitCode -eq 1 -and $bootstrapLoadFailureCode -eq "backup_initialization_failed" -and $bootstrapLoadResolution.Failure.failure_code -eq "backup_initialization_failed") "bootstrap helper load failure is classified by a safe token without backup success"

  $initFailureScript = Join-Path $bootstrapScripts "backup-init-failure.ps1"
  $initFailureSource = $backupScriptSource.Replace('Import-Module (Join-Path $PSScriptRoot "pc-first-key-security.psm1") -Force', 'throw "AGE-SECRET-INIT-MUST-NOT-LEAK"')
  [System.IO.File]::WriteAllText($initFailureScript, $initFailureSource)
  $initFailureReport = Join-Path $bootstrapProfile "init-failure.json"
  $initFailureRun = Invoke-VayujitNativeCapture -FilePath $testPowerShellPath -Arguments @(
    "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", $initFailureScript,
    "-DataRoot", $bootstrapProfile, "-DisposableCertification", "-BackupDestination", (Join-Path $bootstrapProfile "backup-destination"), "-BackupReportPath", $initFailureReport
  )
  $initFailureJson = Get-Content -LiteralPath $initFailureReport -Raw | ConvertFrom-Json
  $initFailureText = ($initFailureJson | ConvertTo-Json -Depth 5) + $initFailureRun.StdErr
  Assert-Regression ($initFailureRun.ExitCode -eq 1 -and $initFailureJson.failure_code -eq "backup_initialization_failed" -and $initFailureText -notmatch "AGE-SECRET-INIT-MUST-NOT-LEAK") "initialization exceptions are reduced to the safe code without emitting exception text"

  $bootstrapMissingMarkerProfile = Join-Path ([System.IO.Path]::GetTempPath()) ("vayujit-backup-bootstrap-unmarked-" + $bootstrapId)
  New-Item -ItemType Directory -Path (Join-Path $bootstrapMissingMarkerProfile "config") -Force | Out-Null
  $missingMarkerReport = Join-Path $bootstrapMissingMarkerProfile "backup-rehearsal.json"
  $missingMarkerRun = Invoke-VayujitNativeCapture -FilePath $testPowerShellPath -Arguments @(
    "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", $backupScriptCopy,
    "-DataRoot", $bootstrapMissingMarkerProfile, "-DisposableCertification", "-BackupDestination", (Join-Path $bootstrapMissingMarkerProfile "destination"), "-BackupReportPath", $missingMarkerReport
  )
  $missingMarkerCode = [regex]::Match([string]$missingMarkerRun.StdOut, '(?m)^VAYUJIT_BACKUP_CHILD_BOUNDARY=(backup_evidence_report_write_failed|backup_initialization_failed|backup_arguments_invalid|backup_preflight_failed)\s*$').Groups[1].Value
  $missingMarkerResolution = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode $missingMarkerRun.ExitCode -ReportPath $missingMarkerReport -BootstrapFailureCode $missingMarkerCode
  Assert-Regression ($missingMarkerRun.ExitCode -eq 1 -and $missingMarkerCode -eq "backup_preflight_failed" -and $missingMarkerResolution.Failure.failure_code -eq "backup_preflight_failed") "missing marker preflight returns a fixed safe boundary token for parent classification"

  $writeFailureParent = Join-Path $bootstrapProfile "report-parent"
  New-Item -ItemType Directory -Path $writeFailureParent -Force | Out-Null
  $writeFailureReport = Join-Path $writeFailureParent "backup.json"
  $writeFailureBoundary = Initialize-VayujitBackupReportBoundary -DisposableCertification $true -DataRoot $bootstrapProfile -BackupReportPath $writeFailureReport -RepositoryRoot (Join-Path $PSScriptRoot "..")
  Assert-Regression ($writeFailureBoundary.IsValid) "report path boundary accepts a marked disposable profile"
  $writeFailureObject = New-VayujitBootstrapFailureReport -BackupId $bootstrapId -FailureCode "backup_initialization_failed" -FailureOperation "backup child initialization"
  $lockedReport = [System.IO.File]::Open($writeFailureReport, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
  try { $writeFailureObserved = -not (Write-VayujitBootstrapFailureReport -ReportPath $writeFailureReport -Report $writeFailureObject) } finally { $lockedReport.Dispose() }
  $writeFailureResolution = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 1 -ReportPath $writeFailureReport -BootstrapFailureCode "backup_evidence_report_write_failed"
  Assert-Regression ($writeFailureObserved -and $writeFailureResolution.Failure.failure_code -eq "backup_evidence_report_write_failed" -and $writeFailureResolution.Failure.child_report_status -eq "INVALID_JSON") "report-writing failure is surfaced by its allowlisted boundary marker"
  $argumentExitResolution = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 1 -ReportPath (Join-Path $bootstrapProfile "unreported-arguments.json") -BootstrapFailureCode "backup_arguments_invalid"
  $initExitResolution = Resolve-VayujitBackupChildReport -LaunchSucceeded $true -ProcessExitCode 1 -ReportPath (Join-Path $bootstrapProfile "unreported-initialization.json") -BootstrapFailureCode "backup_initialization_failed"
  Assert-Regression ($argumentExitResolution.Failure.failure_code -eq "backup_arguments_invalid" -and $initExitResolution.Failure.failure_code -eq "backup_initialization_failed") "parent maps safe early-boundary markers without claiming backup success"

  $healthStates = [System.Collections.Generic.Queue[string]]::new()
  $healthStates.Enqueue("starting")
  $healthStates.Enqueue("healthy")
  $failedBackupWasObserved = $true
  $workerRecoveryState = [pscustomobject]@{ StartAfterFailure = $false }
  $workerRecovery = Invoke-VayujitWorkerRecovery -StartWorker {
    if ($failedBackupWasObserved) { $workerRecoveryState.StartAfterFailure = $true }
    [pscustomobject]@{ ExitCode = 0 }
  } -GetHealth {
    [pscustomobject]@{ ExitCode = 0; Status = $healthStates.Dequeue() }
  } -Delay { param([int]$Seconds) } -MaxAttempts 3
  Assert-Regression ($workerRecovery.Status -eq "PASS" -and $workerRecovery.LastHealth -eq "healthy" -and $workerRecoveryState.StartAfterFailure) "worker is restarted and health-confirmed even after a backup failure"

  $workerStartFailed = Invoke-VayujitWorkerRecovery -StartWorker { [pscustomobject]@{ ExitCode = 23 } } -GetHealth { throw "must not query health after failed start" } -MaxAttempts 1
  Assert-Regression ($workerStartFailed.FailureCode -eq "worker_restart_failed" -and $workerStartFailed.DockerExitCode -eq 23) "worker start nonzero exit is retained as a recovery failure"
  $workerNeverHealthy = Invoke-VayujitWorkerRecovery -StartWorker { [pscustomobject]@{ ExitCode = 0 } } -GetHealth { [pscustomobject]@{ ExitCode = 0; Status = "unhealthy" } } -Delay { param([int]$Seconds) } -MaxAttempts 2
  Assert-Regression ($workerNeverHealthy.FailureCode -eq "worker_restart_not_healthy" -and $workerNeverHealthy.LastHealth -eq "unhealthy") "successful start without healthy state is not reported as recovered"
  $workerHealthFailed = Invoke-VayujitWorkerRecovery -StartWorker { [pscustomobject]@{ ExitCode = 0 } } -GetHealth { [pscustomobject]@{ ExitCode = 17; Status = "unknown" } } -MaxAttempts 1
  Assert-Regression ($workerHealthFailed.FailureCode -eq "worker_health_check_failed" -and $workerHealthFailed.DockerExitCode -eq 17) "worker health-check Docker failure is explicit"

  $backupScript = Get-Content -LiteralPath (Join-Path $PSScriptRoot "backup-pc-first.ps1") -Raw
  $runnerScript = Get-Content -LiteralPath (Join-Path $PSScriptRoot "test-pc-first-disposable.ps1") -Raw
  $securityScript = Get-Content -LiteralPath (Join-Path $PSScriptRoot "pc-first-key-security.psm1") -Raw
  Assert-Regression ($backupScript.Contains('FailureCode "database_encryption_failed"') -and $backupScript.Contains('FailureCode "media_decryption_verification_failed"')) "production encryption and verification callers use stage failure taxonomy"
  $stagePairs = [System.Collections.Generic.List[object]]::new()
  foreach ($line in ($backupScript -split "`r?`n")) {
    if ($line -match 'Set-BackupStage -Operation "([^"]+)" -FailureCode "([^"]+)"' -or
        $line -match 'Invoke-BackupAgeStage .* -Operation "([^"]+)" -FailureCode "([^"]+)"') {
      $stagePairs.Add([pscustomobject]@{ Operation = $Matches[1]; FailureCode = $Matches[2] })
    }
  }
  $invalidStagePairs = @(
    foreach ($stagePair in $stagePairs) {
      $safeStage = New-VayujitBackupFailureReport -BackupId "stage-test" -FailureOperation $stagePair.Operation -FailureCode $stagePair.FailureCode
      if ($safeStage.failure_operation -ne $stagePair.Operation -or $safeStage.failure_code -ne $stagePair.FailureCode) { $stagePair }
    }
  )
  $stageMismatchSummary = @($invalidStagePairs | ForEach-Object { "$($_.Operation) [$($_.FailureCode)]" }) -join ", "
  Assert-Regression ($stagePairs.Count -ge 20 -and $invalidStagePairs.Count -eq 0) "all production backup stages retain their allowlisted operation and failure code: $stageMismatchSummary"
  Assert-Regression ($backupScript.Contains('$script:dockerFailureExitCode = [int]$LASTEXITCODE') -and $backupScript.Contains('elseif ($backupCurrentFailureCode) { $backupCurrentFailureCode }')) "native command failures preserve stage code and exit status"
  $dockerInvocationLines = @($backupScript -split "`r?`n" | Where-Object { $_ -match '& \$docker\.Source' })
  Assert-Regression ($dockerInvocationLines.Count -gt 0 -and @($dockerInvocationLines | Where-Object { $_ -notmatch '2>\$null' }).Count -eq 0) "Docker stderr cannot turn a successful command into a PowerShell terminating error"
  Assert-Regression ($backupScript.Contains('independent restore report parsing') -and $backupScript.Contains('post-decryption media verification output parsing')) "restore and verification parsing have distinct failure stages"
  Assert-Regression ($backupScript.Contains('New-VayujitBackupFailureReport') -and $backupScript.Contains('$backupReportFullPath, (($failure | ConvertTo-Json')) "backup exception writes a structured failure report"
  Assert-Regression ($backupScript.Contains('Get-Content -LiteralPath $backupReportFullPath -Raw | ConvertFrom-Json') -and $backupScript.Contains('WriteAllText($backupReportFullPath')) "recovery updates use the same canonicalized report path as the parent"
  Assert-Regression ($runnerScript.Contains('Set-VayujitDisposableBackupFailure') -and $runnerScript.Contains('$backupExecutionStarted -and -not $backupExecutionCompleted')) "disposable runner propagates failure without replacing later PASS evidence"
  Assert-Regression ($runnerScript.Contains('Invoke-VayujitNativeCapture -FilePath $childPowerShellPath') -and $runnerScript.Contains('Resolve-VayujitBackupChildReport') -and $runnerScript.Contains('Join-Path $tempRoot "backup-rehearsal.json"')) "isolated child process and exact temporary report path are validated before cleanup"
  Assert-Regression ($runnerScript.Contains('"PC_CERT_PASSWORD"') -and $runnerScript.Contains('-RemoveEnvironmentVariables')) "synthetic owner credentials are not inherited by the backup child process"
  Assert-Regression ($securityScript.Contains('"Invoke-VayujitNativeCapture"')) "captured child invocation keeps raw stdout and stderr out of report channels"
  Assert-Regression ($backupScript.Contains('Invoke-VayujitWorkerRecovery') -and $backupScript.Contains('health was') -and $backupScript.Contains('Add-CleanupFailure $workerRecovery.FailureCode')) "backup worker recovery requires health confirmation and persists explicit failures"
  Assert-Regression ($runnerScript.Contains('Omitted to prevent credentials, private material, or customer data')) "raw container diagnostics are omitted from certification reports"
  Assert-Regression ($runnerScript.Contains('VAYUJIT_BACKUP_CHILD_BOUNDARY=') -and $runnerScript.Contains('-BootstrapFailureCode $backupChildBoundaryCode')) "parent consumes only the fixed allowlisted bootstrap-failure token"
  Assert-Regression ($backupScript.Contains('pc-first-backup-bootstrap.ps1') -and $backupScript.Contains('backupBootstrapFailureCode') -and $backupScript.Contains('Stop-VayujitDisposableBackupBootstrap')) "backup child establishes the safe report boundary before modules and preflight"

  Write-Output "Backup artifact regression tests: $passed passed, 0 failed."
} finally {
  Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
  if ($bootstrapProfile -and (Test-Path -LiteralPath $bootstrapProfile)) { Remove-Item -LiteralPath $bootstrapProfile -Recurse -Force -ErrorAction SilentlyContinue }
  if ($bootstrapMissingMarkerProfile -and (Test-Path -LiteralPath $bootstrapMissingMarkerProfile)) { Remove-Item -LiteralPath $bootstrapMissingMarkerProfile -Recurse -Force -ErrorAction SilentlyContinue }
  if ($bootstrapScriptBase -and (Test-Path -LiteralPath $bootstrapScriptBase)) { Remove-Item -LiteralPath $bootstrapScriptBase -Recurse -Force -ErrorAction SilentlyContinue }
}
