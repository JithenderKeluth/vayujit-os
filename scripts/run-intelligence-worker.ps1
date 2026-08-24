$ErrorActionPreference = "Stop"
$apiRoot = Join-Path $PSScriptRoot "..\apps\api"
Push-Location $apiRoot
try {
  & ".\.venv\Scripts\python.exe" -m vayujit_api.intelligence.worker once
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
  Pop-Location
}
