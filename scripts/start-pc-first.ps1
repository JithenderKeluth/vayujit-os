param(
  [ValidateSet("start", "stop", "status", "open")][string]$Command = "start",
  [string]$DataRoot = (Join-Path $env:LOCALAPPDATA "VAYUJIT OS"),
  [switch]$Rebuild,
  [switch]$OpenBrowser
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$configRoot = Join-Path ([System.IO.Path]::GetFullPath($DataRoot)) "config"
$markerPath = Join-Path $configRoot "pc-install.json"
$composeEnvPath = Join-Path $configRoot "compose.env"
$appEnvPath = Join-Path $configRoot "app.env"
foreach ($required in @($markerPath, $composeEnvPath, $appEnvPath)) {
  if (-not (Test-Path -LiteralPath $required)) {
    throw "PC profile is not initialized. Run scripts/initialize-pc-first.ps1 with a separate-drive BackupRoot first."
  }
}
$marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
if ($marker.marker -ne "vayujit-pc-first-live-v1" -or $marker.volume_prefix -ne "vayujit_pc_business") {
  throw "PC install marker did not match the protected business-volume identity."
}
if ((Resolve-Path -LiteralPath $marker.data_root).Path -ne [System.IO.Path]::GetFullPath($DataRoot)) {
  throw "PC data root does not match its protected install marker."
}

$composeFile = Join-Path $repo "infrastructure\docker-compose.pc.yml"
$project = "vayujit-pc-business"
$port = 8443
foreach ($line in Get-Content -LiteralPath $composeEnvPath) {
  if ($line -match '^VAYUJIT_PC_PROJECT_NAME=(.+)$') { $project = $Matches[1] }
  if ($line -match '^VAYUJIT_PC_HTTP_PORT=(\d+)$') { $port = [int]$Matches[1] }
}
if ($project -ne "vayujit-pc-business" -or $port -lt 1024 -or $port -gt 65535) {
  throw "PC project or loopback port configuration is outside the supported profile."
}
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) { throw "Docker Desktop with the WSL2 engine is required. Start Docker Desktop, then retry." }
$composeArgs = @("compose", "--project-name", $project, "-f", $composeFile, "--env-file", $composeEnvPath)

switch ($Command) {
  "start" {
    $initialActivation = $marker.activation -eq "prepared_not_started"
    if ($marker.activation -eq "prepared_not_started") {
      Write-Host "This starts VAYUJIT's persistent business database and applies the repository migrations. No demo records are seeded."
      Write-Host "Database: $($marker.database_name); media and PostgreSQL volumes are named and retained across stop/restart."
      $confirmation = Read-Host "Type START VAYUJIT BUSINESS DATABASE to continue"
      if ($confirmation -cne "START VAYUJIT BUSINESS DATABASE") { throw "Initial activation was not confirmed; nothing was started." }
      $marker.activation = "owner_activated"
      $marker.activated_at_utc = [DateTime]::UtcNow.ToString("o")
      [System.IO.File]::WriteAllText($markerPath, (($marker | ConvertTo-Json -Depth 6) + "`n"), [System.Text.UTF8Encoding]::new($false))
    }
    if ($Rebuild -and -not $initialActivation) {
      $backupStatusPath = Join-Path $marker.backup_root "last-backup-status.json"
      if (-not (Test-Path -LiteralPath $backupStatusPath)) {
        throw "Rebuild is blocked until scripts/backup-pc-first.ps1 completes a verified encrypted backup."
      }
      $backupStatus = Get-Content -LiteralPath $backupStatusPath -Raw | ConvertFrom-Json
      $backupTime = [DateTime]::Parse([string]$backupStatus.created_at_utc).ToUniversalTime()
      if ($backupStatus.status -ne "success" -or [DateTime]::UtcNow - $backupTime -gt [TimeSpan]::FromHours(24)) {
        throw "Rebuild is blocked: require a successful verified encrypted backup created within the last 24 hours."
      }
    }
    & docker @composeArgs config --quiet
    if ($LASTEXITCODE -ne 0) { throw "PC Compose validation failed; services were not started." }
    if ($initialActivation -or $Rebuild) {
      & docker @composeArgs up --build --detach
    } else {
      & docker @composeArgs up --detach
    }
    if ($LASTEXITCODE -ne 0) { throw "Docker could not start the PC profile. Existing named volumes were left intact." }
    $url = "http://127.0.0.1:$port"
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
      try {
        $response = Invoke-WebRequest -Uri "$url/health/ready" -TimeoutSec 4 -UseBasicParsing
        if ($response.StatusCode -eq 200) { $ready = $true; break }
      } catch { Start-Sleep -Seconds 3 }
    }
    if (-not $ready) {
      & docker @composeArgs ps
      throw "Services started but readiness did not pass. Data volumes were retained; inspect Docker health and logs."
    }
    Write-Output "VAYUJIT OS is ready at $url"
    Write-Output "First run: complete the real owner setup in the browser. Do not import demo or certification data."
    if ($OpenBrowser) { Start-Process $url }
  }
  "stop" {
    & docker @composeArgs stop --timeout 60
    if ($LASTEXITCODE -ne 0) { throw "Could not stop all services cleanly. Named data volumes were preserved." }
    Write-Output "VAYUJIT OS stopped cleanly. PostgreSQL and media volumes were preserved."
  }
  "status" {
    & docker @composeArgs ps
    if ($LASTEXITCODE -ne 0) { throw "Could not read Docker Compose status." }
    $backupStatus = Join-Path $marker.backup_root "last-backup-status.json"
    if (Test-Path -LiteralPath $backupStatus) {
      Write-Output "Encrypted backup status:"
      Get-Content -LiteralPath $backupStatus
    } else {
      Write-Output "Encrypted backup status: no successful PC backup recorded yet."
    }
    try {
      $response = Invoke-WebRequest -Uri "http://127.0.0.1:$port/health/ready" -TimeoutSec 4 -UseBasicParsing
      Write-Output "Application readiness: HTTP $($response.StatusCode)"
    } catch { Write-Output "Application readiness: unavailable" }
  }
  "open" {
    Start-Process "http://127.0.0.1:$port"
  }
}
