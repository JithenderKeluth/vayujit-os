param([string[]]$TestPath = @())
$ErrorActionPreference = "Stop"
Remove-Item Env:VAYUJIT_TEST_DATABASE_URL -ErrorAction SilentlyContinue
$env:VAYUJIT_ENV = "test"
$pytest = Join-Path $PSScriptRoot "..\apps\api\.venv\Scripts\pytest.exe"
$target = if ($TestPath.Count) {
    Join-Path $PSScriptRoot "..\apps\api\$($TestPath[0])"
} else {
    Join-Path $PSScriptRoot "..\apps\api"
}
& $pytest $target -m "not integration"
exit $LASTEXITCODE
