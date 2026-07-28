$ErrorActionPreference = "Stop"
$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$electron = Join-Path $repositoryRoot "node_modules\.bin\electron.cmd"

if (-not (Test-Path $electron)) {
    throw "Electron is not installed. Run npm.cmd install."
}

# Some automation hosts export this for Electron tooling. Inheriting it makes
# Electron behave as plain Node and prevents main-process APIs from loading.
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
Write-Host "Launching Electron runtime: $electron"
& $electron (Join-Path $repositoryRoot "apps\desktop")
exit $LASTEXITCODE
