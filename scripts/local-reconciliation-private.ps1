param([Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{16}$')][string]$Token)
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot 'pc-first-key-security.psm1') -Force
$stage=Join-Path $env:LOCALAPPDATA "VAYUJIT OS\migration-stage\$Token"
if(Test-Path -LiteralPath $stage){throw 'private_run_path_exists'}
New-Item -ItemType Directory -Path $stage -ErrorAction Stop | Out-Null
Set-VayujitPrivateAcl -Path $stage -Kind Directory
[IO.File]::WriteAllText((Join-Path $stage 'migration-run.marker'),$Token)
Assert-VayujitPrivateAcl -Path $stage -Kind Directory | Out-Null
@{stage=$stage;acl='owner_and_SYSTEM_only'}|ConvertTo-Json -Compress
