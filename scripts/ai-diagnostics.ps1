param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet("status", "validate", "usage-summary")]
    [string]$Command
)
$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot "..\apps\api\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "API virtual environment is missing. Run npm.cmd run api:install."
}
& $python -m vayujit_api.ai_cli $Command
exit $LASTEXITCODE
