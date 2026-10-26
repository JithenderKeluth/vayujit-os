param(
  [string]$EvidencePath,
  [string]$BackupDestination
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Import-Module (Join-Path $PSScriptRoot "pc-first-key-security.psm1") -Force
Import-Module (Join-Path $PSScriptRoot "pc-first-backup-artifacts.psm1") -Force
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$docker = if ($dockerCommand) { $dockerCommand.Source } else { $null }
if (-not $docker -and $env:ProgramFiles) {
  $programFilesDocker = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe"
  if (Test-Path -LiteralPath $programFilesDocker -ErrorAction SilentlyContinue) { $docker = $programFilesDocker }
}
if (-not $docker -and $env:LOCALAPPDATA) {
  $userDocker = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin\docker.exe"
  try { if (Test-Path -LiteralPath $userDocker -ErrorAction Stop) { $docker = $userDocker } } catch { }
}
if (-not $docker) { throw "Docker Desktop CLI is unavailable in PATH or approved standard install locations." }
$version = & $docker version --format '{{.Server.Version}}' 2>$null
if ($LASTEXITCODE -ne 0 -or -not $version) { throw "Docker Desktop engine is unavailable." }

$id = [guid]::NewGuid().ToString("N").Substring(0, 10)
$project = "vayujit-pc-cert-$id"
$volumePrefix = "vayujit_pc_cert_$id"
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) "vayujit-pc-disposable-$id"
$markerPath = Join-Path $tempRoot "disposable-profile.marker"
$configRoot = Join-Path $tempRoot "config"
$composeFile = Join-Path $repo "infrastructure\docker-compose.pc.yml"
$appEnvPath = Join-Path $configRoot "app.env"
$composeEnvPath = Join-Path $configRoot "compose.env"
$evidenceFile = Join-Path $tempRoot "api-evidence.json"
$chromeProfile = Join-Path $tempRoot "chrome-profile"
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$chromePortProbe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$chromePortProbe.Start()
$chromePort = $chromePortProbe.LocalEndpoint.Port
$chromePortProbe.Stop()
$browserProcess = $null
$composeArgs = @("compose", "--project-name", $project, "-f", $composeFile, "--env-file", $composeEnvPath)
$portProbe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$portProbe.Start()
$port = $portProbe.LocalEndpoint.Port
$portProbe.Stop()
$origin = "http://127.0.0.1:$port"
$email = "pc-cert-$id@example.com"
$ownerPassword = "PC-Cert-$id-" + [guid]::NewGuid().ToString("N") + "!9a"
$report = [ordered]@{
  profile = "pc-first-disposable-certification"
  status = "RUNNING"
  pc_first_classification = ("PC-FIRST DEPLOYMENT " + [char]0x2014 + " IMPLEMENTED / CERTIFICATION PENDING")
  docker_version = $version
  project = $project
  port = $port
  checks = [System.Collections.Generic.List[object]]::new()
  backup_restore = ([ordered]@{ status = "NOT_RUN"; destination_independence = "UNVERIFIED" })
  error = $null
  diagnostic_log_tail = $null
}
$started = $false
$backupExecutionStarted = $false
$backupExecutionCompleted = $false
$backupReportPath = $null
$backupChildLaunchSucceeded = $false
$backupChildExitCode = $null
$backupChildBoundaryCode = $null
$backupChildResolution = $null

function Add-Check([string]$Name, [bool]$Passed, [string]$Evidence = "") {
  $report.checks.Add([ordered]@{ name = $Name; status = $(if ($Passed) { "PASS" } else { "FAIL" }); evidence = $Evidence })
  Write-Output "[$(if ($Passed) { 'PASS' } else { 'FAIL' })] $Name $Evidence"
  if (-not $Passed) { throw "Disposable certification failed: $Name $Evidence" }
}
function New-HexSecret([int]$Length = 32) {
  $bytes = New-Object byte[] $Length
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  [BitConverter]::ToString($bytes).Replace("-", "").ToLowerInvariant()
}
function Write-EnvFile([string]$Path, [string[]]$Lines) {
  [System.IO.File]::WriteAllLines($Path, $Lines, [System.Text.UTF8Encoding]::new($false))
}

try {
New-Item -ItemType Directory -Path $configRoot -Force | Out-Null
Set-VayujitPrivateAcl -Path $configRoot -Kind Directory
[System.IO.File]::WriteAllText($markerPath, "vayujit-pc-disposable-certification-v1`nproject=$project`nvolume_prefix=$volumePrefix`n", [System.Text.UTF8Encoding]::new($false))
$rootPassword = New-HexSecret 36
$appPassword = New-HexSecret 36
$sessionSecret = New-HexSecret 48
$credentialBytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($credentialBytes) } finally { $rng.Dispose() }
$credentialKey = [Convert]::ToBase64String($credentialBytes)
$appLines = @(
  "VAYUJIT_ENVIRONMENT=pc_local", "VAYUJIT_DEBUG=false",
  "VAYUJIT_DATABASE_URL=postgresql+psycopg://vayujit_app:$appPassword@postgres:5432/vayujit_business",
  "VAYUJIT_WEB_ORIGIN=$origin", "VAYUJIT_ALLOWED_ORIGINS=$origin,http://localhost:$port",
  "VAYUJIT_SESSION_SECRET=$sessionSecret", "VAYUJIT_SESSION_LIFETIME_HOURS=12",
  "VAYUJIT_SESSION_SECURE_COOKIE=false", "VAYUJIT_SESSION_SAME_SITE=strict",
  "VAYUJIT_ALLOW_MISSING_ORIGIN=false", "VAYUJIT_REQUIRE_HTTPS=false",
  "VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP=true", "VAYUJIT_LIVE_AI_ENABLED=false",
  "VAYUJIT_LIVE_SOCIAL_PUBLISHING_ENABLED=false", "VAYUJIT_LIVE_MARKETPLACE_MUTATIONS_ENABLED=false",
  "VAYUJIT_LIVE_ADS_MUTATIONS_ENABLED=false", "VAYUJIT_ADS_LIVE_SPEND_ENABLED=false",
  "VAYUJIT_EMAIL_DELIVERY_ENABLED=false", "VAYUJIT_LIVE_EMAIL_DELIVERY_ENABLED=false",
  "VAYUJIT_SHOPIFY_LIVE_MUTATION_ENABLED=false", "VAYUJIT_PUBLISHING_WORKER_ENABLED=true",
  "VAYUJIT_CREDENTIAL_ENCRYPTION_KEY=$credentialKey", "VAYUJIT_CREDENTIAL_ENCRYPTION_KEY_ID=pc-cert",
  "VAYUJIT_STORAGE_PROVIDER=filesystem", "VAYUJIT_MEDIA_STORAGE_DIRECTORY=/var/lib/vayujit/media",
  "VAYUJIT_BACKUP_DIRECTORY=/var/lib/vayujit/backups", "VAYUJIT_MAINTENANCE_MARKER=/var/lib/vayujit/maintenance/enabled",
  "VAYUJIT_BACKUP_RETENTION_DAYS=90", "VAYUJIT_EXPECTED_MIGRATION_REVISION=20261203_0146",
  "VAYUJIT_TRUSTED_PROXY_IPS=172.16.0.0/12"
)
$composeLines = @(
  "VAYUJIT_PC_PROJECT_NAME=$project", "VAYUJIT_PC_VOLUME_PREFIX=$volumePrefix",
  "VAYUJIT_PC_HTTP_PORT=$port", "VAYUJIT_PC_APP_ENV_FILE=$($appEnvPath.Replace('\', '/'))",
  "POSTGRES_DB=postgres", "POSTGRES_USER=postgres", "POSTGRES_PASSWORD=$rootPassword",
  "VAYUJIT_DATABASE_NAME=vayujit_business", "VAYUJIT_DATABASE_USER=vayujit_app",
  "VAYUJIT_DATABASE_PASSWORD=$appPassword"
)
if ($BackupDestination) {
  $ageCommand = Get-Command age -ErrorAction SilentlyContinue
  $ageKeygenCommand = Get-Command age-keygen -ErrorAction SilentlyContinue
  if (-not $ageCommand -or -not $ageKeygenCommand) { throw "Encrypted backup rehearsal requested; install the approved age Windows package first (see the backup/recovery guide)." }
  $identityPath = Join-Path $configRoot "disposable-backup.agekey"
  $ageRecipient = New-VayujitPrivateAgeIdentity -AgeKeygenPath $ageKeygenCommand.Source -IdentityPath $identityPath
  $composeLines += "VAYUJIT_PC_AGE_RECIPIENT=$ageRecipient"
  $composeLines += "VAYUJIT_PC_BACKUP_RETENTION_DAYS=90"
}
Write-EnvFile $appEnvPath $appLines
Write-EnvFile $composeEnvPath $composeLines

  & $docker @composeArgs config --quiet
  Add-Check "Compose configuration" ($LASTEXITCODE -eq 0) "Disposable project=$project"
  & $docker @composeArgs up --build --detach
  if ($LASTEXITCODE -ne 0) { throw "Isolated PC Compose stack did not start." }
  $started = $true

  $ready = $false
  for ($attempt = 0; $attempt -lt 100; $attempt++) {
    try {
      $response = Invoke-WebRequest -Uri "$origin/health/ready" -TimeoutSec 3 -UseBasicParsing
      if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Seconds 3 }
  }
  Add-Check "nginx-proxied production readiness" $ready $origin

  $serviceIds = @(& $docker @composeArgs ps -q)
  Add-Check "all Compose services created" ($serviceIds.Count -eq 5) "count=$($serviceIds.Count)"
  foreach ($network in @("$project`_data", "$project`_app")) {
    $internal = (& $docker network inspect --format '{{.Internal}}' $network) -join ""
    Add-Check "$network is internal and isolated" ($LASTEXITCODE -eq 0 -and $internal -eq "true") $network
  }
  $edgeNetwork = "$project`_edge"
  $edgeOptions = ((& $docker network inspect --format '{{json .Options}}' $edgeNetwork) -join "") | ConvertFrom-Json
  $edgeMasquerade = $edgeOptions.'com.docker.network.bridge.enable_ip_masquerade'
  Add-Check "proxy-only edge bridge has outbound masquerading disabled" ($LASTEXITCODE -eq 0 -and $edgeMasquerade -eq "false") $edgeNetwork
  $proxyId = (& $docker @composeArgs ps -q proxy) -join ""
  $proxyPorts = (& $docker port $proxyId 2>$null) -join ""
  $proxyNetworkPorts = (& $docker inspect --format '{{json .NetworkSettings.Ports}}' $proxyId) -join ""
  Add-Check "only proxy publishes loopback port" ($proxyPorts -match "127\.0\.0\.1:$port" -and $proxyPorts -notmatch "0\.0\.0\.0" -and $proxyNetworkPorts -match "127\.0\.0\.1") "$proxyPorts $proxyNetworkPorts"
  $probePreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  $edgeProbe = & $docker exec $proxyId wget -q -T 3 -O /dev/null http://192.0.2.1/ 2>&1
  $edgeProbeExit = $LASTEXITCODE
  $ErrorActionPreference = $probePreference
  $edgeProbeBlocked = $edgeProbeExit -ne 0
  Add-Check "proxy cannot reach reserved TEST-NET egress probe" $edgeProbeBlocked ($edgeProbe -join " ")
  $boundPortsValid = $true
  foreach ($containerId in $serviceIds) {
    $name = (& $docker inspect --format '{{.Name}}' $containerId) -join ""
    $name = $name.TrimStart('/')
    $bindings = (& $docker inspect --format '{{json .NetworkSettings.Ports}}' $containerId) -join ""
    if ($name -like "*$project*" -and $name -notlike "*$($project)-proxy*" -and $bindings -match 'HostPort') { $boundPortsValid = $false }
  }
  Add-Check "database and app services have no host ports" $boundPortsValid
  $headers = Invoke-WebRequest -Uri $origin -TimeoutSec 10 -UseBasicParsing
  Add-Check "browser app served with security headers" ($headers.Headers["X-Content-Type-Options"] -eq "nosniff" -and $headers.Headers["X-Frame-Options"] -eq "DENY") "HTTP $($headers.StatusCode)"

  $env:PC_CERT_ORIGIN = $origin
  $env:PC_CERT_EMAIL = $email
  $env:PC_CERT_PASSWORD = $ownerPassword
  $env:PC_CERT_EVIDENCE = $evidenceFile
  $env:PC_CERT_PRODUCT_ID = ""
  $env:PC_CERT_INVENTORY_ID = ""
  $env:PC_CERT_MEDIA_ID = ""
  $env:PC_CERT_COST_ID = ""
  $nodeSeed = & node (Join-Path $repo "scripts\pc-first-disposable-api-check.mjs") seed 2>&1
  if ($LASTEXITCODE -ne 0) { throw "Canonical API seeding failed: $($nodeSeed -join ' ')" }
  Add-Check "real canonical API owner/product/cost/media onboarding" $true "synthetic disposable fixture persisted; identifiers retained only in local fixture evidence"

  if ($BackupDestination) {
    $backupReportPath = Join-Path $tempRoot "backup-rehearsal.json"
    $env:PC_CERT_DOCKER_PATH = $docker
    $backupExecutionStarted = $true
    try {
      $childPowerShellPath = (Get-Process -Id $PID -ErrorAction Stop).Path
      if (-not $childPowerShellPath -or -not (Test-Path -LiteralPath $childPowerShellPath -PathType Leaf)) {
        $powerShellCommand = Get-Command powershell.exe -ErrorAction SilentlyContinue
        if (-not $powerShellCommand) { $powerShellCommand = Get-Command pwsh.exe -ErrorAction SilentlyContinue }
        if ($powerShellCommand) { $childPowerShellPath = $powerShellCommand.Source }
      }
      if (-not $childPowerShellPath -or -not (Test-Path -LiteralPath $childPowerShellPath -PathType Leaf)) {
        throw "PowerShell executable unavailable for isolated backup invocation."
      }
      $childBackupScript = Join-Path $PSScriptRoot "backup-pc-first.ps1"
      $childProcessResult = Invoke-VayujitNativeCapture -FilePath $childPowerShellPath -Arguments @(
        "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", $childBackupScript,
        "-DataRoot", $tempRoot, "-DisposableCertification", "-BackupDestination", $BackupDestination,
        "-BackupReportPath", $backupReportPath
      ) -RemoveEnvironmentVariables @(
        "PC_CERT_ORIGIN", "PC_CERT_EMAIL", "PC_CERT_PASSWORD", "PC_CERT_EVIDENCE",
        "PC_CERT_PRODUCT_ID", "PC_CERT_INVENTORY_ID", "PC_CERT_MEDIA_ID", "PC_CERT_COST_ID",
        "PC_CERT_CDP_PORT", "PC_CERT_SCREENSHOT_DIR"
      )
      $backupChildLaunchSucceeded = $true
      $backupChildExitCode = [int]$childProcessResult.ExitCode
      $boundaryMatch = [regex]::Match([string]$childProcessResult.StdOut, '(?m)^VAYUJIT_BACKUP_CHILD_BOUNDARY=(backup_evidence_report_write_failed|backup_initialization_failed|backup_arguments_invalid|backup_preflight_failed)\s*$')
      if ($boundaryMatch.Success) { $backupChildBoundaryCode = $boundaryMatch.Groups[1].Value }
      # Only a fixed allowlisted boundary token is consumed; raw stdout/stderr are never persisted.
      $childProcessResult = $null
    } catch {
      $backupChildLaunchSucceeded = $false
      $backupChildExitCode = $null
    }
    $backupChildResolution = Resolve-VayujitBackupChildReport `
      -LaunchSucceeded $backupChildLaunchSucceeded `
      -ProcessExitCode $backupChildExitCode `
      -ReportPath $backupReportPath `
      -FallbackBackupId $id `
      -BootstrapFailureCode $backupChildBoundaryCode
    if ($backupChildResolution.Status -ne "PASS") { throw "Disposable backup rehearsal did not pass its structured validation." }
    $report.backup_restore = $backupChildResolution.Report
    Add-Check "encrypted disposable backup, negative-key tests, canonical DB comparison, media restore, and source integrity" $true ("backup_seconds={0}; restore_seconds={1}; destination={2}" -f $report.backup_restore.backup_duration_seconds,$report.backup_restore.restore_duration_seconds,$report.backup_restore.destination_independence)
    $backupExecutionCompleted = $true
  }

  if (-not (Test-Path -LiteralPath $chromePath)) { throw "Isolated Chrome executable was not found at the expected Windows path." }
  New-Item -ItemType Directory -Path $chromeProfile -Force | Out-Null
  $browserProcess = Start-Process -FilePath $chromePath -WindowStyle Hidden -PassThru -ArgumentList @(
    "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
    "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=$chromePort",
    "--remote-allow-origins=*", "--user-data-dir=$chromeProfile", "$origin/login"
  )
  $cdpReady = $false
  for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
      $versionResponse = Invoke-WebRequest -Uri "http://127.0.0.1:$chromePort/json/version" -TimeoutSec 2 -UseBasicParsing
      if ($versionResponse.StatusCode -eq 200) { $cdpReady = $true; break }
    } catch { Start-Sleep -Seconds 1 }
  }
  Add-Check "isolated Chrome CDP starts on loopback" $cdpReady "port=$chromePort"
  $env:PC_CERT_CDP_PORT = "$chromePort"
  $env:PC_CERT_PRODUCT_ID = (Get-Content -LiteralPath $evidenceFile -Raw | ConvertFrom-Json).product_id
  $env:PC_CERT_INVENTORY_ID = (Get-Content -LiteralPath $evidenceFile -Raw | ConvertFrom-Json).inventory_item_id
  $env:PC_CERT_SCREENSHOT_DIR = Join-Path $repo "docs\seller-os\artifacts"
  New-Item -ItemType Directory -Path $env:PC_CERT_SCREENSHOT_DIR -Force | Out-Null
  $nodeBrowser = & node (Join-Path $repo "scripts\pc-first-disposable-browser-check.mjs") 2>&1
  $browserJsonLine = $nodeBrowser | Where-Object {
    $line = $_.ToString().TrimStart()
    $line.StartsWith("{") -and $line.Contains(([string][char]34 + "mode" + [char]34))
  } | Select-Object -Last 1
  if (-not $browserJsonLine) { throw "Authenticated isolated Chrome produced no structured report: $($nodeBrowser -join ' ')" }
  $browserReport = "$browserJsonLine" | ConvertFrom-Json
  $report.browser = $browserReport
  if ($LASTEXITCODE -ne 0 -or $browserReport.status -ne "PASS") {
    Add-Check "authenticated isolated Chrome certification" $false ($browserReport.error -replace "\s+", " ")
    throw "Authenticated isolated Chrome certification failed: $($browserReport.error -replace '\s+', ' ')"
  }
  Add-Check "authenticated Chrome, keyboard, responsive, product/catalog deep links, refresh and axe scan" ($browserReport.status -eq "PASS") "checks=$($browserReport.checks.Count); axe-pages=$($browserReport.axe.Count); viewport-checks=$($browserReport.viewports.Count)"

  & $docker @composeArgs stop --timeout 60
  if ($LASTEXITCODE -ne 0) { throw "Disposable stack stopped unsuccessfully." }
  & $docker @composeArgs start
  if ($LASTEXITCODE -ne 0) { throw "Disposable stack could not restart." }
  $readyAfterRestart = $false
  for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
      $response = Invoke-WebRequest -Uri "$origin/health/ready" -TimeoutSec 3 -UseBasicParsing
      if ($response.StatusCode -eq 200) { $readyAfterRestart = $true; break }
    } catch { Start-Sleep -Seconds 3 }
  }
  Add-Check "whole stack readiness after persistent-volume restart" $readyAfterRestart
  $nodeVerify = & node (Join-Path $repo "scripts\pc-first-disposable-api-check.mjs") verify 2>&1
  if ($LASTEXITCODE -ne 0) { throw "Persistence/security verification failed: $($nodeVerify -join ' ')" }
  Add-Check "owner auth, catalog, cost, inventory, media persistence and denied external writes" $true "persistence and external-write denial assertions passed"

  $workerId = (& $docker @composeArgs ps -q worker) -join ""
  $workerHealth = "starting"
  for ($attempt = 0; $attempt -lt 30; $attempt++) {
    $workerHealth = (& $docker inspect --format '{{.State.Health.Status}}' $workerId) -join ""
    if ($LASTEXITCODE -eq 0 -and $workerHealth -eq "healthy") { break }
    Start-Sleep -Seconds 2
  }
  Add-Check "publishing worker becomes healthy after persistent-volume restart" ($LASTEXITCODE -eq 0 -and $workerHealth -eq "healthy") $workerHealth
  $workerNetworks = ((& $docker inspect --format '{{json .NetworkSettings.Networks}}' $workerId) -join "") | ConvertFrom-Json
  $workerNetworkNames = @($workerNetworks.PSObject.Properties.Name)
  Add-Check "worker has only the internal data network" ($workerNetworkNames.Count -eq 1 -and $workerNetworkNames[0] -eq "$project`_data") ($workerNetworkNames -join ",")
  $report.status = "PASS"
  if ($report.backup_restore.status -eq "PASS" -and $report.backup_restore.destination_independence -eq "VERIFIED_DIFFERENT_PHYSICAL_DISK") {
    $report.pc_first_classification = ("PC-FIRST DEPLOYMENT " + [char]0x2014 + " READY FOR HUMAN-CONTROLLED REAL-DATA ACTIVATION")
  }
} catch {
  $report.status = "FAIL"
  if ($backupExecutionStarted -and -not $backupExecutionCompleted) {
    if (-not $backupChildResolution) {
      $backupChildResolution = Resolve-VayujitBackupChildReport `
        -LaunchSucceeded $backupChildLaunchSucceeded `
        -ProcessExitCode $backupChildExitCode `
        -ReportPath $backupReportPath `
        -FallbackBackupId $id `
        -BootstrapFailureCode $backupChildBoundaryCode
    }
    Set-VayujitDisposableBackupFailure -Certification $report -BackupFailure $backupChildResolution.Failure
  } else {
    $report.error = "Disposable certification failed outside the backup stage. Review the local PowerShell error interactively; raw diagnostics were omitted from the report."
  }
  if ($started) {
    $report.diagnostic_log_tail = "Omitted to prevent credentials, private material, or customer data from entering the certification report."
  }
  throw $report.error
} finally {
  Remove-Item Env:PC_CERT_ORIGIN, Env:PC_CERT_EMAIL, Env:PC_CERT_PASSWORD, Env:PC_CERT_EVIDENCE, Env:PC_CERT_PRODUCT_ID, Env:PC_CERT_INVENTORY_ID, Env:PC_CERT_MEDIA_ID, Env:PC_CERT_COST_ID, Env:PC_CERT_CDP_PORT, Env:PC_CERT_SCREENSHOT_DIR, Env:PC_CERT_DOCKER_PATH -ErrorAction SilentlyContinue
  if ($browserProcess) {
    $browserCommand = "--user-data-dir=$chromeProfile"
    $browserMatches = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "chrome.exe" -and $_.CommandLine -and $_.CommandLine.Contains($browserCommand) }
    foreach ($browserMatch in $browserMatches) { Stop-Process -Id $browserMatch.ProcessId -Force -ErrorAction SilentlyContinue }
  }
  if ((Test-Path -LiteralPath $markerPath) -and (Get-Content -LiteralPath $markerPath -Raw).Contains("project=$project") -and (Get-Content -LiteralPath $markerPath -Raw).Contains("volume_prefix=$volumePrefix")) {
    $restorePreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
      if ($started) { & $docker @composeArgs down --remove-orphans *> $null }
      foreach ($suffix in @("_postgres_data", "_media_data", "_runtime_control")) {
        $volume = "$volumePrefix$suffix"
        $volumeLabelsText = (& $docker volume inspect --format '{{json .Labels}}' $volume 2>$null) -join ""
        if ($LASTEXITCODE -eq 0) {
          $volumeLabels = $volumeLabelsText | ConvertFrom-Json
          $volumeProject = $volumeLabels.'com.docker.compose.project'
          if ($volumeProject -eq $project -and $volume -match "^$([regex]::Escape($volumePrefix))_(postgres_data|media_data|runtime_control)$") {
            & $docker volume rm $volume *> $null
          }
        }
      }
    } finally { $ErrorActionPreference = $restorePreference }
    if (-not $EvidencePath) {
      Remove-Item -LiteralPath $tempRoot -Recurse -Force
    } else {
      $resolvedEvidence = Resolve-VayujitEvidencePath -Path $EvidencePath
      [System.IO.File]::WriteAllText($resolvedEvidence, (($report | ConvertTo-Json -Depth 8) + "`n"), [System.Text.UTF8Encoding]::new($false))
      Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
  } else {
    Write-Warning "Disposable marker mismatch; temporary data/resources were retained for manual review: $tempRoot / $project"
  }
}
if ($report.status -ne "PASS") { throw "PC disposable certification did not pass. Inspect evidence and diagnostics." }
Write-Output ($report | ConvertTo-Json -Depth 8)
