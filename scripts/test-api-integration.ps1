param([string[]]$TestPath = @(), [string]$DatabaseName = "vayujit_test", [string]$Marker = "integration")
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "prepare-test-database.ps1") -Purpose integration -DatabaseName $DatabaseName
$env:VAYUJIT_ENV = "test"
$env:VAYUJIT_ENVIRONMENT = "test"
$env:VAYUJIT_TEST_DATABASE_URL = "postgresql+psycopg://vayujit:vayujit_dev@127.0.0.1:5432/$DatabaseName"
$pytest = Join-Path $PSScriptRoot "..\apps\api\.venv\Scripts\pytest.exe"
$target = if ($TestPath.Count) {
    Join-Path $PSScriptRoot "..\apps\api\$($TestPath[0])"
} else {
    Join-Path $PSScriptRoot "..\apps\api"
}
& $pytest $target -m $Marker
exit $LASTEXITCODE
