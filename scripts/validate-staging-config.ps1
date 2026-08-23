param()
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:PYTHONPATH = Join-Path $repo "apps\api"
$env:VAYUJIT_ENVIRONMENT = "staging"
& (Join-Path $repo "apps\api\.venv\Scripts\python.exe") -m vayujit_api.config_cli
exit $LASTEXITCODE
