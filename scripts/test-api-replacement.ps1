$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "prepare-test-database.ps1") -Purpose integration
$env:VAYUJIT_ENV = "test"
$env:VAYUJIT_TEST_DATABASE_URL = "postgresql+psycopg://vayujit:vayujit_dev@127.0.0.1:5432/vayujit_test"
$pytest = Join-Path $PSScriptRoot "..\apps\api\.venv\Scripts\pytest.exe"
& $pytest (Join-Path $PSScriptRoot "..\apps\api\tests\test_campaign_replacement_fixture.py") (Join-Path $PSScriptRoot "..\apps\api\tests\test_campaign_artifact_replacement.py") -m integration
exit $LASTEXITCODE
