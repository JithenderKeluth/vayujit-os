param([ValidateSet('Browser','Backend')][string]$Action='Browser',[switch]$Focused)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repo
try {
    & (Join-Path $PSScriptRoot 'qa-postgres.ps1') -Action Environment
    $env:QA_PHASE='2'
    $env:QA_DATABASE_DROP_TIMEOUT_MS='90000'
    $env:QA_ORIGIN='http://127.0.0.1:4200'
    if($Action -eq 'Browser') {
        $env:QA_WP7A_FOCUSED=if($Focused){'1'}else{'0'}
        & node qa/wp7-run.mjs wp7a; exit $LASTEXITCODE
    }
    $token=[guid]::NewGuid().ToString('N').Substring(0,16)
    $output=Join-Path $repo ('tmp/qa-wp7a-backend/'+$token)
    Import-Module (Join-Path $PSScriptRoot 'pc-first-key-security.psm1') -Force
    $tests=@('test_seller_wp7a.py','test_pr_sos_04_inventory_orders.py','test_seller_wp6a.py','test_seller_wp6a_migration.py','test_business_agent_orchestration.py','test_product_source_review_integration.py')
    if($Focused){$tests=@('test_seller_wp7a.py')}
    $arguments=@('-m','qa.fixture_server','--port','62118','--output',$output,'--token',$token,'--migrate','--pytest')+$tests
    $result=Invoke-VayujitNativeCapture -FilePath (Join-Path $repo 'apps/api/.venv/Scripts/python.exe') -Arguments $arguments -WorkingDirectory $repo
    $record=@{token=$token;exit_code=$result.ExitCode;raw_output_persisted=$false;tests=$tests;output_bytes=($result.StdOut.Length+$result.StdErr.Length)}
    if(Test-Path -LiteralPath $output){[IO.File]::WriteAllText((Join-Path $output 'runner.json'),($record|ConvertTo-Json -Depth 4))}
    $record|ConvertTo-Json -Compress
    exit $result.ExitCode
} finally { Pop-Location }
