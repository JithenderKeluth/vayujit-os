$ErrorActionPreference = "Stop"

$backupScriptPath = Join-Path $PSScriptRoot "backup-pc-first.ps1"
$backupSource = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $backupScriptPath))
$tokens = $null
$parseErrors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($backupScriptPath, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -gt 0) {
  throw "Backup script has PowerShell parse errors: $($parseErrors[0].Message)"
}

$passed = 0
function Assert-Regression([bool]$Condition, [string]$Message) {
  if (-not $Condition) { throw $Message }
  $script:passed++
  Write-Output "PASS $Message"
}

$directExecCalls = @()
foreach ($scriptFile in Get-ChildItem -LiteralPath $PSScriptRoot -Filter "*.ps1" -File) {
  $scriptText = [System.IO.File]::ReadAllText($scriptFile.FullName)
  foreach ($call in [regex]::Matches($scriptText, '(?m)&\s+\$docker(?:\.Source)?\s+exec\b[^\r\n]*')) {
    $directExecCalls += [pscustomobject]@{ Path = $scriptFile.FullName; Text = $call.Value }
  }
}
Assert-Regression ($directExecCalls.Count -ge 1) "direct docker exec call sites across PC-first PowerShell scripts are inventoried"
$invalidDirectExecCalls = @($directExecCalls | Where-Object { $_.Text -match '\bexec\s+(?:-T|--no-TTY)(?:\s|$)' })
Assert-Regression ($invalidDirectExecCalls.Count -eq 0) "no direct docker exec call uses Compose-only no-TTY flags"
Assert-Regression (@($directExecCalls | Where-Object { $_.Path -eq $backupScriptPath }).Count -eq 1) "backup snapshot direct exec is isolated behind the validated capture helper"

$composeExecCalls = [regex]::Matches($backupSource, '(?m)&\s+\$docker\.Source\s+@composeArgs\s+exec\s+-T\b')
Assert-Regression ($composeExecCalls.Count -ge 1) "docker compose exec retains -T to disable Compose TTY allocation"

$helperStart = $backupSource.IndexOf('function Invoke-DockerExecCapturedOutput', [System.StringComparison]::Ordinal)
$mainTryStart = $backupSource.IndexOf("`ntry {", $helperStart, [System.StringComparison]::Ordinal)
if ($helperStart -lt 0 -or $mainTryStart -lt 0) { throw "Docker capture helper boundaries could not be located." }
$helperSource = $backupSource.Substring($helperStart, $mainTryStart - $helperStart)
Assert-Regression ($helperSource.Contains('$ErrorActionPreference = "Continue"') -and $helperSource.Contains('2>$null')) "native stderr cannot become a terminating PowerShell error or leak to console"
Assert-Regression ($helperSource.Contains('$exitCode = $LASTEXITCODE') -and $helperSource.Contains('Docker exit code $exitCode')) "direct Docker exit code and failing operation are preserved without raw stderr"
Assert-Regression ($helperSource.Contains('does not attach') -and $helperSource.Contains('exec $ContainerId @CommandArguments')) "direct exec keeps stdin unattached and captures stdout without a TTY"

$powerShellPath = (Get-Process -Id $PID -ErrorAction Stop).Path
$previousErrorActionPreference = $ErrorActionPreference
try {
  $ErrorActionPreference = "Continue"
  $successfulProbe = & $powerShellPath -NoLogo -NoProfile -NonInteractive -Command "[Console]::Out.WriteLine('docker-stdout-probe'); [Console]::Error.WriteLine('docker-stderr-warning-probe'); exit 0" 2>$null
  $successfulProbeExit = $LASTEXITCODE
  $failedProbe = & $powerShellPath -NoLogo -NoProfile -NonInteractive -Command "[Console]::Error.WriteLine('docker-stderr-failure-probe'); exit 37" 2>$null
  $failedProbeExit = $LASTEXITCODE
} finally {
  $ErrorActionPreference = $previousErrorActionPreference
}
Assert-Regression ($successfulProbeExit -eq 0 -and ($successfulProbe -join "") -match 'docker-stdout-probe') "native stderr warning is discarded safely while stdout and successful exit are retained"
Assert-Regression ($failedProbeExit -eq 37 -and -not ($failedProbe -join "")) "native stderr failure is hidden while the genuine nonzero exit code remains available"

$workerStoppedAt = $backupSource.IndexOf('$workerStopped = $true', [System.StringComparison]::Ordinal)
$workerStopAt = $backupSource.IndexOf('stop --timeout 45 worker', [System.StringComparison]::Ordinal)
$apiStoppedAt = $backupSource.IndexOf('$apiStopped = $true', [System.StringComparison]::Ordinal)
$apiStopAt = $backupSource.IndexOf('stop --timeout 30 api', [System.StringComparison]::Ordinal)
$finallyAt = $backupSource.LastIndexOf('} finally {', [System.StringComparison]::Ordinal)
$recoverySource = if ($finallyAt -ge 0) { $backupSource.Substring($finallyAt) } else { "" }
Assert-Regression ($workerStoppedAt -ge 0 -and $workerStopAt -gt $workerStoppedAt -and $apiStoppedAt -ge 0 -and $apiStopAt -gt $apiStoppedAt) "service recovery flags are armed before disposable API and worker stops"
Assert-Regression ($recoverySource.Contains('start api') -and $recoverySource.Contains('start worker') -and $recoverySource.Contains('maintenance-off --confirm')) "failure cleanup restarts API and worker and clears only owned maintenance after API health"
$caughtFailureAt = $backupSource.IndexOf('$caughtFailure = $_', [System.StringComparison]::Ordinal)
$catchStart = if ($caughtFailureAt -ge 0) { $backupSource.LastIndexOf('} catch {', $caughtFailureAt, [System.StringComparison]::Ordinal) } else { -1 }
$catchSource = if ($catchStart -ge 0 -and $finallyAt -gt $catchStart) { $backupSource.Substring($catchStart, $finallyAt - $catchStart) } else { "" }
Assert-Regression ($catchSource.Contains('-FailureOperation $failureOperation') -and $catchSource.Contains('-DockerExitCode $dockerFailureExitCode') -and $catchSource.Contains('$nativeFailureExitCode')) "backup failure report preserves the failing operation and original native/Docker exit code"
Assert-Regression ($catchSource.Contains('$backupFailureMessage =') -and $catchSource -notmatch 'throw\s+"Encrypted backup failed') "primary failure is retained while finally recovery executes before rethrow"

Write-Output "PC-first Docker exec regression checks: $passed passed."
