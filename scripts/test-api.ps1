$ErrorActionPreference = "Stop"
$apiRoot = Join-Path $PSScriptRoot "..\apps\api"
& (Join-Path $apiRoot ".venv\Scripts\pytest.exe") $apiRoot
