param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet("status", "validate", "collections", "publications", "executions")]
    [string]$Command
)
$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot "..\apps\api\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "API virtual environment is missing. Run npm.cmd run api:install."
}
& $python -m vayujit_api.shopify_cli $Command
exit $LASTEXITCODE
