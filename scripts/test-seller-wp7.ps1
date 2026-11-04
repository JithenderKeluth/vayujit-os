param([ValidateSet('Browser','Backend','Financial','Inventory')][string]$Action='Inventory',[string[]]$Suites=@('surface'))
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repo
try {
    if($Action -eq 'Inventory') { & node qa/wp7-inventory.mjs; exit $LASTEXITCODE }
    & (Join-Path $PSScriptRoot 'qa-postgres.ps1') -Action Environment
    $env:QA_PHASE='2'
    $env:QA_DATABASE_DROP_TIMEOUT_MS='90000'
    $env:QA_ORIGIN='http://127.0.0.1:4200'
    if($Action -eq 'Browser') { & node qa/wp7-run.mjs @Suites; exit $LASTEXITCODE }
    $token=[guid]::NewGuid().ToString('N').Substring(0,16)
    $output=Join-Path $repo ('tmp/qa-wp7-backend/'+$token)
    Import-Module (Join-Path $PSScriptRoot 'pc-first-key-security.psm1') -Force
    $tests=@('test_seller_wp1.py','test_seller_wp2.py','test_seller_wp3.py','test_seller_wp4.py','test_seller_wp5.py','test_seller_wp6.py','test_seller_wp6a.py','test_seller_wp6b.py','test_seller_wp6a_migration.py','test_pr5b_landed_cost.py','test_pr5c_unit_economics.py','test_pr6a_decision_readiness.py','test_pr6c_decision_workflow.py','test_pr_sos_04_inventory_orders.py','test_pr_sos_05_financials.py','test_pr_sos_06_action_center.py','test_qa_phase3a_remediation.py','test_qa_phase3b_remediation.py','test_qa_phase4b_opening_stock.py','test_product_opportunity_scoring.py','test_pr_sos_01_catalog.py','test_business_agent_orchestration.py','test_product_source_review_integration.py','test_intelligence_economic_foundation.py','test_intelligence_economic_calculation.py','test_supplier_due_diligence.py')
    if($Action -eq 'Financial'){$tests=@('test_pr_sos_05_financials.py','test_seller_wp6b.py')}
    $arguments=@('-m','qa.fixture_server','--port','62118','--output',$output,'--token',$token,'--migrate','--pytest')+$tests
    # Pytest tracebacks can contain a database URL. Capture in memory, never log raw output.
    $result=Invoke-VayujitNativeCapture -FilePath (Join-Path $repo 'apps/api/.venv/Scripts/python.exe') -Arguments $arguments -WorkingDirectory $repo
    $record=@{token=$token;exit_code=$result.ExitCode;raw_output_persisted=$false;tests=$tests;output_bytes=($result.StdOut.Length+$result.StdErr.Length)}
    if(Test-Path -LiteralPath $output){[IO.File]::WriteAllText((Join-Path $output 'runner.json'),($record|ConvertTo-Json -Depth 4))}
    $record|ConvertTo-Json -Compress
    exit $result.ExitCode
} finally { Pop-Location }
