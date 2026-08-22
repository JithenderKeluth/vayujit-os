param(
    [string]$Source = $env:VAYUJIT_MEDIA_STORAGE_DIRECTORY,
    [string]$Destination = "var/backups/media"
)
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Source)) { $Source = "var/media" }
$env:PYTHONPATH = Join-Path $PSScriptRoot "..\apps\api"
$python = Join-Path $PSScriptRoot "..\apps\api\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "API virtual environment is missing. Run npm.cmd run api:install." }
& $python -m vayujit_api.media_backup_cli backup $Source $Destination
exit $LASTEXITCODE
