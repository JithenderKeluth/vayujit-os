$ErrorActionPreference = "Stop"
$apiRoot = Join-Path $PSScriptRoot "..\apps\api"
$bin = Join-Path $apiRoot ".venv\Scripts"
& (Join-Path $bin "ruff.exe") check $apiRoot
& (Join-Path $bin "black.exe") --check $apiRoot
& (Join-Path $bin "mypy.exe") $apiRoot
