param([ValidateSet('Browser','Baseline','Quality','Backend')][string]$Action='Browser')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repo
try {
  if($Action -eq 'Quality'){ & node qa/wp7b-quality.mjs; exit $LASTEXITCODE }
  $approval=Get-Content -LiteralPath (Join-Path $repo 'tmp/qa-wp7b/owner-authorization.json') -Raw|ConvertFrom-Json
  if($approval.task_specific_database_approval -ne $true){throw 'Task-specific WP7B disposable authorization required'}
  & (Join-Path $PSScriptRoot 'qa-postgres.ps1') -Action Environment
  if($Action -eq 'Backend'){
    $env:QA_PHASE='2'; $env:QA_BROWSER_PHASE='WP7A7'; $env:QA_DATABASE_DROP_TIMEOUT_MS='90000'; $env:QA_ORIGIN='http://127.0.0.1:4200'
    $token=[guid]::NewGuid().ToString('N').Substring(0,16)
    $output=Join-Path $repo ('tmp/qa-wp7b-backend/'+$token)
    Import-Module (Join-Path $PSScriptRoot 'pc-first-key-security.psm1') -Force
    $result=Invoke-VayujitNativeCapture -FilePath (Join-Path $repo 'apps/api/.venv/Scripts/python.exe') -Arguments @('-m','qa.fixture_server','--port','62129','--output',$output,'--token',$token,'--migrate','--pytest','test_ads_version_safety_acceptance.py','test_ads_concurrency_acceptance.py','test_seller_wp6b.py') -WorkingDirectory $repo
    $record=@{token=$token;exit_code=$result.ExitCode;raw_output_persisted=$false;output_bytes=($result.StdOut.Length+$result.StdErr.Length)}
    if(Test-Path -LiteralPath $output){[IO.File]::WriteAllText((Join-Path $output 'runner.json'),($record|ConvertTo-Json))}
    $record|ConvertTo-Json -Compress
    exit $result.ExitCode
  }
  $env:WP7B_BASELINE=if($Action -eq 'Baseline'){'1'}else{'0'}
  & node qa/wp7-run.mjs wp7b
  exit $LASTEXITCODE
} finally { Pop-Location }
