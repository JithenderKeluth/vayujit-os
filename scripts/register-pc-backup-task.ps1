param(
  [string]$DataRoot = (Join-Path $env:LOCALAPPDATA "VAYUJIT OS"),
  [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')][string]$At = "02:00",
  [switch]$ConfirmRegistration
)
$ErrorActionPreference = "Stop"
$taskName = "VAYUJIT PC encrypted backup"
$script = Join-Path $PSScriptRoot "backup-pc-first.ps1"
$root = [System.IO.Path]::GetFullPath($DataRoot)
$markerPath = Join-Path $root "config\pc-install.json"
$composePath = Join-Path $root "config\compose.env"
$identityPath = Join-Path $root "config\backup.agekey"
foreach ($path in @($script, $markerPath, $composePath, $identityPath)) {
  if (-not (Test-Path -LiteralPath $path)) { throw "PC encrypted-backup prerequisites are missing; no task was registered." }
}
$marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
if ($marker.marker -ne "vayujit-pc-first-live-v1" -or $marker.activation -ne "owner_activated") {
  throw "Only the activated marker-protected VAYUJIT PC profile may schedule backups."
}
if (-not (Get-Command age -ErrorAction SilentlyContinue) -or -not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker Desktop and age must be available before scheduling backups."
}
if (-not $ConfirmRegistration) {
  throw "No task was registered. Rerun with -ConfirmRegistration after confirming the backup drive and schedule."
}
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -DataRoot `"$root`""
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 4) -DisallowStartIfOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Creates and verifies encrypted VAYUJIT PostgreSQL and media backups on the separately configured backup drive. Requires this Windows user to be signed in and Docker Desktop running." -Force | Out-Null
Write-Output "Registered '$taskName' daily at $At local time. It runs as the current user while signed in; connect the backup drive and start Docker Desktop."
