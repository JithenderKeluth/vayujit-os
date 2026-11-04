param([ValidateSet('Backend','Browser')][string]$Action='Backend')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repo
try {
    & (Join-Path $PSScriptRoot 'qa-postgres.ps1') -Action Environment
    $env:QA_PHASE='2'
    $env:QA_ORIGIN='http://127.0.0.1:4200'
    if ($Action -eq 'Browser') {
        $env:QA_MIGRATE='1'
        & node qa/seller-browser-session.mjs
    } else {
        $token=[guid]::NewGuid().ToString('N').Substring(0,16)
        $output=Join-Path $repo ('tmp/qa-wp1-backend/'+$token)
        & apps/api/.venv/Scripts/python.exe -m qa.fixture_server --port 62101 --output $output --token $token --migrate --pytest test_seller_wp1.py test_intelligence_economic_foundation.py test_supplier_due_diligence.py
    }
    exit $LASTEXITCODE
} finally { Pop-Location }
