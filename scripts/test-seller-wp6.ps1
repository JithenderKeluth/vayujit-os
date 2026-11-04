param([ValidateSet('Browser','Backend')][string]$Action='Browser')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repo
try {
    & (Join-Path $PSScriptRoot 'qa-postgres.ps1') -Action Environment
    $env:QA_PHASE='2'
    $env:QA_ORIGIN='http://127.0.0.1:4200'
    if ($Action -eq 'Browser') {
        $env:QA_MIGRATE='1'
        $env:QA_BROWSER_PHASE='WP6'
        & node qa/seller-browser-session.mjs
    } else {
        $token=[guid]::NewGuid().ToString('N').Substring(0,16)
        $output=Join-Path $repo ('tmp/qa-wp6-backend/'+$token)
        & apps/api/.venv/Scripts/python.exe -m qa.fixture_server --port 62106 --output $output --token $token --migrate --pytest test_seller_wp6.py test_seller_wp5.py test_pr_sos_04_inventory_orders.py
    }
    exit $LASTEXITCODE
} finally { Pop-Location }
