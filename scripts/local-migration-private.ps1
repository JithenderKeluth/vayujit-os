param(
  [Parameter(Mandatory=$true)][ValidateSet('Prepare','Check')][string]$Action,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{16}$')][string]$Token,
  [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot 'pc-first-key-security.psm1') -Force
$stage=Join-Path $env:LOCALAPPDATA "VAYUJIT OS\migration-stage\$Token"
$keys=Join-Path $env:LOCALAPPDATA "VAYUJIT OS\migration-recovery-keys\$Token"
$backup=Join-Path ([IO.Path]::GetFullPath($Destination)) "migration-$Token"
$identity=Join-Path $keys 'recovery.agekey'
$wrong=Join-Path $keys 'wrong-check.agekey'
if($Action -eq 'Prepare') {
  foreach($path in @($stage,$keys,$backup)) {
    if(Test-Path -LiteralPath $path){throw 'private_run_path_exists'}
  }
  foreach($path in @($stage,$keys,$backup)) {
    New-Item -ItemType Directory -Path $path -ErrorAction Stop | Out-Null
    Set-VayujitPrivateAcl -Path $path -Kind Directory
    [IO.File]::WriteAllText((Join-Path $path 'migration-run.marker'),$Token)
  }
  $keygen=(Get-Command age-keygen -ErrorAction Stop).Source
  $null=New-VayujitPrivateAgeIdentity -AgeKeygenPath $keygen -IdentityPath $identity
  $null=New-VayujitPrivateAgeIdentity -AgeKeygenPath $keygen -IdentityPath $wrong
}
$checkDirectories=@($keys,$backup)
if($Action -eq 'Prepare' -or (Test-Path -LiteralPath $stage)){$checkDirectories+=@($stage)}
foreach($path in $checkDirectories) {
  Assert-VayujitPrivateAcl -Path $path -Kind Directory | Out-Null
  if([IO.File]::ReadAllText((Join-Path $path 'migration-run.marker')) -cne $Token){throw 'private_marker_mismatch'}
}
Assert-VayujitPrivateAcl -Path $identity -Kind File | Out-Null
if($Action -eq 'Prepare' -or (Test-Path -LiteralPath $wrong)) {
  Assert-VayujitPrivateAcl -Path $wrong -Kind File | Out-Null
}
$recipient=Get-VayujitAgeRecipient -AgeKeygenPath (Get-Command age-keygen -ErrorAction Stop).Source -IdentityPath $identity
@{stage=$stage;keys=$keys;backup=$backup;identity=$identity;wrong=$wrong;recipient=$recipient;acl='owner_and_SYSTEM_only'}|ConvertTo-Json -Compress
