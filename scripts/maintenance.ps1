param(
    [Parameter(Position = 0, Mandatory = $true)]
    [string]$Command,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Remaining
)
$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot "..\apps\api\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "API virtual environment is missing. Run npm.cmd run api:install."
}
& $python -m vayujit_api.maintenance_cli $Command @Remaining
exit $LASTEXITCODE
