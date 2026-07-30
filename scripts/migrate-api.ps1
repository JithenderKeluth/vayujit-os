$ErrorActionPreference = "Stop"
$apiRoot = Join-Path $PSScriptRoot "..\apps\api"
$alembic = Join-Path $apiRoot ".venv\Scripts\alembic.exe"
if (-not (Test-Path $alembic)) { throw "API environment missing. Run npm run api:install." }
Push-Location $apiRoot
try { & $alembic upgrade head } finally { Pop-Location }
