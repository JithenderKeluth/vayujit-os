param(
  [string]$ApiRoot = "",
  [string]$DataRoot = "",
  [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ApiRoot)) { $ApiRoot = Join-Path $PSScriptRoot "..\api" }
if ([string]::IsNullOrWhiteSpace($DataRoot)) { $DataRoot = Join-Path $env:LOCALAPPDATA "VAYUJIT OS" }
$keyPath = & (Join-Path $PSScriptRoot "initialize-packaged-config.ps1") -DataRoot $DataRoot
$venvPython = Join-Path $DataRoot "runtime\api-venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
  throw "Local API runtime is not installed. Run install-packaged-api.ps1 first."
}
$env:VAYUJIT_APP_VERSION = "0.1.0-rc.1"
$env:VAYUJIT_ENV = "production"
$env:VAYUJIT_ALLOWED_ORIGINS = "app://vayujit"
$env:VAYUJIT_SESSION_SECURE_COOKIE = "true"
$env:VAYUJIT_CREDENTIAL_ENCRYPTION_KEY = [System.IO.File]::ReadAllText($keyPath).Trim()
$env:VAYUJIT_BACKUP_DIRECTORY = Join-Path $DataRoot "backups"
$env:VAYUJIT_MEDIA_STORAGE_DIRECTORY = Join-Path $DataRoot "media"
$env:VAYUJIT_MAINTENANCE_MARKER = Join-Path $DataRoot "maintenance.enabled"
$env:VAYUJIT_LOG_LEVEL = "INFO"
$env:VAYUJIT_API_PORT = [string]$Port
$env:PYTHONPATH = $ApiRoot
Push-Location $ApiRoot
try {
  & (Join-Path $PSScriptRoot "backup-packaged-api.ps1") -DataRoot $DataRoot -DatabaseUrl $env:VAYUJIT_DATABASE_URL
  if ($LASTEXITCODE -ne 0) { throw "Backup failed; database migrations were not started." }
  & $venvPython -m alembic -c (Join-Path $ApiRoot "alembic.ini") upgrade head
  if ($LASTEXITCODE -ne 0) { throw "Database migration failed; application startup was stopped." }
  & $venvPython -m uvicorn vayujit_api.main:app --host 127.0.0.1 --port $Port
  exit $LASTEXITCODE
} finally { Pop-Location }
