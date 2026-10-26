param(
  [string]$DataRoot = (Join-Path $env:LOCALAPPDATA "VAYUJIT OS"),
  [switch]$DisposableCertification,
  [string]$BackupDestination,
  [string]$BackupReportPath
)
$ErrorActionPreference = "Stop"
try {
  $bootstrapScript = Join-Path $PSScriptRoot "pc-first-backup-bootstrap.ps1"
  . $bootstrapScript
} catch {
  if ($DisposableCertification) {
    [Console]::Out.WriteLine("VAYUJIT_BACKUP_CHILD_BOUNDARY=backup_initialization_failed")
    throw "backup_initialization_failed"
  }
  throw
}
$script:backupBootstrapBoundary = Initialize-VayujitBackupReportBoundary `
  -DisposableCertification ([bool]$DisposableCertification) `
  -DataRoot $DataRoot `
  -BackupReportPath $BackupReportPath `
  -RepositoryRoot (Join-Path $PSScriptRoot "..")
$script:backupBootstrapFailureCode = "backup_initialization_failed"
$script:backupBootstrapFailureOperation = "backup child initialization"
$script:backupReportWriteFailed = $false
try {
Import-Module (Join-Path $PSScriptRoot "pc-first-key-security.psm1") -Force
Import-Module (Join-Path $PSScriptRoot "pc-first-backup-artifacts.psm1") -Force
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dataFull = [System.IO.Path]::GetFullPath($DataRoot)
$backupReportFullPath = if ($script:backupBootstrapBoundary.IsValid) { $script:backupBootstrapBoundary.ReportPath } else { $null }
function Test-PathWithin([string]$Path, [string]$BasePath) {
  $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  $base = [System.IO.Path]::GetFullPath($BasePath).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  return $fullPath.Equals($base, [System.StringComparison]::OrdinalIgnoreCase) -or
    $fullPath.StartsWith($base + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}
$configRoot = Join-Path $dataFull "config"
$markerPath = if ($DisposableCertification) { Join-Path $dataFull "disposable-profile.marker" } else { Join-Path $configRoot "pc-install.json" }
$composeEnvPath = Join-Path $configRoot "compose.env"
$script:backupBootstrapFailureCode = "backup_preflight_failed"
$script:backupBootstrapFailureOperation = "backup preflight"
foreach ($required in @($markerPath, $composeEnvPath)) {
  if (-not (Test-Path -LiteralPath $required)) { throw "The PC profile has not been initialized." }
}
$composeFile = Join-Path $repo "infrastructure\docker-compose.pc.yml"
$volumePrefix = $null
$project = $null
$dbName = "vayujit_business"
$recipient = $null
$retentionDays = 90
$identityPath = Join-Path $configRoot $(if ($DisposableCertification) { "disposable-backup.agekey" } else { "backup.agekey" })
$stageRoot = Join-Path $dataFull "backup-stage"
$backupRoot = $null

if ($DisposableCertification) {
  $script:backupBootstrapFailureCode = "backup_arguments_invalid"
  $script:backupBootstrapFailureOperation = "backup child argument validation"
  if (-not $script:backupBootstrapBoundary.IsValid) {
    throw "Disposable backup report boundary or marker is invalid."
  }
  if (-not $BackupDestination -or -not $BackupReportPath) {
    throw "Disposable certification requires explicit BackupDestination and BackupReportPath paths."
  }
  $backupReportFullPath = [System.IO.Path]::GetFullPath($BackupReportPath)
  if (-not (Test-PathWithin $backupReportFullPath $dataFull)) {
    throw "Disposable backup report must remain under the marked temporary profile."
  }
  if (Test-Path -LiteralPath $backupReportFullPath) {
    throw "Disposable backup report path already exists; refusing to overwrite it."
  }
  $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
  if (-not (Test-PathWithin $dataFull $tempRoot) -or (Test-PathWithin $dataFull $repo)) {
    throw "Disposable backup mode only accepts a marker-protected data root under the system temporary directory."
  }
  $markerText = Get-Content -LiteralPath $markerPath -Raw
  if (-not $markerText.StartsWith("vayujit-pc-disposable-certification-v1`n", [System.StringComparison]::Ordinal)) {
    throw "Disposable profile marker is missing or invalid."
  }
  $projectMatch = [regex]::Match($markerText, "(?m)^project=(vayujit-pc-cert-([a-f0-9]{10}))\s*$")
  $volumeMatch = [regex]::Match($markerText, "(?m)^volume_prefix=(vayujit_pc_cert_([a-f0-9]{10}))\s*$")
  if (-not $projectMatch.Success -or -not $volumeMatch.Success -or $projectMatch.Groups[2].Value -ne $volumeMatch.Groups[2].Value) {
    throw "Disposable project and volume names do not match the randomized certification marker."
  }
  $project = $projectMatch.Groups[1].Value
  $volumePrefix = $volumeMatch.Groups[1].Value
  $destinationBase = [System.IO.Path]::GetFullPath($BackupDestination)
  if ((Test-PathWithin $destinationBase $repo) -or
      (Test-PathWithin $destinationBase $dataFull) -or
      (Test-PathWithin $dataFull $destinationBase)) {
    throw "Disposable backup destination must be outside the repository and separate from its profile/staging directory."
  }
  $backupRoot = Join-Path $destinationBase ("vayujit-disposable-cert-" + $projectMatch.Groups[2].Value)
  if (Test-Path -LiteralPath $backupRoot) {
    throw "Disposable backup evidence directory already exists; refusing to reuse or overwrite it."
  }
  $backupDriveRoot = [System.IO.Path]::GetPathRoot($backupRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  if ($backupRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar).Equals($backupDriveRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Disposable backup destination must be a dedicated folder, not a drive root."
  }
} else {
  $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
  if ($marker.marker -ne "vayujit-pc-first-live-v1" -or $marker.activation -ne "owner_activated") {
    throw "Encrypted backup requires the activated, marker-protected PC business profile."
  }
  if ($BackupDestination) {
    throw "The permanent backup destination is fixed in its protected installation marker; reinitialize only through the reviewed recovery procedure."
  }
  $backupRoot = [System.IO.Path]::GetFullPath([string]$marker.backup_root)
  if ((Test-PathWithin $backupRoot $repo) -or
      (Test-PathWithin $backupRoot $dataFull) -or
      (Test-PathWithin $dataFull $backupRoot)) {
    throw "Permanent backup destination must be outside the repository and the PC profile/staging directory."
  }
  $project = "vayujit-pc-business"
  $volumePrefix = "vayujit_pc_business"
}

$script:backupBootstrapFailureCode = "backup_preflight_failed"
$script:backupBootstrapFailureOperation = "backup preflight"
foreach ($line in Get-Content -LiteralPath $composeEnvPath) {
  if ($line -match '^VAYUJIT_PC_PROJECT_NAME=(.+)$') { $configuredProject = $Matches[1] }
  if ($line -match '^VAYUJIT_PC_VOLUME_PREFIX=(.+)$') { $configuredVolumePrefix = $Matches[1] }
  if ($line -match '^VAYUJIT_PC_AGE_RECIPIENT=(.+)$') { $recipient = $Matches[1] }
  if ($line -match '^VAYUJIT_PC_BACKUP_RETENTION_DAYS=(\d+)$') { $retentionDays = [int]$Matches[1] }
  if ($line -match '^VAYUJIT_DATABASE_NAME=(.+)$') { $dbName = $Matches[1] }
}
if ($configuredProject -ne $project -or $configuredVolumePrefix -ne $volumePrefix -or $dbName -ne "vayujit_business") {
  throw "Compose profile does not match the marker-protected backup target."
}
if (-not $recipient -or $recipient -notmatch '^age1[0-9a-z]+$') {
  throw "PC backup recipient is invalid or missing."
}
if (-not (Test-Path -LiteralPath $identityPath)) { throw "The age decryption identity is missing; no backup was attempted." }
Assert-VayujitPrivateAcl -Path $identityPath -Kind File | Out-Null
if (-not (Get-Command age -ErrorAction SilentlyContinue)) { throw "The age encryption tool is not installed." }
if ($DisposableCertification -and -not (Get-Command age-keygen -ErrorAction SilentlyContinue)) { throw "age-keygen is required for disposable wrong-key rejection testing." }
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker -and $env:PC_CERT_DOCKER_PATH -and (Test-Path -LiteralPath $env:PC_CERT_DOCKER_PATH)) {
  $docker = [pscustomobject]@{ Source = $env:PC_CERT_DOCKER_PATH }
}
if (-not $docker) { throw "Docker Desktop is unavailable; backup did not run." }
New-Item -ItemType Directory -Path $backupRoot, $stageRoot -Force | Out-Null
$writeProbe = Join-Path $backupRoot (".vayujit-backup-write-probe-" + [guid]::NewGuid().ToString("N"))
try {
  [System.IO.File]::WriteAllText($writeProbe, "probe")
} catch { throw "Backup destination is not writable." }
finally { if (Test-Path -LiteralPath $writeProbe) { Remove-Item -LiteralPath $writeProbe -Force } }

function Get-HostPhysicalDiskNumber([string]$Path) {
  $fullPath = [System.IO.Path]::GetFullPath($Path)
  $cursor = $fullPath
  while ($cursor) {
    if (Test-Path -LiteralPath $cursor) {
      $item = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
      if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { return $null }
    }
    $parent = [System.IO.Directory]::GetParent($cursor)
    if (-not $parent -or $parent.FullName -eq $cursor) { break }
    $cursor = $parent.FullName
  }
  $root = [System.IO.Path]::GetPathRoot($Path)
  if ($root -notmatch '^([A-Za-z]):\\$') { return $null }
  $driveLetter = $Matches[1].ToUpperInvariant()
  return (Get-Partition -DriveLetter $driveLetter -ErrorAction Stop | Select-Object -First 1).DiskNumber
}

function Get-DockerVolumeStorageEvidence([string]$VolumeName) {
  try {
    $volumeInfo = (& $docker.Source volume inspect --format '{{.Driver}}|{{.Mountpoint}}' $VolumeName 2>$null) -join ''
    if ($LASTEXITCODE -ne 0 -or -not $volumeInfo) { throw 'Docker volume could not be inspected.' }
    $parts = [regex]::Split($volumeInfo, '\|', 2)
    if ($parts.Count -ne 2 -or $parts[0] -ne 'local') { throw 'Only a local Docker data volume can be assessed.' }
    $mountpoint = $parts[1]
    if ($mountpoint -match '^[A-Za-z]:\\') {
      $diskNumber = Get-HostPhysicalDiskNumber $mountpoint
      if ($null -ne $diskNumber) {
        return [pscustomobject]@{ status = 'VERIFIED'; disk_number = [int]$diskNumber; mountpoint = $mountpoint; evidence = 'Docker local volume mountpoint mapped to a Windows physical disk.' }
      }
    }

    $operatingSystem = (& $docker.Source info --format '{{.OperatingSystem}}' 2>$null) -join ''
    if ($LASTEXITCODE -ne 0 -or $operatingSystem -notmatch 'Docker Desktop') { throw 'Docker data mountpoint is not host-addressable and the engine is not a recognized Docker Desktop WSL engine.' }

    $configuredImageLocation = $null
    $settingsPath = if ($env:APPDATA) { Join-Path $env:APPDATA 'Docker\settings-store.json' } else { $null }
    if ($settingsPath -and (Test-Path -LiteralPath $settingsPath)) {
      $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
      $locationProperty = $settings.PSObject.Properties['diskImageLocation']
      if ($locationProperty -and $locationProperty.Value) {
        $configuredImageLocation = [Environment]::ExpandEnvironmentVariables([string]$locationProperty.Value)
      }
    }
    $searchDirectories = [System.Collections.Generic.List[string]]::new()
    if ($configuredImageLocation) {
      if ([System.IO.Path]::GetExtension($configuredImageLocation) -ieq '.vhdx') {
        if (Test-Path -LiteralPath $configuredImageLocation -PathType Leaf) {
          $image = Get-Item -LiteralPath $configuredImageLocation
          $imageDisk = Get-HostPhysicalDiskNumber $image.FullName
          if ($null -ne $imageDisk) {
            return [pscustomobject]@{ status = 'VERIFIED'; disk_number = [int]$imageDisk; mountpoint = $mountpoint; evidence = "Docker Desktop configured disk image: $($image.FullName)" }
          }
        }
      } elseif (Test-Path -LiteralPath $configuredImageLocation -PathType Container) {
        $searchDirectories.Add($configuredImageLocation)
        foreach ($child in @('disk', 'data')) {
          $nested = Join-Path $configuredImageLocation $child
          if (Test-Path -LiteralPath $nested -PathType Container) { $searchDirectories.Add($nested) }
        }
      }
    } else {
      if ($env:LOCALAPPDATA) {
        foreach ($relative in @('Docker\wsl\disk', 'Docker\wsl\data')) {
          $candidate = Join-Path $env:LOCALAPPDATA $relative
          if (Test-Path -LiteralPath $candidate -PathType Container) { $searchDirectories.Add($candidate) }
        }
      }
    }
    $images = @(
      foreach ($directory in $searchDirectories | Select-Object -Unique) {
        Get-ChildItem -LiteralPath $directory -Filter '*.vhdx' -File -ErrorAction SilentlyContinue
      }
    ) | Sort-Object -Property FullName -Unique
    if ($images.Count -ne 1) { throw 'Docker Desktop backing virtual disk could not be identified unambiguously from its configured storage location.' }
    $imageDiskNumber = Get-HostPhysicalDiskNumber $images[0].FullName
    if ($null -eq $imageDiskNumber) { throw 'Docker Desktop virtual disk path cannot be mapped to a physical disk.' }
    return [pscustomobject]@{ status = 'VERIFIED'; disk_number = [int]$imageDiskNumber; mountpoint = $mountpoint; evidence = "Docker Desktop backing image: $($images[0].FullName)" }
  } catch {
    return [pscustomobject]@{ status = 'UNVERIFIED'; disk_number = $null; mountpoint = $null; evidence = $_.Exception.Message }
  }
}

$postgresVolume = "${volumePrefix}_postgres_data"
$mediaVolume = "${volumePrefix}_media_data"
$postgresStorage = Get-DockerVolumeStorageEvidence $postgresVolume
$mediaStorage = Get-DockerVolumeStorageEvidence $mediaVolume
$independence = 'UNVERIFIED'
try {
  $backupDisk = Get-HostPhysicalDiskNumber $backupRoot
  if ($postgresStorage.status -eq 'VERIFIED' -and $mediaStorage.status -eq 'VERIFIED' -and
      $postgresStorage.disk_number -eq $mediaStorage.disk_number -and $null -ne $backupDisk) {
    $independence = if ($postgresStorage.disk_number -eq $backupDisk) { 'SAME_PHYSICAL_DISK' } else { 'VERIFIED_DIFFERENT_PHYSICAL_DISK' }
  }
} catch { $independence = 'UNVERIFIED' }
if ($postgresStorage.mountpoint -match '^[A-Za-z]:\\' -and (Test-PathWithin $backupRoot $postgresStorage.mountpoint)) {
  throw 'Backup destination cannot be inside the PostgreSQL data volume.'
}
if ($mediaStorage.mountpoint -match '^[A-Za-z]:\\' -and (Test-PathWithin $backupRoot $mediaStorage.mountpoint)) {
  throw 'Backup destination cannot be inside the media data volume.'
}
if ($backupRoot -match '^\\\\wsl(\$|\.localhost)\\docker-desktop') {
  throw 'Backup destination cannot be within Docker Desktop WSL data.'
}
if (-not $DisposableCertification -and $independence -ne "VERIFIED_DIFFERENT_PHYSICAL_DISK") {
  throw "Permanent backup destination independence is $independence; a verified different physical disk is required."
}
$backupId = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ") + "-" + [guid]::NewGuid().ToString("N").Substring(0, 12)
$workRoot = Join-Path $stageRoot $backupId
$containerRoot = "/tmp/vayujit-pc-$backupId"
$containerDump = "$containerRoot/database.dump"
$containerMedia = $containerRoot
$composeArgs = @("compose", "--project-name", $project, "-f", $composeFile, "--env-file", $composeEnvPath)
$statusPath = Join-Path $backupRoot "last-backup-status.json"
$maintenanceOwned = $false
$workerStopped = $false
$apiStopped = $false
$backupTimer = [System.Diagnostics.Stopwatch]::new()
$restoreSeconds = $null
$canonicalSnapshot = $null
$canonicalSourceUnchanged = $null
$encryptedHeaderVerified = $false
$wrongKeyRejected = $false
$corruptedCiphertextRejected = $false
$financePrecisionVerified = $false
$mediaRestoreVerified = $false
$restoreChecks = @()
$cleanupFailure = $null
$backupCompleted = $false
$dockerFailureOperation = $null
$dockerFailureExitCode = $null
$backupFailureMessage = $null
$backupCurrentOperation = "backup preflight"
$backupCurrentFailureCode = "backup_preflight_failed"
$backupNativeExitCode = $null

function Get-CanonicalSnapshot([string]$ContainerId, [string]$ExpectedPath) {
  $expected = Get-Content -LiteralPath $ExpectedPath -Raw | ConvertFrom-Json
  foreach ($field in @("owner_id", "product_id", "inventory_item_id", "financial_cost_id", "media_id")) {
    if ([string]$expected.$field -notmatch '^[0-9a-fA-F-]{36}$') { throw "Disposable evidence has an invalid $field identifier." }
  }
  $ownerId = [string]$expected.owner_id
  $productId = [string]$expected.product_id
  $inventoryId = [string]$expected.inventory_item_id
  $costId = [string]$expected.financial_cost_id
  $mediaId = [string]$expected.media_id
  $sql = @"
SELECT jsonb_build_object(
  'owner_count', (SELECT count(*) FROM users),
  'owner_id', (SELECT id::text FROM users WHERE id='$ownerId'),
  'product', (SELECT jsonb_build_object('id',id::text,'name',name,'sku',sku,'price',price_amount::text,'price_currency',price_currency,'cost',cost_amount::text,'inventory_quantity',inventory_quantity) FROM products WHERE id='$productId'),
  'financial_cost', (SELECT jsonb_build_object('id',id::text,'amount',amount::text,'currency',currency,'cost_type',cost_type,'evidence_status',evidence_status) FROM financial_cost_evidence WHERE id='$costId'),
  'inventory_item', (SELECT jsonb_build_object('id',id::text,'product_id',product_id::text,'sku',internal_sku,'location',location_code,'on_hand',on_hand_quantity,'reserved',reserved_quantity,'damaged',damaged_quantity,'version',version) FROM inventory_items WHERE id='$inventoryId'),
  'inventory_movements', (SELECT count(*) FROM inventory_movements WHERE inventory_item_id='$inventoryId'),
  'media_asset', (SELECT jsonb_build_object('id',id::text,'checksum',checksum_sha256,'size_bytes',size_bytes,'mime_type',mime_type,'status',status) FROM media_assets WHERE id='$mediaId'),
  'catalog_image', (SELECT jsonb_build_object('media_id',media_id::text,'alt_text',alt_text,'position',position,'is_primary',is_primary) FROM catalog_product_images WHERE product_id='$productId' AND media_id='$mediaId'),
  'audit_events', (SELECT count(*) FROM audit_events WHERE actor_id='$ownerId' AND entity_id IN ('$productId','$inventoryId','$costId','$mediaId'))
)::text;
"@
  $snapshot = Invoke-DockerExecCapturedOutput -ContainerId $ContainerId -CommandArguments @("psql", "-U", "postgres", "-d", $dbName, "-Atc", $sql) -Operation "canonical disposable source snapshot query"
  if (-not $snapshot) { throw "Canonical disposable source snapshot query returned no data." }
  $snapshotObject = $snapshot | ConvertFrom-Json
  if ($snapshotObject.owner_count -ne 1 -or $snapshotObject.owner_id -ne $ownerId -or
      -not $snapshotObject.product -or -not $snapshotObject.financial_cost -or
      -not $snapshotObject.inventory_item -or -not $snapshotObject.media_asset -or
      -not $snapshotObject.catalog_image -or $snapshotObject.inventory_movements -lt 1 -or
      $snapshotObject.audit_events -lt 1) {
    throw "Canonical backup fixture is incomplete; owner, product, inventory, financial, media, or audit evidence is missing."
  }
  return $snapshot
}
function Add-CleanupFailure([string]$Message) {
  if ($script:cleanupFailure) { $script:cleanupFailure += "; $Message" }
  else { $script:cleanupFailure = $Message }
}
function Set-BackupStage([string]$Operation, [string]$FailureCode) {
  $script:backupCurrentOperation = $Operation
  $script:backupCurrentFailureCode = $FailureCode
  $script:backupNativeExitCode = $null
  $script:dockerFailureOperation = $null
  $script:dockerFailureExitCode = $null
}
function Complete-BackupStage {
  $script:backupCurrentOperation = $null
  $script:backupCurrentFailureCode = $null
  $script:backupNativeExitCode = $null
}
function Assert-BackupNativeExit([string]$FailureCode) {
  if ($LASTEXITCODE -ne 0) {
    $script:backupNativeExitCode = [int]$LASTEXITCODE
    $script:dockerFailureOperation = if ($script:backupCurrentOperation) { $script:backupCurrentOperation } else { "Docker command" }
    $script:dockerFailureExitCode = [int]$LASTEXITCODE
    throw $FailureCode
  }
}
function Invoke-BackupAgeStage {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [string[]]$Arguments = @(),
    [Parameter(Mandatory = $true)][string]$Operation,
    [Parameter(Mandatory = $true)][string]$FailureCode
  )
  Set-BackupStage -Operation $Operation -FailureCode $FailureCode
  $result = Invoke-VayujitBackupStage -Operation $Operation -FailureCode $FailureCode -Action {
    Invoke-VayujitNativeCapture -FilePath $FilePath -Arguments $Arguments
  }
  Complete-BackupStage
  return [pscustomobject]@{ ExitCode = $result.ExitCode }
}
function Invoke-DockerExecCapturedOutput {
  param(
    [Parameter(Mandatory = $true)][string]$ContainerId,
    [Parameter(Mandatory = $true)][string[]]$CommandArguments,
    [Parameter(Mandatory = $true)][string]$Operation
  )
  if ($CommandArguments -contains "-T" -or $CommandArguments -contains "--no-TTY") {
    throw "Direct docker exec does not support Compose no-TTY flags."
  }
  $script:dockerFailureOperation = $Operation
  $script:dockerFailureExitCode = $null
  $previousErrorActionPreference = $ErrorActionPreference
  try {
    # Direct `docker exec` has no TTY unless requested and does not attach
    # stdin unless `-i` is requested. Capture stdout, discard stderr safely,
    # and preserve the process exit code; PowerShell 5/7 may otherwise turn
    # native stderr into a terminating NativeCommandError under Stop policy.
    $ErrorActionPreference = "Continue"
    $output = & $docker.Source exec $ContainerId @CommandArguments 2>$null
    $exitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
  if ($exitCode -ne 0) {
    $script:dockerFailureExitCode = [int]$exitCode
    throw "$Operation failed with Docker exit code $exitCode."
  }
  $script:dockerFailureOperation = $null
  return ($output -join "")
}
} catch {
  if ($DisposableCertification) {
    Stop-VayujitDisposableBackupBootstrap `
      -Boundary $script:backupBootstrapBoundary `
      -FailureCode $script:backupBootstrapFailureCode `
      -FailureOperation $script:backupBootstrapFailureOperation
  }
  throw
}
try {
  New-Item -ItemType Directory -Path $workRoot -Force | Out-Null
  Set-BackupStage -Operation "maintenance status check" -FailureCode "maintenance_status_failed"
  $maintenanceStatus = & $docker.Source @composeArgs exec -T api python -m vayujit_api.maintenance_cli maintenance-status 2>$null | ConvertFrom-Json
  Assert-BackupNativeExit -FailureCode "maintenance_status_failed"
  if ($LASTEXITCODE -ne 0 -or $maintenanceStatus.maintenance) { throw "maintenance_already_enabled_or_unavailable" }
  Set-BackupStage -Operation "worker state check" -FailureCode "worker_state_check_failed"
  $workerContainer = (& $docker.Source @composeArgs ps -q worker 2>$null) -join ""
  Assert-BackupNativeExit -FailureCode "worker_container_unavailable"
  if ($LASTEXITCODE -ne 0 -or -not $workerContainer) { throw "worker_container_unavailable" }
  $workerRunning = (& $docker.Source inspect --format '{{.State.Running}}' $workerContainer 2>$null) -join ""
  Assert-BackupNativeExit -FailureCode "worker_state_check_failed"
  if ($LASTEXITCODE -ne 0 -or $workerRunning -ne "true") { throw "worker_not_running_before_backup" }
  Set-BackupStage -Operation "maintenance enable" -FailureCode "maintenance_enable_failed"
  $maintenanceOn = & $docker.Source @composeArgs exec -T api python -m vayujit_api.maintenance_cli maintenance-on --confirm 2>$null | ConvertFrom-Json
  Assert-BackupNativeExit -FailureCode "maintenance_enable_failed"
  if ($LASTEXITCODE -ne 0 -or -not $maintenanceOn.maintenance) { throw "maintenance_enable_failed" }
  $maintenanceOwned = $true
  $workerStopped = $true
  Set-BackupStage -Operation "worker pause" -FailureCode "worker_pause_failed"
  & $docker.Source @composeArgs stop --timeout 45 worker 2>$null | Out-Null
  Assert-BackupNativeExit -FailureCode "worker_pause_failed"
  if ($LASTEXITCODE -ne 0) { throw "worker_pause_failed" }
  $apiStopped = $true
  Set-BackupStage -Operation "API pause" -FailureCode "api_pause_failed"
  & $docker.Source @composeArgs stop --timeout 30 api 2>$null | Out-Null
  Assert-BackupNativeExit -FailureCode "api_pause_failed"
  if ($LASTEXITCODE -ne 0) { throw "api_pause_failed" }

  Set-BackupStage -Operation "PostgreSQL container lookup" -FailureCode "postgres_container_unavailable"
  $postgresContainer = (& $docker.Source @composeArgs ps -q postgres 2>$null) -join ""
  Assert-BackupNativeExit -FailureCode "postgres_container_unavailable"
  if ($LASTEXITCODE -ne 0 -or -not $postgresContainer) { throw "postgres_container_unavailable" }
  $evidenceFile = Join-Path $dataFull "api-evidence.json"
  if ($DisposableCertification) {
    Set-BackupStage -Operation "canonical source snapshot" -FailureCode "canonical_source_snapshot_failed"
    $canonicalSnapshot = Get-CanonicalSnapshot $postgresContainer $evidenceFile
    Complete-BackupStage
    [System.IO.File]::WriteAllText((Join-Path $workRoot "expected-canonical-snapshot.json"), $canonicalSnapshot, [System.Text.UTF8Encoding]::new($false))
  }
  $backupTimer.Start()

  Set-BackupStage -Operation "PostgreSQL dump creation" -FailureCode "database_dump_failed"
  & $docker.Source @composeArgs exec -T postgres sh -lc "mkdir -p '$containerRoot' && pg_dump -Fc --no-owner --no-privileges -U postgres -d '$dbName' -f '$containerDump'" 2>$null
  Assert-BackupNativeExit -FailureCode "database_dump_failed"
  if ($LASTEXITCODE -ne 0) { throw "database_dump_failed" }
  $databaseDumpPath = Join-Path $workRoot "database.dump"
  Set-BackupStage -Operation "PostgreSQL dump copy" -FailureCode "database_dump_copy_failed"
  & $docker.Source @composeArgs cp "postgres:$containerDump" $databaseDumpPath 2>$null
  Assert-BackupNativeExit -FailureCode "database_dump_copy_failed"
  if ($LASTEXITCODE -ne 0) { throw "database_dump_copy_failed" }
  Set-BackupStage -Operation "PostgreSQL dump artifact validation" -FailureCode "database_dump_artifact_validation_failed"
  Assert-VayujitBackupArtifact -Path $databaseDumpPath -MissingFailureCode "database_dump_artifact_missing" -EmptyFailureCode "database_dump_artifact_empty" | Out-Null
  Complete-BackupStage

  $stageMount = "$($workRoot.Replace('\', '/')):$containerMedia"
  Set-BackupStage -Operation "media backup creation" -FailureCode "media_backup_failed"
  & $docker.Source @composeArgs run --rm --no-deps --volume $stageMount --entrypoint python api -m vayujit_api.operations.pc_media_backup_cli create --output-directory $containerMedia --backup-id $backupId 2>$null
  Assert-BackupNativeExit -FailureCode "media_backup_failed"
  if ($LASTEXITCODE -ne 0) { throw "media_backup_failed" }
  # The CLI intentionally renames its temporary timestamped outputs to these
  # stable names. Validate that exact contract; `{"files":N}` from the CLI is
  # the number of archived source files, not an artifact count.
  Set-BackupStage -Operation "media artifact resolution" -FailureCode "media_backup_artifacts_missing"
  $mediaArtifacts = Get-VayujitMediaBackupArtifacts -OutputDirectory $workRoot
  Complete-BackupStage

  # Verify the plaintext media archive against its manifest before encryption.
  # The post-decryption verification below remains necessary to validate the
  # ciphertext round trip independently.
  Set-BackupStage -Operation "pre-encryption media verification" -FailureCode "media_backup_validation_failed"
  $mediaSourceVerificationOutput = & $docker.Source @composeArgs run --rm --no-deps --volume $stageMount --entrypoint python api -m vayujit_api.operations.pc_media_backup_cli verify --archive "$containerMedia/media.zip" --manifest "$containerMedia/media.json" 2>$null
  Assert-BackupNativeExit -FailureCode "media_backup_validation_failed"
  if ($LASTEXITCODE -ne 0) { throw "media_backup_validation_failed" }
  $mediaSourceVerification = Invoke-VayujitBackupStage -Operation "pre-encryption media verification output parsing" -FailureCode "media_backup_validation_output_invalid" -Action {
    ($mediaSourceVerificationOutput -join "") | ConvertFrom-Json
  }
  if ($DisposableCertification -and $mediaSourceVerification.verified_files -lt 1) { throw "disposable_media_backup_has_no_verified_files" }
  Complete-BackupStage

  # Inspect the custom-format dump while its source container is still running;
  # a successful copy alone does not prove that pg_restore can read it.
  Set-BackupStage -Operation "PostgreSQL dump inspection" -FailureCode "database_dump_validation_failed"
  & $docker.Source @composeArgs exec -T postgres pg_restore --list $containerDump 2>$null | Out-Null
  Assert-BackupNativeExit -FailureCode "database_dump_validation_failed"
  if ($LASTEXITCODE -ne 0) { throw "database_dump_validation_failed" }
  Complete-BackupStage

  $databaseEncrypted = Join-Path $backupRoot "pc-backup-$backupId.database.dump.age"
  $mediaEncrypted = Join-Path $backupRoot "pc-backup-$backupId.media.zip.age"
  $manifestEncrypted = Join-Path $backupRoot "pc-backup-$backupId.media.json.age"
  Set-BackupStage -Operation "age executable resolution" -FailureCode "age_tool_unavailable"
  $agePath = (Get-Command age -ErrorAction Stop).Source
  Complete-BackupStage
  $null = Invoke-BackupAgeStage -FilePath $agePath -Arguments @("--encrypt", "--recipient", $recipient, "--output", $databaseEncrypted, $databaseDumpPath) -Operation "database encryption" -FailureCode "database_encryption_failed"
  $null = Invoke-BackupAgeStage -FilePath $agePath -Arguments @("--encrypt", "--recipient", $recipient, "--output", $mediaEncrypted, $mediaArtifacts.ArchivePath) -Operation "media encryption" -FailureCode "media_encryption_failed"
  $null = Invoke-BackupAgeStage -FilePath $agePath -Arguments @("--encrypt", "--recipient", $recipient, "--output", $manifestEncrypted, $mediaArtifacts.ManifestPath) -Operation "media manifest encryption" -FailureCode "media_manifest_encryption_failed"
  $backupTimer.Stop()
  Set-BackupStage -Operation "encrypted artifact header validation" -FailureCode "encrypted_artifact_header_invalid"
  $header = [System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($databaseEncrypted), 0, [Math]::Min(22, (Get-Item -LiteralPath $databaseEncrypted).Length))
  $encryptedHeaderVerified = $header.StartsWith("age-encryption.org/v1", [System.StringComparison]::Ordinal)
  if (-not $encryptedHeaderVerified) { throw "database_ciphertext_header_invalid" }
  Complete-BackupStage

  $verifyDatabase = Join-Path $workRoot "verify.dump"
  $verifyMedia = Join-Path $workRoot "verify-media.zip"
  $verifyManifest = Join-Path $workRoot "verify-media.json"
  $null = Invoke-BackupAgeStage -FilePath $agePath -Arguments @("--decrypt", "--identity", $identityPath, "--output", $verifyDatabase, $databaseEncrypted) -Operation "database decryption verification" -FailureCode "database_decryption_verification_failed"
  $null = Invoke-BackupAgeStage -FilePath $agePath -Arguments @("--decrypt", "--identity", $identityPath, "--output", $verifyMedia, $mediaEncrypted) -Operation "media decryption verification" -FailureCode "media_decryption_verification_failed"
  $null = Invoke-BackupAgeStage -FilePath $agePath -Arguments @("--decrypt", "--identity", $identityPath, "--output", $verifyManifest, $manifestEncrypted) -Operation "media manifest decryption verification" -FailureCode "media_manifest_decryption_verification_failed"
  Set-BackupStage -Operation "decrypted artifact validation" -FailureCode "decrypted_artifact_validation_failed"
  Assert-VayujitBackupArtifact -Path $verifyDatabase -MissingFailureCode "database_decryption_verification_missing" -EmptyFailureCode "database_decryption_verification_empty" | Out-Null
  Assert-VayujitBackupArtifact -Path $verifyMedia -MissingFailureCode "media_decryption_verification_missing" -EmptyFailureCode "media_decryption_verification_empty" | Out-Null
  Assert-VayujitBackupArtifact -Path $verifyManifest -MissingFailureCode "media_manifest_decryption_verification_missing" -EmptyFailureCode "media_manifest_decryption_verification_empty" | Out-Null
  Complete-BackupStage

  if ($DisposableCertification) {
    Set-BackupStage -Operation "wrong-key rejection verification" -FailureCode "wrong_key_test_failed"
    $wrongIdentity = Join-Path $configRoot "wrong-test-identity.agekey"
    $ageKeygenPath = (Get-Command age-keygen -ErrorAction Stop).Source
    $null = New-VayujitPrivateAgeIdentity -AgeKeygenPath $ageKeygenPath -IdentityPath $wrongIdentity
    $wrongOutput = Join-Path $workRoot "wrong-key-output.dump"
    $wrongKeyRejected = Test-VayujitNativeFailure -FilePath $agePath -Arguments @("--decrypt", "--identity", $wrongIdentity, "--output", $wrongOutput, $databaseEncrypted)
    Remove-Item -LiteralPath $wrongIdentity -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $wrongOutput) { Remove-Item -LiteralPath $wrongOutput -Force }
    if (-not $wrongKeyRejected) { throw "wrong_key_was_accepted" }
    Complete-BackupStage

    Set-BackupStage -Operation "corrupted ciphertext rejection verification" -FailureCode "corrupted_ciphertext_test_failed"
    $corruptedCiphertext = Join-Path $workRoot "corrupted-database.dump.age"
    Copy-Item -LiteralPath $databaseEncrypted -Destination $corruptedCiphertext
    $cipherStream = [System.IO.File]::Open($corruptedCiphertext, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    try {
      if ($cipherStream.Length -lt 64) { throw "encrypted_database_artifact_too_small" }
      $cipherStream.Position = $cipherStream.Length - 1
      $lastByte = $cipherStream.ReadByte()
      $cipherStream.Position = $cipherStream.Length - 1
      $cipherStream.WriteByte([byte]($lastByte -bxor 1))
    } finally { $cipherStream.Dispose() }
    $corruptOutput = Join-Path $workRoot "corrupted-output.dump"
    $corruptedCiphertextRejected = Test-VayujitNativeFailure -FilePath $agePath -Arguments @("--decrypt", "--identity", $identityPath, "--output", $corruptOutput, $corruptedCiphertext)
    if (Test-Path -LiteralPath $corruptOutput) { Remove-Item -LiteralPath $corruptOutput -Force }
    if (-not $corruptedCiphertextRejected) { throw "corrupted_ciphertext_was_accepted" }
    Complete-BackupStage
  }

  $restoreReportPath = Join-Path $workRoot "restore-validation.json"
  $restoreTimer = [System.Diagnostics.Stopwatch]::StartNew()
  Set-BackupStage -Operation "independent PostgreSQL restore" -FailureCode "independent_database_restore_failed"
  if ($DisposableCertification) {
    & (Join-Path $PSScriptRoot "verify-pc-restore.ps1") -DatabaseDump $verifyDatabase -BackupId $backupId -ExpectedEvidencePath $evidenceFile -ExpectedSnapshotPath (Join-Path $workRoot "expected-canonical-snapshot.json") -ReportPath $restoreReportPath
  } else {
    & (Join-Path $PSScriptRoot "verify-pc-restore.ps1") -DatabaseDump $verifyDatabase -BackupId $backupId
  }
  Assert-BackupNativeExit -FailureCode "independent_database_restore_failed"
  if ($LASTEXITCODE -ne 0) { throw "independent_database_restore_failed" }
  $restoreTimer.Stop()
  $restoreSeconds = [Math]::Round($restoreTimer.Elapsed.TotalSeconds, 3)
  if ($DisposableCertification) {
    $restoreReport = Invoke-VayujitBackupStage -Operation "independent restore report parsing" -FailureCode "restore_report_invalid" -Action {
      Get-Content -LiteralPath $restoreReportPath -Raw | ConvertFrom-Json
    }
    $restoreChecks = @($restoreReport.checks)
    $financePrecisionVerified = [bool]$restoreReport.financial_precision_verified
    if ($restoreReport.status -ne "PASS" -or -not $financePrecisionVerified) { throw "restored_canonical_records_or_financial_precision_mismatch" }
  }
  Complete-BackupStage
  Copy-Item -LiteralPath $verifyMedia -Destination (Join-Path $workRoot "verify-media.zip")
  Copy-Item -LiteralPath $verifyManifest -Destination (Join-Path $workRoot "verify-media.json")
  $verifyMount = "$($workRoot.Replace('\', '/')):$containerMedia"
  Set-BackupStage -Operation "post-decryption media restore verification" -FailureCode "media_archive_validation_failed"
  $mediaVerifyOutput = & $docker.Source @composeArgs run --rm --no-deps --volume $verifyMount --entrypoint python api -m vayujit_api.operations.pc_media_backup_cli verify --archive "$containerMedia/verify-media.zip" --manifest "$containerMedia/verify-media.json" 2>$null
  Assert-BackupNativeExit -FailureCode "media_archive_validation_failed"
  if ($LASTEXITCODE -ne 0) { throw "media_archive_validation_failed" }
  if ($DisposableCertification) {
    $mediaVerification = Invoke-VayujitBackupStage -Operation "post-decryption media verification output parsing" -FailureCode "media_restore_report_invalid" -Action {
      ($mediaVerifyOutput -join "") | ConvertFrom-Json
    }
    $mediaRestoreVerified = $mediaVerification.verified_files -ge 1
    if (-not $mediaRestoreVerified) { throw "independent_media_restore_empty" }
    Set-BackupStage -Operation "canonical source integrity comparison" -FailureCode "source_integrity_verification_failed"
    $canonicalAfter = Get-CanonicalSnapshot $postgresContainer $evidenceFile
    $canonicalSourceUnchanged = $canonicalAfter -ceq $canonicalSnapshot
    if (-not $canonicalSourceUnchanged) { throw "source_canonical_data_changed_during_backup_rehearsal" }
  }
  Complete-BackupStage

  Set-BackupStage -Operation "encrypted artifact integrity manifest creation" -FailureCode "backup_artifact_manifest_creation_failed"
  $artifacts = @($databaseEncrypted, $mediaEncrypted, $manifestEncrypted)
  $files = foreach ($artifact in $artifacts) {
    $hash = Get-FileHash -LiteralPath $artifact -Algorithm SHA256
    [ordered]@{ name = [System.IO.Path]::GetFileName($artifact); size_bytes = (Get-Item $artifact).Length; sha256 = $hash.Hash.ToLowerInvariant() }
  }
  $sidecarPath = Join-Path $backupRoot "pc-backup-$backupId.json"
  Set-BackupStage -Operation "backup evidence report creation" -FailureCode "backup_evidence_report_write_failed"
  $sidecar = [ordered]@{
    format = "vayujit-pc-encrypted-backup-v1"
    backup_id = $backupId
    created_at_utc = [DateTime]::UtcNow.ToString("o")
    database_name = $dbName
    encryption = "age"
    profile = if ($DisposableCertification) { "disposable_certification_only" } else { "activated_pc_business" }
    recovery_identity_lifetime = if ($DisposableCertification) { "temporary_test_identity_not_retained" } else { "owner_custodied_permanent_identity" }
    database_validation = "independent_disposable_postgres_restore_passed"
    media_validation = "manifest_and_content_checksums_passed"
    backup_destination_independence = $independence
    postgres_storage_evidence = $postgresStorage.evidence
    media_storage_evidence = $mediaStorage.evidence
    backup_duration_seconds = [Math]::Round($backupTimer.Elapsed.TotalSeconds, 3)
    restore_duration_seconds = $restoreSeconds
    disposable_negative_tests = if ($DisposableCertification) { [ordered]@{ wrong_key_rejected = $wrongKeyRejected; corrupted_ciphertext_rejected = $corruptedCiphertextRejected } } else { $null }
    canonical_fixture_match = if ($DisposableCertification) { [ordered]@{ restored_database_match = $financePrecisionVerified; source_unchanged = $canonicalSourceUnchanged; media_restore_verified = $mediaRestoreVerified; checks = $restoreChecks } } else { $null }
    files = @($files)
  }
  [System.IO.File]::WriteAllText($sidecarPath, (($sidecar | ConvertTo-Json -Depth 6) + "`n"), [System.Text.UTF8Encoding]::new($false))
  $status = [ordered]@{ status = "success"; backup_id = $backupId; created_at_utc = [DateTime]::UtcNow.ToString("o"); file_count = 3; verification = "encrypted_decryption_independent_database_restore_and_media_integrity_passed"; backup_destination_independence = $independence; backup_duration_seconds = [Math]::Round($backupTimer.Elapsed.TotalSeconds, 3); restore_duration_seconds = $restoreSeconds }
  [System.IO.File]::WriteAllText($statusPath, (($status | ConvertTo-Json -Depth 4) + "`n"), [System.Text.UTF8Encoding]::new($false))
  if (-not $DisposableCertification) {
    $cutoff = [DateTime]::UtcNow.AddDays(-$retentionDays)
    foreach ($oldSidecar in Get-ChildItem -LiteralPath $backupRoot -Filter "pc-backup-*.json" -File) {
      if ($oldSidecar.Name -eq "last-backup-status.json" -or $oldSidecar.LastWriteTimeUtc -ge $cutoff) { continue }
      try {
        $old = Get-Content -LiteralPath $oldSidecar.FullName -Raw | ConvertFrom-Json
        foreach ($item in $old.files) {
          $safeName = [System.IO.Path]::GetFileName([string]$item.name)
          if ($safeName -like "pc-backup-*" -and (Test-Path -LiteralPath (Join-Path $backupRoot $safeName))) {
            Remove-Item -LiteralPath (Join-Path $backupRoot $safeName) -Force
          }
        }
        Remove-Item -LiteralPath $oldSidecar.FullName -Force
      } catch { Write-Warning "A retained backup group could not be rotated; it was kept for manual review." }
    }
  }
  Write-Output "Encrypted database and media backup verified: $backupId"
  if ($DisposableCertification) {
    $certification = [ordered]@{
      status = "PASS"
      profile = "marker_protected_disposable_only"
      artifacts_are_not_business_backups = $true
      recovery_identity_lifecycle = "Temporary private key is isolated in the marker-protected profile and is removed when the disposable runner cleans that profile."
      backup_id = $backupId
      artifact_directory = $backupRoot
      artifact_manifest = @($files)
      sidecar_sha256 = (Get-FileHash -LiteralPath $sidecarPath -Algorithm SHA256).Hash.ToLowerInvariant()
      destination_independence = $independence
      postgres_storage = $postgresStorage
      media_storage = $mediaStorage
      encrypted_artifact_header = $encryptedHeaderVerified
      wrong_key_rejected = $wrongKeyRejected
      corrupted_ciphertext_rejected = $corruptedCiphertextRejected
      canonical_records_restored_and_compared = $financePrecisionVerified
      financial_precision_verified = $financePrecisionVerified
      media_restored_and_checksums_verified = $mediaRestoreVerified
      source_canonical_records_unchanged = $canonicalSourceUnchanged
      backup_duration_seconds = [Math]::Round($backupTimer.Elapsed.TotalSeconds, 3)
      restore_duration_seconds = $restoreSeconds
      evidence = "Synthetic randomized disposable fixture only; never copy or promote to the permanent owner profile."
    }
    [System.IO.File]::WriteAllText($backupReportFullPath, (($certification | ConvertTo-Json -Depth 8) + "`n"), [System.Text.UTF8Encoding]::new($false))
  }
  Complete-BackupStage
  $backupCompleted = $true
} catch {
  $caughtFailure = $_
  foreach ($partial in @(
    "pc-backup-$backupId.database.dump.age",
    "pc-backup-$backupId.media.zip.age",
    "pc-backup-$backupId.media.json.age",
    "pc-backup-$backupId.json"
  )) {
    $partialPath = Join-Path $backupRoot $partial
    try {
      if (Test-Path -LiteralPath $partialPath) { Remove-Item -LiteralPath $partialPath -Force }
    } catch { Add-CleanupFailure "partial_artifact_cleanup_failed" }
  }
  $knownFailureMarker = if ($caughtFailure.Exception.Message -match '^[a-z][a-z0-9_]*$') { $caughtFailure.Exception.Message } else { $null }
  $stageFailureCode = $caughtFailure.Exception.Data["failure_code"]
  $stageFailureOperation = $caughtFailure.Exception.Data["failure_operation"]
  $stageNativeExitCode = $caughtFailure.Exception.Data["native_exit_code"]
  $failureCode = if ($stageFailureCode) { [string]$stageFailureCode } elseif ($knownFailureMarker) { $knownFailureMarker } elseif ($backupCurrentFailureCode) { $backupCurrentFailureCode } elseif ($null -ne $dockerFailureExitCode) { "docker_command_failed" } else { "backup_unexpected_exception" }
  $failureOperation = if ($stageFailureOperation) { [string]$stageFailureOperation } elseif ($backupCurrentOperation) { $backupCurrentOperation } elseif ($dockerFailureOperation) { $dockerFailureOperation } elseif ($knownFailureMarker) { $knownFailureMarker } else { "backup stage unclassified" }
  $nativeFailureExitCode = if ($null -ne $dockerFailureExitCode) { [int]$dockerFailureExitCode } elseif ($null -ne $stageNativeExitCode) { [int]$stageNativeExitCode } elseif ($null -ne $backupNativeExitCode) { [int]$backupNativeExitCode } else { $null }
  $failure = New-VayujitBackupFailureReport -BackupId $backupId -FailureOperation $failureOperation -FailureCode $failureCode -NativeExitCode $nativeFailureExitCode -DockerExitCode $dockerFailureExitCode -CleanupFailure $cleanupFailure
  $statusFailure = $failure.Clone()
  $statusFailure.status = "failed"
  try { [System.IO.File]::WriteAllText($statusPath, (($statusFailure | ConvertTo-Json -Depth 4) + "`n"), [System.Text.UTF8Encoding]::new($false)) } catch { }
  if ($DisposableCertification -and $backupReportFullPath) {
    try {
      [System.IO.File]::WriteAllText($backupReportFullPath, (($failure | ConvertTo-Json -Depth 5) + "`n"), [System.Text.UTF8Encoding]::new($false))
    } catch {
      $script:backupReportWriteFailed = $true
    }
  }
  $backupFailureMessage = if ($null -ne $nativeFailureExitCode) {
    "Encrypted backup failed during $failureOperation ($failureCode; native exit code $nativeFailureExitCode). No partial backup was certified."
  } else {
    "Encrypted backup failed during $failureOperation ($failureCode). No partial backup was certified."
  }
} finally {
  if ($DisposableCertification) {
    $wrongIdentityPath = Join-Path $configRoot "wrong-test-identity.agekey"
    if (Test-Path -LiteralPath $wrongIdentityPath) { Remove-Item -LiteralPath $wrongIdentityPath -Force -ErrorAction SilentlyContinue }
  }
  $apiReady = -not $apiStopped
  if ($apiStopped) {
    try {
      & $docker.Source @composeArgs start api 2>$null | Out-Null
      if ($LASTEXITCODE -ne 0) { throw "api_restart_failed" }
      $apiReady = $false
      for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $apiContainer = (& $docker.Source @composeArgs ps -q api 2>$null) -join ""
        if ($LASTEXITCODE -eq 0 -and $apiContainer) {
          $health = (& $docker.Source inspect --format '{{.State.Health.Status}}' $apiContainer 2>$null) -join ""
          if ($LASTEXITCODE -eq 0 -and $health -eq "healthy") { $apiReady = $true; break }
        }
        Start-Sleep -Seconds 2
      }
      if (-not $apiReady) { throw "api_restart_not_healthy" }
    } catch {
      Add-CleanupFailure "api_restart_failed"
      Write-Warning "The API could not be confirmed healthy after backup; check Docker health before reopening writes."
    }
  }
  if ($workerStopped) {
    $workerRecovery = Invoke-VayujitWorkerRecovery -StartWorker {
      & $docker.Source @composeArgs start worker 2>$null | Out-Null
      [pscustomobject]@{ ExitCode = [int]$LASTEXITCODE }
    } -GetHealth {
      $workerContainer = (& $docker.Source @composeArgs ps -q worker 2>$null) -join ""
      $lookupExit = [int]$LASTEXITCODE
      if ($lookupExit -ne 0) { return [pscustomobject]@{ ExitCode = $lookupExit; Status = "unknown" } }
      if (-not $workerContainer) { return [pscustomobject]@{ ExitCode = 0; Status = "starting" } }
      $health = (& $docker.Source inspect --format '{{.State.Health.Status}}' $workerContainer 2>$null) -join ""
      [pscustomobject]@{ ExitCode = [int]$LASTEXITCODE; Status = $health }
    }
    if ($workerRecovery.Status -ne "PASS") {
      Add-CleanupFailure $workerRecovery.FailureCode
      if ($null -ne $workerRecovery.DockerExitCode) {
        Write-Warning "Publishing worker recovery failed: $($workerRecovery.FailureCode) (Docker exit code $($workerRecovery.DockerExitCode)); health was '$($workerRecovery.LastHealth)'. Scheduled work is not confirmed healthy."
      } else {
        Write-Warning "Publishing worker recovery failed: $($workerRecovery.FailureCode); health was '$($workerRecovery.LastHealth)'. Scheduled work is not confirmed healthy."
      }
    }
  }
  if ($maintenanceOwned) {
    if (-not $apiReady) {
      Add-CleanupFailure "maintenance_marker_preserved_because_api_is_not_healthy"
      Write-Warning "The persistent maintenance marker was kept because the API is not healthy."
    } else {
      try {
        $maintenanceOff = (& $docker.Source @composeArgs exec -T api python -m vayujit_api.maintenance_cli maintenance-off --confirm 2>$null | ConvertFrom-Json)
        if ($LASTEXITCODE -ne 0 -or $maintenanceOff.maintenance) { throw "maintenance_clear_failed" }
      } catch {
        Add-CleanupFailure "maintenance_clear_failed"
        Write-Warning "Maintenance remains enabled; do not resume business writes until service health and the maintenance marker are reviewed."
      }
    }
  }
  try {
    if (Test-Path -LiteralPath $workRoot) { Remove-Item -LiteralPath $workRoot -Recurse -Force }
  } catch {
    Add-CleanupFailure "host_plaintext_staging_cleanup_failed"
    Write-Warning "Plaintext host staging could not be removed; inspect the exact generated backup-stage folder before resuming normal use."
  }
  foreach ($service in @('postgres', 'api')) {
    try {
      & $docker.Source @composeArgs exec -T $service rm -rf "/tmp/vayujit-pc-$backupId" 2>$null | Out-Null
      if ($LASTEXITCODE -ne 0) { throw "container_temporary_staging_cleanup_failed" }
    } catch {
      Add-CleanupFailure "container_temporary_staging_cleanup_failed"
      Write-Warning "Temporary container staging cleanup needs manual review; no database or media volume was removed."
    }
  }
}
if ($cleanupFailure) {
  if ($backupCompleted) {
    $failedStatus = [ordered]@{ status = "failed"; backup_id = $backupId; recorded_at_utc = [DateTime]::UtcNow.ToString("o"); failure_code = "service_recovery_failed"; recovery_hint = "Backup may have completed, but application recovery did not. Confirm API/worker health and maintenance marker before resuming writes." }
    try { [System.IO.File]::WriteAllText($statusPath, (($failedStatus | ConvertTo-Json -Depth 4) + "`n"), [System.Text.UTF8Encoding]::new($false)) } catch { }
  } elseif (Test-Path -LiteralPath $statusPath) {
    try {
      $failedStatus = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
      $failedStatus.cleanup_failure = $cleanupFailure
      [System.IO.File]::WriteAllText($statusPath, (($failedStatus | ConvertTo-Json -Depth 4) + "`n"), [System.Text.UTF8Encoding]::new($false))
    } catch { }
  }
  if ($DisposableCertification -and $backupReportFullPath -and (Test-Path -LiteralPath $backupReportFullPath)) {
    try {
      $certification = Get-Content -LiteralPath $backupReportFullPath -Raw | ConvertFrom-Json
      $certification = Set-VayujitBackupRecoveryFailure -Report $certification -CleanupFailure $cleanupFailure
      [System.IO.File]::WriteAllText($backupReportFullPath, (($certification | ConvertTo-Json -Depth 8) + "`n"), [System.Text.UTF8Encoding]::new($false))
    } catch {
      $script:backupReportWriteFailed = $true
    }
  }
}
if ($script:backupReportWriteFailed) {
  [Console]::Out.WriteLine("VAYUJIT_BACKUP_CHILD_BOUNDARY=backup_evidence_report_write_failed")
  throw "backup_evidence_report_write_failed"
}
if ($backupFailureMessage) {
  if ($cleanupFailure) { throw "$backupFailureMessage Recovery also reported: $cleanupFailure" }
  throw $backupFailureMessage
}
if ($cleanupFailure) {
  throw "Backup artifacts may exist, but service recovery failed: $cleanupFailure"
}
