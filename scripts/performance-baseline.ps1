$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\")).Path
$python = Join-Path $repoRoot "apps\api\.venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $repoRoot "apps\api"
& $python (Join-Path $PSScriptRoot "performance-baseline.py")
exit $LASTEXITCODE
