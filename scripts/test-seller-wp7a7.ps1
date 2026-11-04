param([ValidateSet('Backend','Browser')][string]$Action='Backend',[switch]$Focused)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repo
try {
  & (Join-Path $PSScriptRoot 'qa-postgres.ps1') -Action Environment
  $env:QA_PHASE='2'; $env:QA_BROWSER_PHASE='WP7A7'
  $env:QA_DATABASE_DROP_TIMEOUT_MS='90000'; $env:QA_ORIGIN='http://127.0.0.1:4200'
  if($Action -eq 'Browser') {
    $env:QA_WP7A_FOCUSED=if($Focused){'1'}else{'0'}
    & node qa/wp7-run.mjs wp7a7
    exit $LASTEXITCODE
  }
  $token=[guid]::NewGuid().ToString('N').Substring(0,16)
  $output=Join-Path $repo ('tmp/qa-wp7a7-backend/'+$token)
  Import-Module (Join-Path $PSScriptRoot 'pc-first-key-security.psm1') -Force
  $tests=@('test_seller_wp7a7.py')
  if(-not $Focused){$tests+=@('test_seller_wp7a6.py','test_pr_sos_02_amazon_controls.py','test_pr_sos_03_flipkart_controls.py','test_social_video_acceptance.py','test_social_video_durable.py','test_ads_concurrency_acceptance.py','test_ads_version_safety_acceptance.py','test_campaign_activity_rescheduling.py','test_campaign_recovery_dispatch.py')}
  $started=[DateTime]::UtcNow.ToString('o')
  $sourceFiles=@(Get-ChildItem -LiteralPath (Join-Path $repo 'apps/api/vayujit_api'),(Join-Path $repo 'apps/api/tests'),(Join-Path $repo 'qa') -Recurse -File -Filter '*.py')
  $before=@{}
  foreach($sourceFile in $sourceFiles){$before[$sourceFile.FullName.Substring($repo.Length+1)]=(Get-FileHash -LiteralPath $sourceFile.FullName -Algorithm SHA256).Hash}
  $result=Invoke-VayujitNativeCapture -FilePath (Join-Path $repo 'apps/api/.venv/Scripts/python.exe') -Arguments (@('-m','qa.fixture_server','--port','62129','--output',$output,'--token',$token,'--migrate','--pytest')+$tests) -WorkingDirectory $repo
  $record=@{token=$token;started_at=$started;exit_code=$result.ExitCode;raw_output_persisted=$false;tests=$tests;output_bytes=($result.StdOut.Length+$result.StdErr.Length)}
  $record.source_unchanged=$true
  foreach($sourceFile in $sourceFiles){if($before[$sourceFile.FullName.Substring($repo.Length+1)] -cne (Get-FileHash -LiteralPath $sourceFile.FullName -Algorithm SHA256).Hash){$record.source_unchanged=$false}}
  if(Test-Path -LiteralPath $output){[IO.File]::WriteAllText((Join-Path $output 'tested-source-sha256.json'),($before|ConvertTo-Json -Depth 3))}
  if(Test-Path -LiteralPath $output){[IO.File]::WriteAllText((Join-Path $output 'runner.json'),($record|ConvertTo-Json -Depth 4))}
  $record|ConvertTo-Json -Compress
  exit $result.ExitCode
} finally { Pop-Location }
