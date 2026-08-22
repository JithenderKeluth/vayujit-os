param(
    [Parameter(Mandatory = $true)][string]$Archive,
    [Parameter(Mandatory = $true)][string]$Manifest,
    [Parameter(Mandatory = $true)][string]$Destination
)
$ErrorActionPreference = "Stop"
if ($Destination -match "production|prod") { throw "Restore target is not an approved disposable path." }
$env:PYTHONPATH = Join-Path $PSScriptRoot "..\apps\api"
$python = Join-Path $PSScriptRoot "..\apps\api\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "API virtual environment is missing. Run npm.cmd run api:install." }
& $python -m vayujit_api.media_backup_cli restore $Archive $Manifest $Destination
exit $LASTEXITCODE
