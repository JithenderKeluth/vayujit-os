param([ValidateSet('Backend','Browser','Adjacent')][string]$Action='Backend')
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
        $output=Join-Path $repo ('tmp/qa-wp3-backend/'+$token)
        if ($Action -eq 'Adjacent') {
            & apps/api/.venv/Scripts/python.exe -m qa.fixture_server --port 62103 --output $output --token $token --migrate --pytest test_pr5b_landed_cost.py test_pr5c_unit_economics.py test_pr6a_decision_readiness.py test_pr6c_decision_workflow.py test_supplier_due_diligence.py
        } else {
            & apps/api/.venv/Scripts/python.exe -m qa.fixture_server --port 62103 --output $output --token $token --migrate --pytest test_seller_wp3.py test_seller_wp1.py test_seller_wp2.py
        }
    }
    exit $LASTEXITCODE
} finally { Pop-Location }
