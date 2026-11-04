param([switch]$Integration)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repo
try {
    if ($Integration) {
        & (Join-Path $PSScriptRoot 'qa-postgres.ps1') -Action Environment
        $env:QA_PHASE = '2'
        $env:QA_ORIGIN = 'http://127.0.0.1:4200'
        $qaDiscoveryToken = [guid]::NewGuid().ToString('N').Substring(0, 16)
        & apps/api/.venv/Scripts/python.exe -m qa.fixture_server --port 62107 --output ('tmp/qa-discovery-regression/' + $qaDiscoveryToken) --token $qaDiscoveryToken --migrate --pytest test_product_source_review_integration.py test_business_agent_orchestration.py
    } else {
        Push-Location (Join-Path $repo 'apps/api')
        try {
            & .venv/Scripts/python.exe -m pytest tests/test_product_discovery_planning.py tests/test_product_discovery_boundaries.py tests/test_gp75_product_discovery.py tests/test_gp76_product_research.py --no-cov -q
        } finally { Pop-Location }
    }
    exit $LASTEXITCODE
} finally { Pop-Location }
