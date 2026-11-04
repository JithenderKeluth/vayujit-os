param([ValidateSet('Browser','Backend','Adjacent')][string]$Action='Browser')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repo
try {
    & (Join-Path $PSScriptRoot 'qa-postgres.ps1') -Action Environment
    $env:QA_PHASE='2'
    $env:QA_DATABASE_DROP_TIMEOUT_MS='90000'
    $env:QA_ORIGIN='http://127.0.0.1:4200'
    if ($Action -eq 'Browser') {
        $env:QA_MIGRATE='1'
        $env:QA_BROWSER_PHASE='WP6B'
        & node qa/seller-browser-session.mjs
    } else {
        $token=[guid]::NewGuid().ToString('N').Substring(0,16)
        $output=Join-Path $repo ('tmp/qa-wp6b-backend/'+$token)
        if ($Action -eq 'Adjacent') {
            & apps/api/.venv/Scripts/python.exe -m qa.fixture_server --port 62108 --output $output --token $token --migrate --pytest test_seller_wp6a.py test_seller_wp6a_migration.py test_seller_wp6.py test_seller_wp5.py test_pr_sos_04_inventory_orders.py
        } else {
            & apps/api/.venv/Scripts/python.exe -m qa.fixture_server --port 62108 --output $output --token $token --migrate --pytest test_seller_wp6b.py
        }
    }
    exit $LASTEXITCODE
} finally { Pop-Location }
