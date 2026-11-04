function Stop-VayujitCapturedProcess {
  param(
    [Parameter(Mandatory=$true)][int]$CapturedId,
    [Parameter(Mandatory=$true)][string]$Created,
    [scriptblock]$ReadIdentity = {param($Value) Get-CimInstance Win32_Process -Filter ('ProcessId='+$Value)},
    [scriptblock]$StopCaptured = {param($Value) Stop-Process -Id $Value -Force -ErrorAction Stop}
  )
  $live=& $ReadIdentity $CapturedId
  if(-not $live){return}
  if($live.CreationDate.ToUniversalTime().ToString('o') -cne $Created){throw 'api_pid_reused'}
  try { & $StopCaptured $CapturedId }
  catch {
    # A supervisor exit can naturally terminate its captured child between the
    # identity check and Stop-Process. Accept only positively observed absence.
    $remaining=& $ReadIdentity $CapturedId
    if($remaining){throw}
  }
}
function Initialize-VayujitApiResumeState {
  param([Parameter(Mandatory=$true)]$State)
  $State | Add-Member -NotePropertyName new_root -NotePropertyValue $null -Force
}
function Test-VayujitPrivateConsoleChild {
  param($Process,[int]$RootId)
  return ($Process.Name -ieq 'conhost.exe' -and $Process.ParentProcessId -eq $RootId -and
    $Process.ExecutablePath -ieq (Join-Path ([Environment]::SystemDirectory) 'conhost.exe'))
}
Export-ModuleMember -Function Stop-VayujitCapturedProcess,Initialize-VayujitApiResumeState,Test-VayujitPrivateConsoleChild
