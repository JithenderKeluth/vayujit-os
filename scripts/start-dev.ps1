$ErrorActionPreference = "Stop"
if (-not (Test-Path (Join-Path $PSScriptRoot "..\.env"))) {
    Write-Warning "No root .env found; defaults from .env.example-compatible settings will be used."
}
npm run db:up
npm run db:migrate
npm run dev
