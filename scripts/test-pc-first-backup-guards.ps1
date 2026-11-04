$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "pc-first-key-security.psm1") -Force
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$runId = [guid]::NewGuid().ToString("N")
$guardRoot = Join-Path $tempRoot "vayujit-backup-guard-$runId"
$destinationRoot = Join-Path $tempRoot "vayujit-backup-guard-destination-$runId"
$backupScript = Join-Path $PSScriptRoot "backup-pc-first.ps1"
$expectedBase = $tempRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)

function Assert-RejectedBeforeRuntime([string]$Name, [string]$DataRoot, [bool]$Disposable, [string]$ExpectedMessage) {
  # Hashtable splatting is required for named script parameters. Array
  # splatting forwards these strings positionally and silently tests the
  # missing-profile guard instead of the intended disposable marker guard.
  $arguments = @{
    DataRoot = $DataRoot
    BackupDestination = $destinationRoot
    BackupReportPath = (Join-Path $DataRoot "report.json")
  }
  if ($Disposable) { $arguments.DisposableCertification = $true }
  if ($Disposable) {
    $testPowerShellPath = (Get-Process -Id $PID -ErrorAction Stop).Path
    $childArguments = @("-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", $backupScript, "-DataRoot", $DataRoot, "-DisposableCertification", "-BackupDestination", $destinationRoot, "-BackupReportPath", (Join-Path $DataRoot "report.json"))
    $child = Invoke-VayujitNativeCapture -FilePath $testPowerShellPath -Arguments $childArguments
    $expectedCode = if ($ExpectedMessage -eq "PC profile has not been initialized") { "backup_preflight_failed" } else { "backup_arguments_invalid" }
    if ($child.ExitCode -eq 0 -or $child.StdOut -notmatch "(?m)^VAYUJIT_BACKUP_CHILD_BOUNDARY=$expectedCode\s*$") {
      throw "Guard regression: '$Name' was not rejected with the expected safe boundary code."
    }
  } else {
    $failureMessage = $null
    try { & $backupScript @arguments | Out-Null } catch { $failureMessage = $_.Exception.Message }
    if (-not $failureMessage -or $failureMessage -notmatch $ExpectedMessage) {
      throw "Guard regression: '$Name' was not rejected as expected. Actual failure: $failureMessage"
    }
  }
  Write-Output "PASS $Name"
}

try {
  # Missing profile markers must fail before Docker/age discovery or any I/O.
  Assert-RejectedBeforeRuntime "permanent profile requires its activation marker" $guardRoot $false "PC profile has not been initialized"
  Assert-RejectedBeforeRuntime "disposable profile requires its marker" $guardRoot $true "PC profile has not been initialized"

  New-Item -ItemType Directory -Path (Join-Path $guardRoot "config") -Force | Out-Null
  [System.IO.File]::WriteAllText(
    (Join-Path $guardRoot "disposable-profile.marker"),
    "not-a-vayujit-profile`nproject=vayujit-pc-business`nvolume_prefix=vayujit_pc_business`n",
    [System.Text.UTF8Encoding]::new($false)
  )
  [System.IO.File]::WriteAllText((Join-Path $guardRoot "config\compose.env"), "", [System.Text.UTF8Encoding]::new($false))
  Assert-RejectedBeforeRuntime "disposable mode rejects a non-disposable marker" $guardRoot $true "Disposable profile marker is missing or invalid"

  [System.IO.File]::WriteAllText(
    (Join-Path $guardRoot "disposable-profile.marker"),
    "vayujit-pc-disposable-certification-v1`nproject=vayujit-pc-business`nvolume_prefix=vayujit_pc_business`n",
    [System.Text.UTF8Encoding]::new($false)
  )
  Assert-RejectedBeforeRuntime "disposable mode rejects the permanent business project identity" $guardRoot $true "Disposable project and volume names do not match"
  Write-Output "Backup target guard checks passed: 4/4. No Docker command or database was used."
} finally {
  $resolvedGuardRoot = [System.IO.Path]::GetFullPath($guardRoot)
  $resolvedDestinationRoot = [System.IO.Path]::GetFullPath($destinationRoot)
  if (-not $resolvedGuardRoot.StartsWith($expectedBase + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean a guard fixture outside the system temporary directory."
  }
  if (-not $resolvedDestinationRoot.StartsWith($expectedBase + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean a guard destination outside the system temporary directory."
  }
  foreach ($path in @($resolvedGuardRoot, $resolvedDestinationRoot)) {
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
  }
}
