param(
  [Parameter(Mandatory = $true)][string]$BackupRoot,
  [string]$DataRoot = (Join-Path $env:LOCALAPPDATA "VAYUJIT OS")
)
$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "pc-first-key-security.psm1") -Force
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dataFull = [System.IO.Path]::GetFullPath($DataRoot)
$backupFull = [System.IO.Path]::GetFullPath($BackupRoot)
if ($dataFull.StartsWith($repo, [System.StringComparison]::OrdinalIgnoreCase) -or
    $backupFull.StartsWith($repo, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "PC operational data and backup folders must be outside the source repository."
}
if (-not (Get-Command age-keygen -ErrorAction SilentlyContinue) -or
    -not (Get-Command age -ErrorAction SilentlyContinue)) {
  throw "Install the approved age Windows binaries (age and age-keygen) before initializing encrypted backups."
}

$dataDrive = [System.IO.Path]::GetPathRoot($dataFull).TrimEnd('\').TrimEnd(':').ToUpperInvariant()
$backupDrive = [System.IO.Path]::GetPathRoot($backupFull).TrimEnd('\').TrimEnd(':').ToUpperInvariant()
if (-not $dataDrive -or -not $backupDrive -or $dataDrive -eq $backupDrive) {
  throw "Choose a backup folder on a different physical drive from PC data ($dataFull)."
}
try {
  $dataDisk = (Get-Partition -DriveLetter $dataDrive).DiskNumber
  $backupDisk = (Get-Partition -DriveLetter $backupDrive).DiskNumber
  if ($dataDisk -eq $backupDisk) {
    throw "The backup path is on the same physical disk. Use a second disk or encrypted external drive."
  }
} catch {
  if ($_.Exception.Message -match "same physical disk") { throw }
  throw "Could not verify that the backup destination is on a separate physical disk: $($_.Exception.Message)"
}

$configRoot = Join-Path $dataFull "config"
$mediaRoot = Join-Path $dataFull "media"
$logsRoot = Join-Path $dataFull "logs"
$stageRoot = Join-Path $dataFull "backup-stage"
$identityPath = Join-Path $configRoot "backup.agekey"
$appEnvPath = Join-Path $configRoot "app.env"
$composeEnvPath = Join-Path $configRoot "compose.env"
$markerPath = Join-Path $configRoot "pc-install.json"
if (Test-Path $markerPath) {
  throw "A PC profile already exists at $configRoot. Refusing to rotate or replace its credentials."
}
foreach ($generatedSecret in @($identityPath, $appEnvPath, $composeEnvPath)) {
  if (Test-Path -LiteralPath $generatedSecret) {
    throw "Partial PC profile material already exists at $configRoot. Refusing to overwrite secrets; follow the documented safe recovery procedure."
  }
}
foreach ($folder in @($configRoot, $mediaRoot, $logsRoot, $stageRoot, $backupFull)) {
  New-Item -ItemType Directory -Path $folder -Force | Out-Null
}
Set-VayujitPrivateAcl -Path $configRoot -Kind Directory

function New-HexSecret([int]$Length = 32) {
  $bytes = New-Object byte[] $Length
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  return [BitConverter]::ToString($bytes).Replace("-", "").ToLowerInvariant()
}
function Write-PrivateText([string]$Path, [string]$Text) {
  [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
  & icacls.exe $Path /inheritance:r /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(R,W)" "NT AUTHORITY\SYSTEM:(R)" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Could not restrict access to $Path" }
}

$ageKeygen = Get-Command age-keygen -ErrorAction Stop
$recipient = New-VayujitPrivateAgeIdentity -AgeKeygenPath $ageKeygen.Source -IdentityPath $identityPath

$dbRootPassword = New-HexSecret
$appPassword = New-HexSecret
$sessionSecret = New-HexSecret
$credentialBytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($credentialBytes) } finally { $rng.Dispose() }
$credentialKey = [Convert]::ToBase64String($credentialBytes)
$appEnv = @(
  "VAYUJIT_ENVIRONMENT=pc_local"
  "VAYUJIT_DEBUG=false"
  "VAYUJIT_DATABASE_URL=postgresql+psycopg://vayujit_app:$appPassword@postgres:5432/vayujit_business"
  "VAYUJIT_WEB_ORIGIN=http://127.0.0.1:8443"
  "VAYUJIT_ALLOWED_ORIGINS=http://127.0.0.1:8443,http://localhost:8443"
  "VAYUJIT_SESSION_SECRET=$sessionSecret"
  "VAYUJIT_SESSION_LIFETIME_HOURS=12"
  "VAYUJIT_SESSION_SECURE_COOKIE=false"
  "VAYUJIT_SESSION_SAME_SITE=strict"
  "VAYUJIT_ALLOW_MISSING_ORIGIN=false"
  "VAYUJIT_REQUIRE_HTTPS=false"
  "VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP=true"
  "VAYUJIT_LIVE_AI_ENABLED=false"
  "VAYUJIT_LIVE_SOCIAL_PUBLISHING_ENABLED=false"
  "VAYUJIT_LIVE_MARKETPLACE_MUTATIONS_ENABLED=false"
  "VAYUJIT_LIVE_ADS_MUTATIONS_ENABLED=false"
  "VAYUJIT_ADS_LIVE_SPEND_ENABLED=false"
  "VAYUJIT_EMAIL_DELIVERY_ENABLED=false"
  "VAYUJIT_LIVE_EMAIL_DELIVERY_ENABLED=false"
  "VAYUJIT_SHOPIFY_LIVE_MUTATION_ENABLED=false"
  "VAYUJIT_PUBLISHING_WORKER_ENABLED=true"
  "VAYUJIT_CREDENTIAL_ENCRYPTION_KEY=$credentialKey"
  "VAYUJIT_CREDENTIAL_ENCRYPTION_KEY_ID=pc-local-current"
  "VAYUJIT_STORAGE_PROVIDER=filesystem"
  "VAYUJIT_MEDIA_STORAGE_DIRECTORY=/var/lib/vayujit/media"
  "VAYUJIT_BACKUP_DIRECTORY=/var/lib/vayujit/backups"
  "VAYUJIT_MAINTENANCE_MARKER=/var/lib/vayujit/maintenance/enabled"
  "VAYUJIT_BACKUP_RETENTION_DAYS=90"
  "VAYUJIT_EXPECTED_MIGRATION_REVISION=20261203_0146"
  "VAYUJIT_TRUSTED_PROXY_IPS=172.16.0.0/12"
) -join "`n"
$appPathForCompose = $appEnvPath.Replace('\', '/')
$composeEnv = @(
  "VAYUJIT_PC_PROJECT_NAME=vayujit-pc-business"
  "VAYUJIT_PC_VOLUME_PREFIX=vayujit_pc_business"
  "VAYUJIT_PC_HTTP_PORT=8443"
  "VAYUJIT_PC_APP_ENV_FILE=$appPathForCompose"
  "VAYUJIT_PC_BACKUP_ROOT=$($backupFull.Replace('\', '/'))"
  "VAYUJIT_PC_STAGE_ROOT=$($stageRoot.Replace('\', '/'))"
  "VAYUJIT_PC_AGE_IDENTITY_FILE=$($identityPath.Replace('\', '/'))"
  "VAYUJIT_PC_AGE_RECIPIENT=$recipient"
  "VAYUJIT_PC_BACKUP_RETENTION_DAYS=90"
  "POSTGRES_DB=postgres"
  "POSTGRES_USER=postgres"
  "POSTGRES_PASSWORD=$dbRootPassword"
  "VAYUJIT_DATABASE_NAME=vayujit_business"
  "VAYUJIT_DATABASE_USER=vayujit_app"
  "VAYUJIT_DATABASE_PASSWORD=$appPassword"
) -join "`n"
Write-PrivateText $appEnvPath ($appEnv + "`n")
Write-PrivateText $composeEnvPath ($composeEnv + "`n")
Write-PrivateText $markerPath ((@{
  marker = "vayujit-pc-first-live-v1"
  installation_id = [guid]::NewGuid().ToString()
  created_at_utc = [DateTime]::UtcNow.ToString("o")
  data_root = $dataFull
  backup_root = $backupFull
  volume_prefix = "vayujit_pc_business"
  activation = "prepared_not_started"
  database_name = "vayujit_business"
  external_mutations = "disabled"
} | ConvertTo-Json -Depth 4) + "`n")

Write-Output "PC profile prepared at $dataFull. No database was started or seeded."
Write-Output "Encrypted backups target the separate drive at $backupFull."
Write-Output "Keep the private age identity backed up offline; loss of that identity makes encrypted backups unrecoverable."
Write-Output "Next: run scripts/start-pc-first.ps1 and confirm first activation when ready."
