$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot 'local-api-process-security.psm1') -Force
$created=[datetime]::UtcNow
$stamp=$created.ToString('o')
$item=[pscustomobject]@{CreationDate=$created}
$script:stopped=0
Stop-VayujitCapturedProcess -CapturedId 99 -Created $stamp -ReadIdentity {param($v) $item} -StopCaptured {param($v) $script:stopped++}
if($script:stopped -ne 1){throw 'successful_stop_not_called'}
Stop-VayujitCapturedProcess -CapturedId 99 -Created $stamp -ReadIdentity {param($v) $null} -StopCaptured {throw 'must_not_stop_absent'}
$script:reads=0
Stop-VayujitCapturedProcess -CapturedId 99 -Created $stamp -ReadIdentity {param($v) $script:reads++;if($script:reads -eq 1){$item}} -StopCaptured {throw 'simulated_exit_race'}
if($script:reads -ne 2){throw 'absence_not_rechecked'}
$denied=$false
try {Stop-VayujitCapturedProcess -CapturedId 99 -Created $stamp -ReadIdentity {param($v) $item} -StopCaptured {throw 'genuine_stop_failure'}} catch {$denied=$true}
if(-not $denied){throw 'real_failure_suppressed'}
$denied=$false
try {Stop-VayujitCapturedProcess -CapturedId 99 -Created ($created.AddSeconds(-1).ToString('o')) -ReadIdentity {param($v) $item} -StopCaptured {throw 'must_not_stop_reused_pid'}} catch {$denied=$true}
if(-not $denied){throw 'reused_pid_not_rejected'}
$restored='{"paused":true,"resumed":false}' | ConvertFrom-Json
Initialize-VayujitApiResumeState -State $restored
$restored.new_root=123
if(($restored|ConvertTo-Json|ConvertFrom-Json).new_root -ne 123){throw 'resume_state_schema_not_initialized'}
$console=[pscustomobject]@{Name='conhost.exe';ParentProcessId=99;ExecutablePath=(Join-Path ([Environment]::SystemDirectory) 'conhost.exe')}
if(-not(Test-VayujitPrivateConsoleChild -Process $console -RootId 99)){throw 'private_console_not_recognized'}
if(Test-VayujitPrivateConsoleChild -Process $console -RootId 98){throw 'unrelated_console_accepted'}
$console.ExecutablePath='C:\unexpected\conhost.exe'
if(Test-VayujitPrivateConsoleChild -Process $console -RootId 99){throw 'noncanonical_console_accepted'}
@{passed=9;failed=0;mode='deterministic_mocked_process_controls_no_real_stop'}|ConvertTo-Json -Compress
