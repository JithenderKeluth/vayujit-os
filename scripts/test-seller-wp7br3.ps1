param()
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repo
try {
    # Process-local environment only. Never stop/reconfigure the normal application.
    & (Join-Path $PSScriptRoot 'qa-postgres.ps1') -Action Environment
    & node qa/wp7br3-session.mjs
    exit $LASTEXITCODE
} finally { Pop-Location }
