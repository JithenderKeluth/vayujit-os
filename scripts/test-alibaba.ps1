param(
  [string[]]$TestPath = @(
    "tests/test_alibaba_discovery.py",
    "tests/test_alibaba_integration.py",
    "tests/test_alibaba_hard_gate.py"
  )
)
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "prepare-test-database.ps1") -Purpose integration
$env:VAYUJIT_ENV = "test"
$env:VAYUJIT_ENVIRONMENT = "test"
$env:VAYUJIT_ALIBABA_ENABLED = "true"
$env:VAYUJIT_ALIBABA_MODE = "LOCAL_FIXTURE"
$env:VAYUJIT_TEST_DATABASE_URL = "postgresql+psycopg://vayujit:vayujit_dev@127.0.0.1:5432/vayujit_test"
$pytest = Join-Path $PSScriptRoot "..\apps\api\.venv\Scripts\pytest.exe"
$targets = $TestPath | ForEach-Object { Join-Path $PSScriptRoot "..\apps\api\$_" }
& $pytest $targets -m integration
exit $LASTEXITCODE
