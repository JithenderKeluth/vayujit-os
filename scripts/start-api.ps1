$ErrorActionPreference = "Stop"
$apiRoot = Join-Path $PSScriptRoot "..\apps\api"
$python = Join-Path $apiRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "API environment missing. Run npm run api:install." }
& $python -m uvicorn vayujit_api.main:app --app-dir $apiRoot --host 127.0.0.1 --port 8000 --reload
