param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet("status", "validate", "destinations", "executions", "reconcile")]
    [string]$Command,
    [string]$ExecutionId
)
$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot "..\apps\api\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "API virtual environment is missing. Run npm.cmd run api:install."
}
$arguments = @("-m", "vayujit_api.publishing_cli", $Command)
if ($ExecutionId) { $arguments += @("--execution-id", $ExecutionId) }
& $python @arguments
exit $LASTEXITCODE
