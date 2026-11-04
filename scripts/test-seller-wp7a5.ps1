param([ValidateSet('Browser','Backend','BackendRemaining')][string]$Action='Browser',[switch]$Focused)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repo
try {
    & (Join-Path $PSScriptRoot 'qa-postgres.ps1') -Action Environment
    $env:QA_PHASE='2'; $env:QA_DATABASE_DROP_TIMEOUT_MS='90000'; $env:QA_ORIGIN='http://127.0.0.1:4200'
    $env:QA_BROWSER_PHASE='WP7A5'
    if($Action -eq 'Browser') {
        $env:QA_WP7A_FOCUSED=if($Focused){'1'}else{'0'}
        & node qa/wp7-run.mjs wp7a5; exit $LASTEXITCODE
    }
    $token=[guid]::NewGuid().ToString('N').Substring(0,16)
    $output=Join-Path $repo ('tmp/qa-wp7a5-backend/'+$token)
    Import-Module (Join-Path $PSScriptRoot 'pc-first-key-security.psm1') -Force
    $tests=@('test_seller_wp7a5.py','test_ai_seo.py','test_ai_video_bulk_e2e.py','test_ai_video_bulk_restart.py','test_social_video_acceptance.py','test_social_video_durable.py','test_trend_analysis_api.py','test_pr_sos_02_amazon_controls.py','test_pr_sos_03_flipkart_controls.py')
    if($Focused){$tests=@('test_seller_wp7a5.py','test_ai_studio_e2e.py','test_ai_images_integration.py','test_ai_images_bulk.py')}
    if($Action -eq 'BackendRemaining'){$tests=@('test_seller_wp7a5.py','test_ai_video_bulk_e2e.py','test_trend_analysis_api.py')}
    $result=Invoke-VayujitNativeCapture -FilePath (Join-Path $repo 'apps/api/.venv/Scripts/python.exe') -Arguments (@('-m','qa.fixture_server','--port','62119','--output',$output,'--token',$token,'--migrate','--pytest')+$tests) -WorkingDirectory $repo
    $record=@{token=$token;exit_code=$result.ExitCode;raw_output_persisted=$false;tests=$tests;output_bytes=($result.StdOut.Length+$result.StdErr.Length)}
    if(Test-Path -LiteralPath $output){[IO.File]::WriteAllText((Join-Path $output 'runner.json'),($record|ConvertTo-Json -Depth 4))}
    $record|ConvertTo-Json -Compress
    exit $result.ExitCode
} finally { Pop-Location }
