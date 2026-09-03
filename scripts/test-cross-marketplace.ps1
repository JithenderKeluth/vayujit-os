$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$apiRoot = Join-Path $root 'apps/api'
$python = Join-Path $apiRoot '.venv/Scripts/python.exe'
if (-not (Test-Path $python)) { throw "Python virtual environment not found: $python" }
$env:VAYUJIT_TEST_DATABASE_URL = if ($env:VAYUJIT_TEST_DATABASE_URL) { $env:VAYUJIT_TEST_DATABASE_URL } else { 'postgresql+psycopg://vayujit:vayujit@127.0.0.1:5432/vayujit_test' }
Push-Location $apiRoot
try {
  & $python -m pytest -q tests/test_cross_marketplace_supplier_intelligence.py
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { Pop-Location }
