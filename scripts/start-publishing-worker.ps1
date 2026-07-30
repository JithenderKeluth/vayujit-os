$ErrorActionPreference = "Stop"
$apiRoot = Join-Path $PSScriptRoot "..\apps\api"
$python = Join-Path $apiRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "API environment missing. Run npm.cmd run api:install." }
$env:PYTHONPATH = $apiRoot
& $python -m vayujit_api.publishing.worker run
