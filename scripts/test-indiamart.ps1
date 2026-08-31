param(
  [string[]]$TestPath = @(
    "tests/test_indiamart_discovery.py",
    "tests/test_indiamart_certification.py",
    "tests/test_indiamart_proof.py",
    "tests/test_indiamart_change_alert_matrix.py",
    "tests/test_indiamart_rejected_data.py",
    "tests/test_indiamart_risk_contradiction_matrix.py",
    "tests/test_indiamart_retry_recovery.py",
    "tests/test_indiamart_crash_recovery.py",
    "tests/test_indiamart_concurrency.py",
    "tests/test_indiamart_storage_integrity.py",
    "tests/test_indiamart_performance.py",
    "tests/test_indiamart_query_counts.py",
    "tests/test_indiamart_security_privacy.py"
  )
)
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "prepare-test-database.ps1") -Purpose integration
$env:VAYUJIT_ENV = "test"
$env:VAYUJIT_ENVIRONMENT = "test"
$env:VAYUJIT_INDIAMART_ENABLED = "true"
$env:VAYUJIT_INDIAMART_MODE = "LOCAL_FIXTURE"
$env:VAYUJIT_TEST_DATABASE_URL = "postgresql+psycopg://vayujit:vayujit_dev@127.0.0.1:5432/vayujit_test"
$pytest = Join-Path $PSScriptRoot "..\apps\api\.venv\Scripts\pytest.exe"
$targets = $TestPath | ForEach-Object { Join-Path $PSScriptRoot "..\apps\api\$_" }
& $pytest $targets -m integration
exit $LASTEXITCODE
