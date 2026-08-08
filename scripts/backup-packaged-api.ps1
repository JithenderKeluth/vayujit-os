param(
  [string]$DataRoot = "",
  [string]$DatabaseUrl = ""
)
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($DataRoot)) { $DataRoot = Join-Path $env:LOCALAPPDATA "VAYUJIT OS" }
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { $DatabaseUrl = $env:VAYUJIT_DATABASE_URL }
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { $DatabaseUrl = "postgresql://vayujit:vayujit_dev@127.0.0.1:5432/vayujit" }
$resolver = Join-Path $PSScriptRoot "resolve-pg-dump.ps1"
$pgDump = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $resolver
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace("$pgDump")) { throw "pg_dump.exe is required before a packaged upgrade. Install PostgreSQL 17 client tools or set VAYUJIT_PG_DUMP_PATH to a validated executable path." }
$normalized = $DatabaseUrl -replace '^postgresql\+[^:]+://', 'postgresql://'
$uri = [Uri]$normalized
$user = [Uri]::UnescapeDataString($uri.UserInfo.Split(':')[0])
$password = if ($uri.UserInfo.Contains(':')) { [Uri]::UnescapeDataString($uri.UserInfo.Split(':', 2)[1]) } else { "" }
$database = $uri.AbsolutePath.TrimStart('/')
$dbHost = $uri.Host
$dbPort = if ($uri.Port -gt 0) { $uri.Port } else { 5432 }
$backupRoot = Join-Path $DataRoot "backups"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $backupRoot "pre-upgrade-$stamp.dump"
$oldPassword = $env:PGPASSWORD
try {
  $env:PGPASSWORD = $password
  & $pgDump --format=custom --file=$backupPath --host=$dbHost --port=$dbPort --username=$user --dbname=$database
  if ($LASTEXITCODE -ne 0) { throw "Database backup failed; migrations were not started." }
} finally {
  if ($null -eq $oldPassword) { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue } else { $env:PGPASSWORD = $oldPassword }
}
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $backupPath).Hash.ToLowerInvariant()
"$hash  $(Split-Path -Leaf $backupPath)" | Set-Content -LiteralPath "$backupPath.sha256" -Encoding ascii
Write-Output "$backupPath`n$backupPath.sha256"
