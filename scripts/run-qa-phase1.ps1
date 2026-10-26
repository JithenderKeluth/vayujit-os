param([switch]$AuditOnly)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$node = Get-Command node -ErrorAction Stop
Push-Location $repo
try {
    if ($AuditOnly) {
        & $node.Source 'qa/audit.mjs'
    } else {
        if (-not $env:QA_DATABASE_ADMIN_URL) {
            throw 'QA_DATABASE_ADMIN_URL is required: loopback PostgreSQL admin connection, database postgres. Never use a business database URL.'
        }
        & $node.Source 'qa/run.mjs'
    }
    if ($LASTEXITCODE -ne 0) { throw "QA Phase 1 returned exit code $LASTEXITCODE. Review docs/qa/initial-report.md; do not infer PASS." }
} finally { Pop-Location }
