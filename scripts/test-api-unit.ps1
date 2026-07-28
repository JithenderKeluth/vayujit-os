$ErrorActionPreference = "Stop"
Remove-Item Env:VAYUJIT_TEST_DATABASE_URL -ErrorAction SilentlyContinue
$env:VAYUJIT_ENV = "test"
$pytest = Join-Path $PSScriptRoot "..\apps\api\.venv\Scripts\pytest.exe"
& $pytest (Join-Path $PSScriptRoot "..\apps\api") -m "not integration"
exit $LASTEXITCODE
