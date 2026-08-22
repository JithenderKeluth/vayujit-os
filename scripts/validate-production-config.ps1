param([ValidateSet("local", "test", "development", "staging", "production")][string]$Environment = "production")
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:PYTHONPATH = Join-Path $repo "apps\api"
$env:VAYUJIT_ENVIRONMENT = $Environment
& (Join-Path $repo "apps\api\.venv\Scripts\python.exe") -m vayujit_api.config_cli
exit $LASTEXITCODE