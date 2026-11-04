param([ValidateSet('Create','Status','Start','Stop','Environment')][string]$Action='Status')
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Import-Module (Join-Path $PSScriptRoot 'pc-first-key-security.psm1') -Force
$docker=(Get-Command docker -ErrorAction Stop).Source
$python=Join-Path $repo 'apps\api\.venv\Scripts\python.exe'
$private=Join-Path $repo 'tmp\qa-postgres-private'
$manifestPath=Join-Path $private 'instance.json'
$evidence=Join-Path $repo 'tmp\qa-postgres-evidence'
function Docker-Checked([string[]]$Arguments){
  $r=Invoke-VayujitNativeCapture -FilePath $docker -Arguments $Arguments -WorkingDirectory $repo -TimeoutSeconds 90
  if($r.ExitCode -ne 0){throw 'QA Docker operation failed; raw command output omitted.'}
  return $r.StdOut.Trim()
}
function Python-Checked([string]$Mode){
  $r=Invoke-VayujitNativeCapture -FilePath $python -Arguments @('-m','qa.postgres_instance',$Mode) -WorkingDirectory $repo -TimeoutSeconds 90
  if($r.ExitCode -ne 0){throw 'QA instance attestation failed; inspect the safe validation record. No resource was removed.'}
  return $r.StdOut.Trim()
}
if($Action -eq 'Create'){
  # All collisions are fatal, including valid-looking resources and old profiles.
  $containers=@((Docker-Checked @('ps','-a','--format','{{.Names}}')) -split '\r?\n')
  $networks=@((Docker-Checked @('network','ls','--format','{{.Name}}')) -split '\r?\n')
  $volumes=@((Docker-Checked @('volume','ls','--format','{{.Name}}')) -split '\r?\n')
  if('vayujit-qa-postgres' -in $containers -or 'vayujit-qa-postgres-net' -in $networks -or 'vayujit-qa-postgres-host' -in $networks -or 'vayujit-qa-postgres-data' -in $volumes -or (Test-Path -LiteralPath $private)){throw 'QA resource/profile collision: STOP. Nothing reused, overwritten or removed.'}
  $listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,55432)
  try{$listener.Start()}finally{$listener.Stop()}
  $image=Docker-Checked @('image','inspect','postgres@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193','--format','{{.Id}}')
  New-Item -ItemType Directory -Path $evidence -Force|Out-Null
  # No environment, credentials or raw inspect output in the preservation record.
  $baseline=[ordered]@{containers=@();networks=$networks;volumes=$volumes}
  $ids=(Docker-Checked @('ps','-aq','--no-trunc')) -split '\r?\n'|Where-Object{$_}
  foreach($id in $ids){
    $c=(Docker-Checked @('inspect',$id)|ConvertFrom-Json)[0]
    $baseline.containers+=@{id=$c.Id;name=$c.Name;image=$c.Image;status=$c.State.Status;started=$c.State.StartedAt;finished=$c.State.FinishedAt;mounts=@($c.Mounts|Select-Object Type,Name,Source,Destination,RW);networks=@($c.NetworkSettings.Networks.PSObject.Properties.Name)}
  }
  [IO.File]::WriteAllText((Join-Path $evidence 'preflight.json'),($baseline|ConvertTo-Json -Depth 7))
  $cursor=[IO.DirectoryInfo]::new((Split-Path $private -Parent))
  while($cursor){if($cursor.Exists -and ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'QA private path reparse point denied'};$cursor=$cursor.Parent}
  $ignored=Invoke-VayujitNativeCapture -FilePath (Get-Command git).Source -Arguments @('-c',('safe.directory='+$repo.Replace('\','/')),'check-ignore','--no-index','--','tmp/qa-postgres-private/qa-password') -WorkingDirectory $repo
  if($ignored.ExitCode -ne 0){throw 'QA secret path must be Git-ignored'}
  New-Item -ItemType Directory -Path $private|Out-Null
  Set-VayujitPrivateAcl -Path $private -Kind Directory
  $instanceId=[guid]::NewGuid().ToString()
  foreach($name in @('bootstrap-password','qa-password','guard-key','instance-id')){
    $bytes=New-Object byte[] 32
    $rng=[Security.Cryptography.RandomNumberGenerator]::Create();try{$rng.GetBytes($bytes)}finally{$rng.Dispose()}
    $value=if($name -eq 'instance-id'){$instanceId}else{[Convert]::ToBase64String($bytes)}
    $file=Join-Path $private $name
    [IO.File]::WriteAllText($file,$value,[Text.UTF8Encoding]::new($false))
    Set-VayujitPrivateAcl -Path $file -Kind File
  }
  $env:VAYUJIT_QA_SECRET_DIR=$private.Replace('\','/')
  $env:VAYUJIT_QA_INSTANCE_ID=$instanceId
  $compose=@('compose','--project-name','vayujit-qa-postgres','-f',(Join-Path $repo 'infrastructure\docker-compose.qa.yml'))
  $null=Docker-Checked ($compose+@('config','--quiet'))
  # Never remove on failure: leave only our new labelled resources for inspection.
  $null=Docker-Checked ($compose+@('up','-d','--no-build','--pull','never'))
  $container=$null
  for($attempt=0;$attempt -lt 45;$attempt++){
    $container=(Docker-Checked @('inspect','vayujit-qa-postgres')|ConvertFrom-Json)[0]
    if($container.State.Health.Status -eq 'healthy'){break}
    Start-Sleep -Seconds 2
  }
  if($container.State.Health.Status -ne 'healthy'){throw 'New QA PostgreSQL did not become healthy; no resources removed.'}
  $m=[ordered]@{container_name='vayujit-qa-postgres';container_id=$container.Id;image_id=$image;instance_id=$instanceId;engine_id=(Docker-Checked @('info','--format','{{.ID}}'));docker_executable=$docker;host='127.0.0.1';port=55432;role='vayujit_qa_admin';scope='disposable-only'}
  [IO.File]::WriteAllText($manifestPath,($m|ConvertTo-Json),[Text.UTF8Encoding]::new($false))
  Set-VayujitPrivateAcl -Path $manifestPath -Kind File
  $null=Python-Checked 'attest'
  foreach($file in Get-ChildItem -LiteralPath $private -File){Assert-VayujitPrivateAcl -Path $file.FullName -Kind File|Out-Null}
  Python-Checked 'status'
}else{
  Assert-VayujitPrivateAcl -Path $private -Kind Directory|Out-Null
  foreach($file in @('instance.json','qa-password','guard-key','bootstrap-password')){Assert-VayujitPrivateAcl -Path (Join-Path $private $file) -Kind File|Out-Null}
  $identity=Python-Checked 'identity'|ConvertFrom-Json
  if($Action -eq 'Stop'){$null=Docker-Checked @('stop','--time','30',$identity.container_id);Write-Output 'Stopped only the attested QA container; storage retained.'}
  elseif($Action -eq 'Start'){$null=Docker-Checked @('start',$identity.container_id);Write-Output 'Started only the attested QA container; check Status after health settles.'}
  elseif($Action -eq 'Environment'){
    $null=Python-Checked 'status'
    $password=[Uri]::EscapeDataString([IO.File]::ReadAllText((Join-Path $private 'qa-password')).Trim())
    $env:QA_DATABASE_ADMIN_URL='postgresql+psycopg://vayujit_qa_admin:'+ $password +'@127.0.0.1:55432/postgres'
    $env:QA_POSTGRES_INSTANCE_MANIFEST=$manifestPath
    $env:QA_PYTHON=$python
    $password=$null
    Write-Output 'QA-only environment configured in this shell; no credentials displayed.'
  }else{Python-Checked 'status'}
}
