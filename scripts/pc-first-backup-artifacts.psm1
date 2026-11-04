Set-StrictMode -Version Latest

$script:SafeBackupOperations = @(
  "backup preflight", "backup stage unclassified", "backup subprocess report propagation",
  "backup child process launch", "backup child process exit", "backup child report missing",
  "backup child initialization", "backup child argument validation", "backup evidence report creation",
  "backup child report parsing", "backup child report schema validation",
  "publishing worker restart and health verification", "application service recovery",
  "maintenance status check", "worker state check", "maintenance enable", "worker pause", "API pause",
  "PostgreSQL container lookup", "canonical source snapshot", "canonical disposable source snapshot query",
  "PostgreSQL dump creation", "PostgreSQL dump copy", "PostgreSQL dump artifact validation",
  "media backup creation", "media artifact resolution", "pre-encryption media verification",
  "pre-encryption media verification output parsing", "PostgreSQL dump inspection", "age executable resolution",
  "database encryption", "media encryption", "media manifest encryption", "encrypted artifact header validation",
  "database decryption verification", "media decryption verification", "media manifest decryption verification",
  "decrypted artifact validation", "wrong-key rejection verification", "corrupted ciphertext rejection verification",
  "independent PostgreSQL restore", "independent restore report parsing", "post-decryption media restore verification",
  "post-decryption media verification output parsing", "canonical source integrity comparison",
  "encrypted artifact integrity manifest creation", "backup evidence report creation", "Docker command"
)

$script:SafeBackupFailureCodes = @(
  "age_tool_unavailable", "api_pause_failed", "api_restart_failed", "api_restart_not_healthy",
  "backup_artifact_manifest_creation_failed", "backup_evidence_report_write_failed", "backup_preflight_failed",
  "backup_arguments_invalid", "backup_initialization_failed",
  "backup_subprocess_failed", "backup_subprocess_launch_failed", "backup_subprocess_nonzero_exit",
  "backup_report_missing", "backup_report_invalid_json", "backup_report_schema_invalid",
  "backup_unexpected_exception", "canonical_source_snapshot_failed",
  "container_temporary_staging_cleanup_failed", "corrupted_ciphertext_test_failed", "corrupted_ciphertext_was_accepted",
  "database_ciphertext_header_invalid", "encrypted_artifact_header_invalid",
  "database_decryption_verification_empty", "database_decryption_verification_failed", "database_decryption_verification_missing",
  "database_dump_artifact_empty", "database_dump_artifact_missing", "database_dump_artifact_validation_failed",
  "database_dump_copy_failed", "database_dump_failed", "database_dump_validation_failed", "database_encryption_failed",
  "decrypted_artifact_validation_failed", "docker_command_failed", "host_plaintext_staging_cleanup_failed",
  "encrypted_database_artifact_too_small", "independent_database_restore_failed", "independent_media_restore_empty",
  "maintenance_already_enabled_or_unavailable",
  "maintenance_clear_failed", "maintenance_enable_failed", "maintenance_marker_preserved_because_api_is_not_healthy",
  "maintenance_status_failed", "media_archive_validation_failed", "media_backup_archive_empty", "media_backup_archive_missing",
  "media_backup_artifacts_missing", "media_backup_failed", "media_backup_manifest_empty", "media_backup_manifest_missing",
  "disposable_media_backup_has_no_verified_files", "media_backup_validation_failed", "media_backup_validation_output_invalid", "media_decryption_verification_empty",
  "media_decryption_verification_failed", "media_decryption_verification_missing", "media_encryption_failed",
  "media_manifest_decryption_verification_empty", "media_manifest_decryption_verification_failed",
  "media_manifest_decryption_verification_missing", "media_manifest_encryption_failed", "media_restore_report_invalid",
  "postgres_container_unavailable", "restore_report_invalid", "service_recovery_failed",
  "restored_canonical_records_or_financial_precision_mismatch", "source_canonical_data_changed_during_backup_rehearsal",
  "source_integrity_verification_failed", "worker_container_unavailable",
  "worker_not_running_before_backup", "worker_pause_failed", "worker_pause_timeout", "worker_not_quiescent", "worker_restart_failed",
  "worker_restart_not_healthy", "worker_health_check_failed", "worker_state_check_failed",
  "wrong_key_test_failed", "wrong_key_was_accepted"
)

function Assert-VayujitBackupArtifact {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$MissingFailureCode,
    [Parameter(Mandatory = $true)][string]$EmptyFailureCode
  )

  $artifact = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
  if (-not $artifact -or $artifact.PSIsContainer) {
    throw $MissingFailureCode
  }
  if ($artifact.Length -le 0) {
    throw $EmptyFailureCode
  }
  return $artifact
}

function Get-VayujitMediaBackupArtifacts {
  [CmdletBinding()]
  param([Parameter(Mandatory = $true)][string]$OutputDirectory)

  $archivePath = Join-Path $OutputDirectory "media.zip"
  $manifestPath = Join-Path $OutputDirectory "media.json"
  $archive = Assert-VayujitBackupArtifact `
    -Path $archivePath `
    -MissingFailureCode "media_backup_archive_missing" `
    -EmptyFailureCode "media_backup_archive_empty"
  $manifest = Assert-VayujitBackupArtifact `
    -Path $manifestPath `
    -MissingFailureCode "media_backup_manifest_missing" `
    -EmptyFailureCode "media_backup_manifest_empty"

  return [pscustomobject]@{
    ArchivePath = $archive.FullName
    ManifestPath = $manifest.FullName
    ArchiveLength = [long]$archive.Length
    ManifestLength = [long]$manifest.Length
  }
}

function New-VayujitBackupStageException {
  param(
    [Parameter(Mandatory = $true)][string]$Operation,
    [Parameter(Mandatory = $true)][string]$FailureCode,
    [Nullable[int]]$NativeExitCode
  )

  if ($Operation -notin $script:SafeBackupOperations) { $Operation = "backup stage unclassified" }
  if ($FailureCode -notin $script:SafeBackupFailureCodes) { $FailureCode = "backup_unexpected_exception" }
  $exception = [System.Exception]::new($FailureCode)
  $exception.Data["failure_operation"] = $Operation
  $exception.Data["failure_code"] = $FailureCode
  if ($null -ne $NativeExitCode) { $exception.Data["native_exit_code"] = [int]$NativeExitCode }
  return $exception
}

function Invoke-VayujitBackupStage {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][string]$Operation,
    [Parameter(Mandatory = $true)][string]$FailureCode,
    [Parameter(Mandatory = $true)][scriptblock]$Action
  )

  try {
    $result = & $Action
  } catch {
    throw (New-VayujitBackupStageException -Operation $Operation -FailureCode $FailureCode)
  }

  $exitProperty = if ($null -ne $result) { $result.PSObject.Properties["ExitCode"] } else { $null }
  if ($exitProperty -and [int]$exitProperty.Value -ne 0) {
    throw (New-VayujitBackupStageException -Operation $Operation -FailureCode $FailureCode -NativeExitCode ([int]$exitProperty.Value))
  }
  return $result
}

function New-VayujitBackupFailureReport {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][string]$BackupId,
    [Parameter(Mandatory = $true)][string]$FailureOperation,
    [Parameter(Mandatory = $true)][string]$FailureCode,
    [Nullable[int]]$NativeExitCode,
    [Nullable[int]]$DockerExitCode,
    [string]$CleanupFailure,
    [Nullable[int]]$SubprocessExitCode,
    [string]$ChildReportStatus,
    [string]$DestinationIndependence = "UNVERIFIED"
  )

  $safeException = New-VayujitBackupStageException -Operation $FailureOperation -FailureCode $FailureCode -NativeExitCode $NativeExitCode
  $safeBackupId = if ($BackupId -match '^[A-Za-z0-9_-]{1,80}$') { $BackupId } else { "unavailable" }
  $safeCleanup = $null
  if ($CleanupFailure) {
    $safeCleanup = @($CleanupFailure -split ';\s*' | ForEach-Object {
      if ($_ -match '^[a-z][a-z0-9_]{0,79}$') { $_ } else { "cleanup_recovery_failed" }
    } | Select-Object -Unique) -join "; "
  }
  $safeIndependence = if ($DestinationIndependence -in @("VERIFIED_DIFFERENT_PHYSICAL_DISK", "SAME_PHYSICAL_DISK", "UNVERIFIED")) { $DestinationIndependence } else { "UNVERIFIED" }
  $report = [ordered]@{
    status = "FAIL"
    backup_id = $safeBackupId
    failure_code = $safeException.Data["failure_code"]
    failure_operation = $safeException.Data["failure_operation"]
    native_exit_code = if ($null -ne $NativeExitCode) { [int]$NativeExitCode } else { $null }
    docker_exit_code = if ($null -ne $DockerExitCode) { [int]$DockerExitCode } else { $null }
    cleanup_failure = $safeCleanup
    destination_independence = $safeIndependence
    recovery_hint = "Review the recorded stage code and service health. No partial backup was certified."
  }
  if ($null -ne $SubprocessExitCode) { $report.subprocess_exit_code = [int]$SubprocessExitCode }
  if ($ChildReportStatus -in @("MISSING", "INVALID_JSON", "SCHEMA_INVALID", "PASS", "FAIL")) {
    $report.child_report_status = $ChildReportStatus
  }
  return $report
}

function Resolve-VayujitBackupChildReport {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][bool]$LaunchSucceeded,
    [Nullable[int]]$ProcessExitCode,
    [Parameter(Mandatory = $true)][string]$ReportPath,
    [string]$FallbackBackupId = "unavailable",
    [string]$BootstrapFailureCode
  )

  $exitNumber = if ($null -ne $ProcessExitCode) { [Nullable[int]]([int]$ProcessExitCode) } else { [Nullable[int]]$null }
  $makeFailure = {
    param([string]$Operation, [string]$Code, [string]$ReportStatus)
    $failure = New-VayujitBackupFailureReport `
      -BackupId $FallbackBackupId `
      -FailureOperation $Operation `
      -FailureCode $Code `
      -SubprocessExitCode $exitNumber `
      -ChildReportStatus $ReportStatus
    return [pscustomobject]@{ Status = "FAIL"; Failure = $failure; Report = $null }
  }
  $makeBootstrapFailure = {
    param([string]$ReportStatus)
    $map = @{
      backup_evidence_report_write_failed = @("backup evidence report creation", "backup_evidence_report_write_failed")
      backup_initialization_failed = @("backup child initialization", "backup_initialization_failed")
      backup_arguments_invalid = @("backup child argument validation", "backup_arguments_invalid")
      backup_preflight_failed = @("backup preflight", "backup_preflight_failed")
    }
    if (-not $map.ContainsKey([string]$BootstrapFailureCode)) { return $null }
    $pair = $map[[string]$BootstrapFailureCode]
    return (& $makeFailure $pair[0] $pair[1] $ReportStatus)
  }

  if (-not $LaunchSucceeded) { return (& $makeFailure "backup child process launch" "backup_subprocess_launch_failed" "MISSING") }
  if (-not (Test-Path -LiteralPath $ReportPath -PathType Leaf)) {
    $bootstrapFailure = & $makeBootstrapFailure "MISSING"
    if ($bootstrapFailure) { return $bootstrapFailure }
    if ($null -ne $exitNumber -and [int]$exitNumber -ne 0) {
      return (& $makeFailure "backup child process exit" "backup_subprocess_nonzero_exit" "MISSING")
    }
    return (& $makeFailure "backup child report missing" "backup_report_missing" "MISSING")
  }

  try {
    $childJson = Get-Content -LiteralPath $ReportPath -Raw -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace([string]$childJson)) { throw "backup_report_empty" }
    $child = $childJson | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $bootstrapFailure = & $makeBootstrapFailure "INVALID_JSON"
    if ($bootstrapFailure) { return $bootstrapFailure }
    return (& $makeFailure "backup child report parsing" "backup_report_invalid_json" "INVALID_JSON")
  }

  $validSchema = $null -ne $child -and $null -ne $child.PSObject.Properties["status"] -and
    $null -ne $child.PSObject.Properties["backup_id"] -and
    [string]$child.backup_id -match '^[A-Za-z0-9_-]{1,80}$'
  if ($validSchema -and [string]$child.status -eq "PASS") {
    $requiredPassFields = @(
      "profile", "artifacts_are_not_business_backups", "artifact_manifest", "destination_independence",
      "encrypted_artifact_header", "wrong_key_rejected", "corrupted_ciphertext_rejected",
      "canonical_records_restored_and_compared", "financial_precision_verified",
      "media_restored_and_checksums_verified", "source_canonical_records_unchanged",
      "backup_duration_seconds", "restore_duration_seconds"
    )
    foreach ($field in $requiredPassFields) {
      if ($null -eq $child.PSObject.Properties[$field]) { $validSchema = $false; break }
    }
    if ($validSchema) {
      $validSchema = [string]$child.profile -eq "marker_protected_disposable_only" -and
        [bool]$child.artifacts_are_not_business_backups -and
        [string]$child.destination_independence -in @("VERIFIED_DIFFERENT_PHYSICAL_DISK", "SAME_PHYSICAL_DISK", "UNVERIFIED") -and
        [bool]$child.encrypted_artifact_header -and [bool]$child.wrong_key_rejected -and
        [bool]$child.corrupted_ciphertext_rejected -and [bool]$child.canonical_records_restored_and_compared -and
        [bool]$child.financial_precision_verified -and [bool]$child.media_restored_and_checksums_verified -and
        [bool]$child.source_canonical_records_unchanged -and @($child.artifact_manifest).Count -gt 0 -and
        [string]$child.backup_duration_seconds -match '^\d+(\.\d+)?$' -and
        [string]$child.restore_duration_seconds -match '^\d+(\.\d+)?$'
    }
    if ($validSchema -and $null -ne $exitNumber -and [int]$exitNumber -ne 0) {
      $bootstrapFailure = & $makeBootstrapFailure "PASS"
      if ($bootstrapFailure) { return $bootstrapFailure }
      return (& $makeFailure "backup child process exit" "backup_subprocess_nonzero_exit" "PASS")
    }
    if ($validSchema) { return [pscustomobject]@{ Status = "PASS"; Failure = $null; Report = $child } }
  } elseif ($validSchema -and [string]$child.status -eq "FAIL") {
    foreach ($field in @("failure_code", "failure_operation", "native_exit_code", "docker_exit_code", "cleanup_failure", "destination_independence")) {
      if ($null -eq $child.PSObject.Properties[$field]) { $validSchema = $false; break }
    }
    if ($validSchema) {
      $validSchema = [string]$child.failure_code -in $script:SafeBackupFailureCodes -and
        [string]$child.failure_operation -in $script:SafeBackupOperations -and
        [string]$child.destination_independence -in @("VERIFIED_DIFFERENT_PHYSICAL_DISK", "SAME_PHYSICAL_DISK", "UNVERIFIED")
    }
    foreach ($field in @("native_exit_code", "docker_exit_code")) {
      $value = $child.PSObject.Properties[$field]
      if (-not $value -or ($null -ne $value.Value -and [string]$value.Value -notmatch '^-?\d{1,9}$')) { $validSchema = $false }
    }
    if ($validSchema) {
      $nativeChildExit = [Nullable[int]]$null
      if ($null -ne $child.native_exit_code) { $nativeChildExit = [Nullable[int]]([int]$child.native_exit_code) }
      $dockerChildExit = [Nullable[int]]$null
      if ($null -ne $child.docker_exit_code) { $dockerChildExit = [Nullable[int]]([int]$child.docker_exit_code) }
      $childCleanupFailure = [string]$child.cleanup_failure
      if ([string]$BootstrapFailureCode -eq "backup_evidence_report_write_failed") {
        $childCleanupFailure = @($childCleanupFailure, "backup_evidence_report_write_failed" | Where-Object { $_ }) -join "; "
      }
      $failure = New-VayujitBackupFailureReport `
        -BackupId ([string]$child.backup_id) `
        -FailureOperation ([string]$child.failure_operation) `
        -FailureCode ([string]$child.failure_code) `
        -NativeExitCode $nativeChildExit `
        -DockerExitCode $dockerChildExit `
        -CleanupFailure $childCleanupFailure `
        -SubprocessExitCode $exitNumber `
        -ChildReportStatus "FAIL" `
        -DestinationIndependence ([string]$child.destination_independence)
      return [pscustomobject]@{ Status = "FAIL"; Failure = $failure; Report = $null }
    }
  }

  $bootstrapFailure = & $makeBootstrapFailure "SCHEMA_INVALID"
  if ($bootstrapFailure) { return $bootstrapFailure }

  return (& $makeFailure "backup child report schema validation" "backup_report_schema_invalid" "SCHEMA_INVALID")
}

function Invoke-VayujitWorkerRecovery {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][scriptblock]$StartWorker,
    [Parameter(Mandatory = $true)][scriptblock]$GetHealth,
    [scriptblock]$Delay = { param([int]$Seconds) Start-Sleep -Seconds $Seconds },
    [ValidateRange(1, 120)][int]$MaxAttempts = 30
  )

  $dockerExitCode = $null
  try { $start = & $StartWorker } catch {
    $exitValue = $_.Exception.Data["native_exit_code"]
    $safeExit = if ($null -ne $exitValue -and [string]$exitValue -match '^-?\d{1,9}$') { [int]$exitValue } else { $null }
    return [pscustomobject]@{ Status = "FAIL"; FailureCode = "worker_restart_failed"; DockerExitCode = $safeExit; LastHealth = "unknown" }
  }
  $startExit = if ($null -ne $start) { $start.PSObject.Properties["ExitCode"] } else { $null }
  if (-not $startExit -or [string]$startExit.Value -notmatch '^-?\d{1,9}$') {
    return [pscustomobject]@{ Status = "FAIL"; FailureCode = "worker_restart_failed"; DockerExitCode = $null; LastHealth = "unknown" }
  }
  $dockerExitCode = [int]$startExit.Value
  if ($dockerExitCode -ne 0) {
    return [pscustomobject]@{ Status = "FAIL"; FailureCode = "worker_restart_failed"; DockerExitCode = $dockerExitCode; LastHealth = "unknown" }
  }

  $lastHealth = "starting"
  for ($attempt = 0; $attempt -lt $MaxAttempts; $attempt++) {
    try { $health = & $GetHealth } catch {
      $exitValue = $_.Exception.Data["native_exit_code"]
      $safeExit = if ($null -ne $exitValue -and [string]$exitValue -match '^-?\d{1,9}$') { [int]$exitValue } else { $null }
      return [pscustomobject]@{ Status = "FAIL"; FailureCode = "worker_health_check_failed"; DockerExitCode = $safeExit; LastHealth = $lastHealth }
    }
    $healthExit = if ($null -ne $health) { $health.PSObject.Properties["ExitCode"] } else { $null }
    $healthStatus = if ($null -ne $health -and $health.PSObject.Properties["Status"]) { ([string]$health.Status).ToLowerInvariant() } else { "unknown" }
    if (-not $healthExit -or [string]$healthExit.Value -notmatch '^-?\d{1,9}$' -or [int]$healthExit.Value -ne 0) {
      $healthDockerExit = if ($healthExit -and [string]$healthExit.Value -match '^-?\d{1,9}$') { [int]$healthExit.Value } else { $null }
      return [pscustomobject]@{ Status = "FAIL"; FailureCode = "worker_health_check_failed"; DockerExitCode = $healthDockerExit; LastHealth = "unknown" }
    }
    $lastHealth = if ($healthStatus -in @("healthy", "starting", "unhealthy")) { $healthStatus } else { "unknown" }
    if ($lastHealth -eq "healthy") {
      return [pscustomobject]@{ Status = "PASS"; FailureCode = $null; DockerExitCode = $null; LastHealth = $lastHealth }
    }
    if ($attempt + 1 -lt $MaxAttempts) { & $Delay 2 }
  }
  return [pscustomobject]@{ Status = "FAIL"; FailureCode = "worker_restart_not_healthy"; DockerExitCode = $null; LastHealth = $lastHealth }
}

function Set-VayujitBackupRecoveryFailure {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][object]$Report,
    [Parameter(Mandatory = $true)][string]$CleanupFailure
  )

  $backupId = if ($Report.PSObject.Properties["backup_id"]) { [string]$Report.backup_id } else { "unavailable" }
  $independence = if ($Report.PSObject.Properties["destination_independence"]) { [string]$Report.destination_independence } else { "UNVERIFIED" }
  $existingStatus = if ($Report.PSObject.Properties["status"]) { [string]$Report.status } else { "" }
  if ($existingStatus -eq "PASS") {
    $failure = New-VayujitBackupFailureReport `
      -BackupId $backupId `
      -FailureOperation "application service recovery" `
      -FailureCode "service_recovery_failed" `
      -CleanupFailure $CleanupFailure `
      -DestinationIndependence $independence
    $Report | Add-Member -NotePropertyName failure_code -NotePropertyValue $failure.failure_code -Force
    $Report | Add-Member -NotePropertyName failure_operation -NotePropertyValue $failure.failure_operation -Force
    $Report | Add-Member -NotePropertyName native_exit_code -NotePropertyValue $failure.native_exit_code -Force
    $Report | Add-Member -NotePropertyName docker_exit_code -NotePropertyValue $failure.docker_exit_code -Force
    $Report | Add-Member -NotePropertyName recovery_hint -NotePropertyValue "Backup verification completed, but service recovery failed. Confirm API/worker health and maintenance state before relying on scheduled work." -Force
  }
  $Report.status = "FAIL"
  $safeCleanup = New-VayujitBackupFailureReport `
    -BackupId $backupId `
    -FailureOperation "application service recovery" `
    -FailureCode "service_recovery_failed" `
    -CleanupFailure $CleanupFailure `
    -DestinationIndependence $independence
  $Report | Add-Member -NotePropertyName cleanup_failure -NotePropertyValue $safeCleanup.cleanup_failure -Force
  $Report | Add-Member -NotePropertyName destination_independence -NotePropertyValue $safeCleanup.destination_independence -Force
  return $Report
}

function Set-VayujitDisposableBackupFailure {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][System.Collections.IDictionary]$Certification,
    [Parameter(Mandatory = $true)][object]$BackupFailure
  )

  $readValue = {
    param([object]$InputObject, [string]$Name)
    if ($InputObject -is [System.Collections.IDictionary]) {
      if ($InputObject.Contains($Name)) { return $InputObject[$Name] }
      return $null
    }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($property) { return $property.Value }
    return $null
  }
  $operation = [string](& $readValue $BackupFailure "failure_operation")
  $code = [string](& $readValue $BackupFailure "failure_code")
  $backupId = [string](& $readValue $BackupFailure "backup_id")
  $nativeExitCode = & $readValue $BackupFailure "native_exit_code"
  $dockerExitCode = & $readValue $BackupFailure "docker_exit_code"
  $cleanupFailure = [string](& $readValue $BackupFailure "cleanup_failure")
  $destinationIndependence = [string](& $readValue $BackupFailure "destination_independence")
  $subprocessExitCode = & $readValue $BackupFailure "subprocess_exit_code"
  $childReportStatus = [string](& $readValue $BackupFailure "child_report_status")
  if ($operation -notin $script:SafeBackupOperations) { $operation = "backup stage unclassified" }
  if ($code -notin $script:SafeBackupFailureCodes) { $code = "backup_unexpected_exception" }
  $nativeNumber = if ($null -ne $nativeExitCode -and [string]$nativeExitCode -match '^-?\d{1,9}$') { [Nullable[int]]([int]$nativeExitCode) } else { [Nullable[int]]$null }
  $dockerNumber = if ($null -ne $dockerExitCode -and [string]$dockerExitCode -match '^-?\d{1,9}$') { [Nullable[int]]([int]$dockerExitCode) } else { [Nullable[int]]$null }
  $subprocessNumber = if ($null -ne $subprocessExitCode -and [string]$subprocessExitCode -match '^-?\d{1,9}$') { [Nullable[int]]([int]$subprocessExitCode) } else { [Nullable[int]]$null }
  if ($childReportStatus -notin @("MISSING", "INVALID_JSON", "SCHEMA_INVALID", "PASS", "FAIL")) { $childReportStatus = $null }
  $safeFailure = New-VayujitBackupFailureReport -BackupId $backupId -FailureOperation $operation -FailureCode $code -NativeExitCode $nativeNumber -DockerExitCode $dockerNumber -CleanupFailure $cleanupFailure -SubprocessExitCode $subprocessNumber -ChildReportStatus $childReportStatus -DestinationIndependence $destinationIndependence
  $Certification["backup_restore"] = $safeFailure
  $exitDescription = ""
  if ($null -ne $dockerNumber) {
    $exitDescription = "; Docker exit code $dockerNumber"
  } elseif ($null -ne $nativeNumber) {
    $exitDescription = "; native exit code $nativeNumber"
  } elseif ($null -ne $subprocessNumber) {
    $exitDescription = "; child process exit code $subprocessNumber"
  }
  $recoveryDescription = if ($safeFailure.cleanup_failure) { " Recovery failure: $($safeFailure.cleanup_failure)." } else { "" }
  $Certification["error"] = "Encrypted backup failed during $operation ($code$exitDescription).$recoveryDescription"
}

function Get-VayujitBackupCheckpointStages {
  return @("bootstrap load", "report boundary initialization", "key security module import", "backup artifact module import", "profile path resolution", "profile files check", "disposable argument validation", "profile configuration", "recipient validation", "identity ACL verification", "age dependency check", "age keygen dependency check", "Docker dependency check", "staging directory creation", "destination write probe", "PostgreSQL storage evidence", "media storage evidence", "destination independence check", "runtime initialization", "runtime staging creation", "child report write", "service recovery", "backup finalization") + $script:SafeBackupOperations
}

function ConvertTo-VayujitSafeStageLedger {
  param([object]$Ledger)
  $read = {
    param([string]$Name)
    if ($null -eq $Ledger) { return $null }
    if ($Ledger -is [System.Collections.IDictionary]) { return $Ledger[$Name] }
    $p = $Ledger.PSObject.Properties[$Name]
    if ($p) { return $p.Value }
    return $null
  }
  $safe = [ordered]@{}
  $stages = Get-VayujitBackupCheckpointStages
  foreach ($name in @("last_entered_stage", "last_completed_stage", "failed_stage")) {
    $value = [string](& $read $name)
    $safe[$name] = if ($value -in $stages) { $value } else { $null }
  }
  $kind = [string](& $read "failure_classification")
  $safe.failure_classification = if ($kind -in @("none", "powershell_error", "native_failure", "report_write_failed", "unhandled_process_exit", "unobserved")) { $kind } else { "unobserved" }
  $line = & $read "source_line"
  $safe.source_line = if ([string]$line -match '^\d{1,6}$' -and [int]$line -gt 0) { [int]$line } else { $null }
  $file = [string](& $read "source_file")
  $safe.source_file = if ($file -in @("backup-pc-first.ps1", "pc-first-backup-bootstrap.ps1", "pc-first-key-security.psm1", "pc-first-backup-artifacts.psm1")) { $file } else { "unavailable" }
  $exitValue = & $read "process_exit_code"
  $safe.process_exit_code = if ($null -ne $exitValue -and [string]$exitValue -match '^-?\d{1,9}$') { [int]$exitValue } else { $null }
  $written = & $read "expected_report_written"
  $safe.expected_report_written = if ($written -is [bool]) { $written } else { $null }
  $count = & $read "checkpoint_count"
  $safe.checkpoint_count = if ([string]$count -match '^\d{1,5}$') { [int]$count } else { 0 }
  return $safe
}

function Read-VayujitBackupStageLedger {
  param([string]$StdOut, [Nullable[int]]$ProcessExitCode, [string]$ReportPath)
  $ledger = @{last_entered_stage=$null; last_completed_stage=$null; failed_stage=$null; failure_classification="unobserved"; source_line=$null; source_file="unavailable"; process_exit_code=$ProcessExitCode; expected_report_written=$null; checkpoint_count=0}
  $stages = Get-VayujitBackupCheckpointStages
  $pattern = '(?m)^VAYUJIT_BACKUP_STAGE=(ENTER|COMPLETE|FAIL)\|([^|\r\n]{1,100})\|(none|powershell_error|native_failure|report_write_failed)\|(\d{1,6})\|(backup-pc-first\.ps1|pc-first-backup-bootstrap\.ps1|pc-first-key-security\.psm1|pc-first-backup-artifacts\.psm1|unavailable)\r?$'
  foreach ($match in [regex]::Matches([string]$StdOut, $pattern)) {
    $stage = $match.Groups[2].Value
    if ($stage -notin $stages) { continue }
    $ledger.checkpoint_count++
    if ($match.Groups[1].Value -eq "ENTER") { $ledger.last_entered_stage = $stage }
    elseif ($match.Groups[1].Value -eq "COMPLETE" -and $stage -eq $ledger.last_entered_stage) { $ledger.last_completed_stage = $stage }
    elseif ($match.Groups[1].Value -eq "FAIL" -and $stage -eq $ledger.last_entered_stage -and -not $ledger.failed_stage) {
      $ledger.failed_stage = $stage
      $ledger.failure_classification = $match.Groups[3].Value
      $ledger.source_line = [int]$match.Groups[4].Value
      $ledger.source_file = $match.Groups[5].Value
    }
    if (-not $ledger.failed_stage) {
      $ledger.source_line = [int]$match.Groups[4].Value
      $ledger.source_file = $match.Groups[5].Value
    }
  }
  if ($ReportPath) {
    try { $ledger.expected_report_written = [bool](Test-Path -LiteralPath $ReportPath -PathType Leaf -ErrorAction Stop) } catch { }
  }
  if (-not $ledger.failed_stage -and $ledger.last_entered_stage) {
    $ledger.failure_classification = "none"
    if (($null -ne $ProcessExitCode -and $ProcessExitCode -ne 0) -or ($ledger.expected_report_written -ceq $false -and $ledger.last_entered_stage -ne $ledger.last_completed_stage)) {
      $ledger.failure_classification = "unhandled_process_exit"
      $ledger.failed_stage = $ledger.last_entered_stage
    }
  }
  return ConvertTo-VayujitSafeStageLedger -Ledger $ledger
}

function ConvertTo-VayujitSafeChildDiagnostic {
  param([Parameter(Mandatory = $true)][object]$Diagnostic)
  $read = {
    param([string]$Name)
    if ($Diagnostic -is [System.Collections.IDictionary]) { return $Diagnostic[$Name] }
    $p = $Diagnostic.PSObject.Properties[$Name]
    if ($p) { return $p.Value }
    return $null
  }
  $messages = @{
    executable_unavailable = "The selected child executable is unavailable."
    process_launch_failed = "The child process could not be launched; raw launch exceptions were omitted."
    script_path_unavailable = "The selected child script is unavailable."
    script_parse_failed = "PowerShell could not parse the child script; only a safe error identifier and source line are retained."
    argument_binding_failed = "PowerShell rejected child arguments before normal script execution."
    execution_policy_rejected = "PowerShell reported an execution-policy or script authorization failure."
    module_import_failed = "PowerShell reported a module import failure."
    dependency_unavailable = "PowerShell reported a missing command or executable dependency."
    report_write_failed = "The child reported that structured evidence could not be written."
    initialization_failed = "The child reported an initialization failure."
    preflight_failed = "The child reported a preflight failure."
    nonzero_exit_unclassified = "The child exited unsuccessfully; stderr was captured but has no recognized safe signature."
    completed = "The child exited zero; stderr warnings alone do not establish failure."
    unclassified = "No recognized safe child-process diagnostic is available."
  }
  $classification = [string](& $read "classification")
  if (-not $messages.ContainsKey($classification)) { $classification = "unclassified" }
  $errorId = [string](& $read "powershell_error_id")
  if ($errorId -notin @("ParserError", "UnexpectedToken", "IfStatementMissingCondition", "MissingEndCurlyBrace", "MissingEndParenthesisInExpression", "MissingEndParenthesisInFunctionParameterList", "TerminatorExpectedAtEndOfString", "NamedParameterNotFound", "PositionalParameterNotFound", "MissingMandatoryParameter", "MissingArgument", "ParameterArgumentValidationError", "ParameterBindingException", "UnauthorizedAccess", "PSSecurityException", "Modules_ModuleNotFound", "CommandNotFoundException")) { $errorId = $null }
  $engine = [string](& $read "engine")
  if ($engine -notin @("WindowsPowerShell", "PowerShell")) { $engine = "UNVERIFIED" }
  $exitValue = & $read "process_exit_code"
  $exitNumber = if ($null -ne $exitValue -and [string]$exitValue -match '^-?\d{1,9}$') { [int]$exitValue } else { $null }
  $lineValue = & $read "source_line"
  $lineNumber = if ([string]$lineValue -match '^\d{1,6}$' -and [int]$lineValue -gt 0) { [int]$lineValue } else { $null }
  return [ordered]@{
    schema_version = 1
    classification = $classification
    safe_stderr_summary = $messages[$classification]
    powershell_error_id = $errorId
    source_line = $lineNumber
    source_location = "backup_child_script_or_powershell_startup"
    process_exit_code = $exitNumber
    launch_succeeded = ((& $read "launch_succeeded") -ceq $true)
    script_started_token_observed = ((& $read "script_started_token_observed") -ceq $true)
    stderr_captured = ((& $read "stderr_captured") -ceq $true)
    stdout_captured = ((& $read "stdout_captured") -ceq $true)
    engine = $engine
    invocation = "NoProfile_NonInteractive_File"
    working_directory = "repository_root"
    report_path_contract = "marked_disposable_profile/backup-rehearsal.json"
    raw_output_persisted = $false
    diagnostic_is_not_backup_certification = $true
    stage_ledger = (ConvertTo-VayujitSafeStageLedger -Ledger (& $read "stage_ledger"))
  }
}

function Get-VayujitBackupChildDiagnostic {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][bool]$LaunchSucceeded,
    [Nullable[int]]$ProcessExitCode,
    [string]$ExecutablePath,
    [string]$ChildScriptPath,
    [string]$StdOut,
    [string]$StdErr,
    [string]$ReportPath
  )
  # Positive allowlisting, not regex removal of known secrets: unrecognized
  # free text, paths, argument values and stdout are never returned or saved.
  $kind = "unclassified"
  $errorId = $null
  $sourceLine = $null
  $exeExists = $false
  $scriptExists = $false
  $engine = "UNVERIFIED"
  try { $exeExists = $ExecutablePath -and (Test-Path -LiteralPath $ExecutablePath -PathType Leaf -ErrorAction Stop) } catch { }
  try { $scriptExists = $ChildScriptPath -and (Test-Path -LiteralPath $ChildScriptPath -PathType Leaf -ErrorAction Stop) } catch { }
  try {
    $engine = switch ([System.IO.Path]::GetFileName([string]$ExecutablePath).ToLowerInvariant()) {
      "powershell.exe" { "WindowsPowerShell"; break }
      "pwsh.exe" { "PowerShell"; break }
      default { "UNVERIFIED" }
    }
  } catch { } # Invalid/inaccessible diagnostic paths must not erase the failure.
  if (-not $LaunchSucceeded) {
    $kind = if (-not $exeExists) { "executable_unavailable" } else { "process_launch_failed" }
  } elseif (-not $scriptExists) {
    $kind = "script_path_unavailable"
  } elseif ($null -ne $ProcessExitCode -and $ProcessExitCode -eq 0) {
    $kind = "completed"
  } else {
    $kind = "nonzero_exit_unclassified"
    # Use the parent's PS parser as a read-only, locale-independent additional
    # witness. Never execute the child here or copy parser exception messages.
    try {
      $tokens = $null
      $parseErrors = $null
      [System.Management.Automation.Language.Parser]::ParseFile($ChildScriptPath, [ref]$tokens, [ref]$parseErrors) | Out-Null
      if ($parseErrors.Count -gt 0) {
        $kind = "script_parse_failed"
        $errorId = [string]$parseErrors[0].ErrorId
        $sourceLine = [int]$parseErrors[0].Extent.StartLineNumber
      }
    } catch { } # Diagnostics must not erase the already-observed process exit.
    if ($kind -ne "script_parse_failed") {
      $safeIds = 'NamedParameterNotFound|PositionalParameterNotFound|MissingMandatoryParameter|MissingArgument|ParameterArgumentValidationError|ParameterBindingException|UnauthorizedAccess|PSSecurityException|Modules_ModuleNotFound|CommandNotFoundException|ParserError|UnexpectedToken'
      $match = [regex]::Match([string]$StdErr, '(?m)^\s*\+?\s*FullyQualifiedErrorId\s*:\s*(' + $safeIds + ')(?=,|\s|$)')
      if ($match.Success) { $errorId = $match.Groups[1].Value }
      switch -Regex ([string]$errorId) {
        '^(NamedParameterNotFound|PositionalParameterNotFound|MissingMandatoryParameter|MissingArgument|ParameterArgumentValidationError|ParameterBindingException)$' { $kind = "argument_binding_failed"; break }
        '^(UnauthorizedAccess|PSSecurityException)$' { $kind = "execution_policy_rejected"; break }
        '^Modules_ModuleNotFound$' { $kind = "module_import_failed"; break }
        '^CommandNotFoundException$' { $kind = "dependency_unavailable"; break }
        '^(ParserError|UnexpectedToken)$' { $kind = "script_parse_failed"; break }
      }
      # Bootstrap tokens may reach stdout when the child can execute but cannot
      # produce its file. They remain diagnostic hints, never success evidence.
      $boundary = [regex]::Match([string]$StdOut, '(?m)^VAYUJIT_BACKUP_CHILD_BOUNDARY=(backup_evidence_report_write_failed|backup_initialization_failed|backup_arguments_invalid|backup_preflight_failed)\s*$')
      if ($boundary.Success) {
        $kind = switch ($boundary.Groups[1].Value) {
          "backup_evidence_report_write_failed" { "report_write_failed" }
          "backup_initialization_failed" { "initialization_failed" }
          "backup_arguments_invalid" { "argument_binding_failed" }
          "backup_preflight_failed" { "preflight_failed" }
        }
      }
    }
  }
  return ConvertTo-VayujitSafeChildDiagnostic -Diagnostic @{
    classification = $kind; powershell_error_id = $errorId; source_line = $sourceLine
    process_exit_code = $ProcessExitCode; launch_succeeded = $LaunchSucceeded; engine = $engine
    script_started_token_observed = ([string]$StdOut -match '(?m)^VAYUJIT_BACKUP_CHILD_STARTED=1\s*$')
    stderr_captured = (-not [string]::IsNullOrWhiteSpace($StdErr))
    stdout_captured = (-not [string]::IsNullOrWhiteSpace($StdOut))
    stage_ledger = (Read-VayujitBackupStageLedger -StdOut $StdOut -ProcessExitCode $ProcessExitCode -ReportPath $ReportPath)
  }
}

function Write-VayujitBackupChildDiagnostic {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][string]$Directory,
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-f0-9]{10}$')][string]$BackupId,
    [Parameter(Mandatory = $true)][object]$Diagnostic
  )
  $safe = ConvertTo-VayujitSafeChildDiagnostic -Diagnostic $Diagnostic
  $target = Join-Path ([System.IO.Path]::GetFullPath($Directory)) "backup-child-$BackupId.json"
  try {
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) {
      New-Item -ItemType Directory -Path $Directory -Force -ErrorAction Stop | Out-Null
    }
    # Never overwrite an existing diagnostic artifact or follow its symlink.
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $safe -Depth 4) + "`n")
    $stream = [System.IO.File]::Open($target, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
  } catch { throw "backup_parent_diagnostic_write_failed" }
  return $target
}

Export-ModuleMember -Function Assert-VayujitBackupArtifact, Get-VayujitMediaBackupArtifacts, Invoke-VayujitBackupStage, Invoke-VayujitWorkerRecovery, New-VayujitBackupFailureReport, Resolve-VayujitBackupChildReport, Set-VayujitBackupRecoveryFailure, Set-VayujitDisposableBackupFailure, Get-VayujitBackupChildDiagnostic, Write-VayujitBackupChildDiagnostic
