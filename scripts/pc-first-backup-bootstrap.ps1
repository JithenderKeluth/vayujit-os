# This file is deliberately dependency-free. backup-pc-first.ps1 loads it before
# either project module so initialization failures can still be reported safely.

function Test-VayujitBootstrapPathWithin {
  param([string]$Path, [string]$BasePath)
  $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  $base = [System.IO.Path]::GetFullPath($BasePath).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  return $fullPath.Equals($base, [System.StringComparison]::OrdinalIgnoreCase) -or
    $fullPath.StartsWith($base + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

function Initialize-VayujitBackupReportBoundary {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][bool]$DisposableCertification,
    [string]$DataRoot,
    [string]$BackupReportPath,
    [string]$RepositoryRoot
  )

  $boundary = [pscustomobject]@{ IsValid = $false; ReportPath = $null; BackupId = "unavailable" }
  if (-not $DisposableCertification) { return $boundary }
  try {
    if ([string]::IsNullOrWhiteSpace($DataRoot) -or [string]::IsNullOrWhiteSpace($BackupReportPath)) { return $boundary }
    $dataFull = [System.IO.Path]::GetFullPath($DataRoot)
    $reportFull = [System.IO.Path]::GetFullPath($BackupReportPath)
    $reportDirectory = [System.IO.Path]::GetDirectoryName($reportFull)
    $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $repoFull = [System.IO.Path]::GetFullPath($RepositoryRoot)
    if (-not (Test-Path -LiteralPath $dataFull -PathType Container) -or
        -not (Test-VayujitBootstrapPathWithin -Path $dataFull -BasePath $tempRoot) -or
        $dataFull.TrimEnd('\', '/') -eq $tempRoot.TrimEnd('\', '/') -or
        (Test-VayujitBootstrapPathWithin -Path $dataFull -BasePath $repoFull) -or
        -not (Test-VayujitBootstrapPathWithin -Path $reportFull -BasePath $dataFull) -or
        -not $reportDirectory -or -not (Test-VayujitBootstrapPathWithin -Path $reportDirectory -BasePath $dataFull) -or
        -not (Test-Path -LiteralPath $reportDirectory -PathType Container) -or
        (Test-Path -LiteralPath $reportFull)) { return $boundary }

    $dataItem = Get-Item -LiteralPath $dataFull -Force -ErrorAction Stop
    $reportDirectoryItem = Get-Item -LiteralPath $reportDirectory -Force -ErrorAction Stop
    if (($dataItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -or
        ($reportDirectoryItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { return $boundary }
    $markerPath = Join-Path $dataFull "disposable-profile.marker"
    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) { return $boundary }
    $markerText = [System.IO.File]::ReadAllText($markerPath)
    if (-not $markerText.StartsWith("vayujit-pc-disposable-certification-v1`n", [System.StringComparison]::Ordinal)) { return $boundary }
    $projectMatch = [regex]::Match($markerText, "(?m)^project=vayujit-pc-cert-([a-f0-9]{10})\s*$")
    $volumeMatch = [regex]::Match($markerText, "(?m)^volume_prefix=vayujit_pc_cert_([a-f0-9]{10})\s*$")
    if (-not $projectMatch.Success -or -not $volumeMatch.Success -or $projectMatch.Groups[1].Value -ne $volumeMatch.Groups[1].Value) { return $boundary }

    $boundary.IsValid = $true
    $boundary.ReportPath = $reportFull
    $boundary.BackupId = $projectMatch.Groups[1].Value
    return $boundary
  } catch {
    # Never surface path or filesystem exception text in a certification report.
    return $boundary
  }
}

function New-VayujitBootstrapFailureReport {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][string]$BackupId,
    [Parameter(Mandatory = $true)][string]$FailureCode,
    [Parameter(Mandatory = $true)][string]$FailureOperation
  )

  $safePair = switch ("$FailureCode|$FailureOperation") {
    "backup_arguments_invalid|backup child argument validation" { @("backup_arguments_invalid", "backup child argument validation"); break }
    "backup_initialization_failed|backup child initialization" { @("backup_initialization_failed", "backup child initialization"); break }
    "backup_preflight_failed|backup preflight" { @("backup_preflight_failed", "backup preflight"); break }
    default { @("backup_initialization_failed", "backup child initialization") }
  }
  $safeBackupId = if ($BackupId -match '^[A-Za-z0-9_-]{1,80}$') { $BackupId } else { "unavailable" }
  return [ordered]@{
    status = "FAIL"
    backup_id = $safeBackupId
    failure_code = $safePair[0]
    failure_operation = $safePair[1]
    native_exit_code = $null
    docker_exit_code = $null
    cleanup_failure = $null
    destination_independence = "UNVERIFIED"
    recovery_hint = "Review the recorded initialization or preflight stage. No partial backup was certified."
  }
}

function Write-VayujitBootstrapFailureReport {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][string]$ReportPath,
    [Parameter(Mandatory = $true)][System.Collections.IDictionary]$Report
  )

  try {
    $parent = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($ReportPath))
    if ([string]::IsNullOrWhiteSpace($parent) -or -not (Test-Path -LiteralPath $parent -PathType Container)) { return $false }
    $json = ConvertTo-Json -InputObject $Report -Depth 5
    [System.IO.File]::WriteAllText([System.IO.Path]::GetFullPath($ReportPath), ($json + "`n"), [System.Text.UTF8Encoding]::new($false))
    return $true
  } catch {
    # Deliberately return only a boolean. Callers use a reserved process exit
    # code so the parent can identify report-write failure without raw output.
    return $false
  }
}

function Stop-VayujitDisposableBackupBootstrap {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][object]$Boundary,
    [Parameter(Mandatory = $true)][string]$FailureCode,
    [Parameter(Mandatory = $true)][string]$FailureOperation
  )

  $safe = New-VayujitBootstrapFailureReport -BackupId ([string]$Boundary.BackupId) -FailureCode $FailureCode -FailureOperation $FailureOperation
  if ($Boundary.IsValid -and (Write-VayujitBootstrapFailureReport -ReportPath ([string]$Boundary.ReportPath) -Report $safe)) {
    throw ([string]$safe.failure_code)
  }

  $boundaryCode = if ($Boundary.IsValid) { "backup_evidence_report_write_failed" } else { [string]$safe.failure_code }
  if ($boundaryCode -notin @("backup_arguments_invalid", "backup_initialization_failed", "backup_preflight_failed", "backup_evidence_report_write_failed")) {
    $boundaryCode = "backup_initialization_failed"
  }
  [Console]::Out.WriteLine("VAYUJIT_BACKUP_CHILD_BOUNDARY=$boundaryCode")
  throw $boundaryCode
}
