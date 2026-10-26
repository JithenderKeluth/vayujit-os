Set-StrictMode -Version 2.0

function Get-VayujitCurrentUserSid {
  $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
  if (-not $identity.User) { throw "Could not resolve the current Windows user SID." }
  return $identity.User
}

function Set-VayujitPrivateAcl {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][ValidateSet("Directory", "File")][string]$Kind
  )
  $fullPath = [System.IO.Path]::GetFullPath($Path)
  if ($Kind -eq "Directory") {
    if (-not (Test-Path -LiteralPath $fullPath -PathType Container)) { throw "Private directory does not exist." }
  } elseif (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
    throw "Private file does not exist."
  }

  $alreadyPrivate = $false
  try {
    $alreadyPrivate = Assert-VayujitPrivateAcl -Path $fullPath -Kind $Kind
  } catch {
    # A noncompliant or inherited ACL must be replaced below. Any failure to
    # read or write the resulting ACL remains fatal at the normal checks.
  }
  if ($alreadyPrivate) { return }

  $acl = Get-Acl -LiteralPath $fullPath -ErrorAction Stop
  $acl.SetAccessRuleProtection($true, $false)
  foreach ($rule in @($acl.Access)) { $acl.RemoveAccessRuleSpecific($rule) }

  $ownerSid = Get-VayujitCurrentUserSid
  $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
  $fullControl = [System.Security.AccessControl.FileSystemRights]::FullControl
  $systemRights = if ($Kind -eq "Directory") { [System.Security.AccessControl.FileSystemRights]::ReadAndExecute } else { [System.Security.AccessControl.FileSystemRights]::Read }
  $allow = [System.Security.AccessControl.AccessControlType]::Allow
  if ($Kind -eq "Directory") {
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $ownerRule = [System.Security.AccessControl.FileSystemAccessRule]::new($ownerSid, $fullControl, $inherit, [System.Security.AccessControl.PropagationFlags]::None, $allow)
    $systemRule = [System.Security.AccessControl.FileSystemAccessRule]::new($systemSid, $systemRights, $inherit, [System.Security.AccessControl.PropagationFlags]::None, $allow)
  } else {
    $ownerRule = [System.Security.AccessControl.FileSystemAccessRule]::new($ownerSid, $fullControl, $allow)
    $systemRule = [System.Security.AccessControl.FileSystemAccessRule]::new($systemSid, $systemRights, $allow)
  }
  $acl.SetOwner($ownerSid)
  $acl.AddAccessRule($ownerRule)
  $acl.AddAccessRule($systemRule)
  Set-Acl -LiteralPath $fullPath -AclObject $acl -ErrorAction Stop
  Assert-VayujitPrivateAcl -Path $fullPath -Kind $Kind | Out-Null
}

function Assert-VayujitPrivateAcl {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][ValidateSet("Directory", "File")][string]$Kind
  )
  $fullPath = [System.IO.Path]::GetFullPath($Path)
  $acl = Get-Acl -LiteralPath $fullPath -ErrorAction Stop
  $ownerSid = Get-VayujitCurrentUserSid
  $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
  $aclOwnerSid = $acl.GetOwner([System.Security.Principal.SecurityIdentifier])
  if (-not $acl.AreAccessRulesProtected -or $aclOwnerSid.Value -ne $ownerSid.Value) {
    throw "Private $Kind ACL is not protected for the current owner."
  }

  $allowedSids = @($ownerSid.Value, $systemSid.Value)
  $rules = @($acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]))
  $seenSids = @{}
  $ownerRights = [System.Security.AccessControl.FileSystemRights]0
  $systemRights = [System.Security.AccessControl.FileSystemRights]0
  foreach ($rule in $rules) {
    if ($rule.IsInherited -or $rule.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow -or
        $rule.IdentityReference.Value -notin $allowedSids) {
      throw "Private $Kind ACL grants or inherits access beyond the current owner and SYSTEM."
    }
    $seenSids[$rule.IdentityReference.Value] = $true
    if ($rule.IdentityReference.Value -eq $ownerSid.Value) { $ownerRights = $ownerRights -bor $rule.FileSystemRights }
    if ($rule.IdentityReference.Value -eq $systemSid.Value) { $systemRights = $systemRights -bor $rule.FileSystemRights }
  }
  foreach ($sid in $allowedSids) {
    if (-not $seenSids.ContainsKey($sid)) { throw "Private $Kind ACL is missing a required owner or SYSTEM entry." }
  }
  $requiredSystemRights = if ($Kind -eq "Directory") { [System.Security.AccessControl.FileSystemRights]::ReadAndExecute } else { [System.Security.AccessControl.FileSystemRights]::Read }
  if (($ownerRights -band [System.Security.AccessControl.FileSystemRights]::FullControl) -ne [System.Security.AccessControl.FileSystemRights]::FullControl -or
      ($systemRights -band $requiredSystemRights) -ne $requiredSystemRights) {
    throw "Private $Kind ACL does not grant the required owner and SYSTEM access."
  }
  return $true
}

function ConvertTo-VayujitWindowsArgument {
  param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value)
  $builder = [System.Text.StringBuilder]::new()
  [void]$builder.Append([char]34)
  $slashes = 0
  foreach ($character in $Value.ToCharArray()) {
    if ($character -eq [char]92) { $slashes++; continue }
    if ($character -eq [char]34) {
      [void]$builder.Append([char]92, (2 * $slashes) + 1)
      [void]$builder.Append([char]34)
    } else {
      if ($slashes -gt 0) { [void]$builder.Append([char]92, $slashes) }
      [void]$builder.Append($character)
    }
    $slashes = 0
  }
  if ($slashes -gt 0) { [void]$builder.Append([char]92, 2 * $slashes) }
  [void]$builder.Append([char]34)
  return $builder.ToString()
}

function Invoke-VayujitNativeCapture {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [string[]]$Arguments = @(),
    [string[]]$RemoveEnvironmentVariables = @()
  )
  $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $startInfo.FileName = $FilePath
  $startInfo.Arguments = (($Arguments | ForEach-Object { ConvertTo-VayujitWindowsArgument -Value ([string]$_) }) -join " ")
  $startInfo.UseShellExecute = $false
  $startInfo.CreateNoWindow = $true
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  foreach ($environmentName in $RemoveEnvironmentVariables) {
    if ($environmentName -match '^[A-Za-z_][A-Za-z0-9_]*$') {
      [void]$startInfo.EnvironmentVariables.Remove($environmentName)
    }
  }
  $process = [System.Diagnostics.Process]::new()
  $process.StartInfo = $startInfo
  try {
    if (-not $process.Start()) { throw "Could not start the requested security utility." }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    return [pscustomobject]@{ ExitCode = $process.ExitCode; StdOut = $stdout; StdErr = $stderr }
  } finally {
    $process.Dispose()
  }
}

function Assert-VayujitNativeSuccess {
  param(
    [Parameter(Mandatory = $true)]$Result,
    [Parameter(Mandatory = $true)][string]$Operation
  )
  if ($Result.ExitCode -ne 0) { throw "$Operation failed with exit code $($Result.ExitCode)." }
}

function Invoke-VayujitNativeChecked {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [string[]]$Arguments = @(),
    [Parameter(Mandatory = $true)][string]$Operation
  )
  $result = Invoke-VayujitNativeCapture -FilePath $FilePath -Arguments $Arguments
  Assert-VayujitNativeSuccess -Result $result -Operation $Operation
  return [pscustomobject]@{ ExitCode = $result.ExitCode }
}

function Test-VayujitNativeFailure {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [string[]]$Arguments = @()
  )
  $result = Invoke-VayujitNativeCapture -FilePath $FilePath -Arguments $Arguments
  return ($result.ExitCode -ne 0)
}

function Write-VayujitPrivateIdentity {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$IdentityText
  )
  $secretKeys = [regex]::Matches($IdentityText, "(?m)^AGE-SECRET-KEY-[A-Z0-9-]+\s*$")
  if ($secretKeys.Count -ne 1 -or $IdentityText.Length -gt 16384) {
    throw "age-keygen output did not contain exactly one valid private identity."
  }
  $fullPath = [System.IO.Path]::GetFullPath($Path)
  $parent = [System.IO.Path]::GetDirectoryName($fullPath)
  if (-not $parent -or -not (Test-Path -LiteralPath $parent -PathType Container)) { throw "Private identity directory is unavailable." }
  Set-VayujitPrivateAcl -Path $parent -Kind Directory
  $stream = $null
  try {
    $stream = [System.IO.File]::Open($fullPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    $stream.Dispose()
    $stream = $null
    Set-VayujitPrivateAcl -Path $fullPath -Kind File
    [System.IO.File]::WriteAllText($fullPath, $IdentityText, [System.Text.UTF8Encoding]::new($false))
    Assert-VayujitPrivateAcl -Path $fullPath -Kind File | Out-Null
  } catch {
    if ($stream) { $stream.Dispose() }
    if (Test-Path -LiteralPath $fullPath -PathType Leaf) { Remove-Item -LiteralPath $fullPath -Force -ErrorAction SilentlyContinue }
    throw
  }
}

function Get-VayujitAgeRecipient {
  param(
    [Parameter(Mandatory = $true)][string]$AgeKeygenPath,
    [Parameter(Mandatory = $true)][string]$IdentityPath
  )
  Assert-VayujitPrivateAcl -Path $IdentityPath -Kind File | Out-Null
  $result = Invoke-VayujitNativeCapture -FilePath $AgeKeygenPath -Arguments @("-y", [System.IO.Path]::GetFullPath($IdentityPath))
  Assert-VayujitNativeSuccess -Result $result -Operation "age-keygen recipient derivation"
  $recipient = $result.StdOut.Trim()
  if ($recipient -notmatch '^age1[0-9a-z]+$') { throw "age-keygen returned an invalid recipient." }
  return $recipient
}

function New-VayujitPrivateAgeIdentity {
  param(
    [Parameter(Mandatory = $true)][string]$AgeKeygenPath,
    [Parameter(Mandatory = $true)][string]$IdentityPath
  )
  $fullPath = [System.IO.Path]::GetFullPath($IdentityPath)
  if (Test-Path -LiteralPath $fullPath) { throw "Refusing to overwrite an existing age identity." }
  $parent = [System.IO.Path]::GetDirectoryName($fullPath)
  if (-not $parent -or -not (Test-Path -LiteralPath $parent -PathType Container)) { throw "Private identity directory is unavailable." }
  Set-VayujitPrivateAcl -Path $parent -Kind Directory
  $result = Invoke-VayujitNativeCapture -FilePath $AgeKeygenPath
  Assert-VayujitNativeSuccess -Result $result -Operation "age-keygen identity generation"
  try {
    Write-VayujitPrivateIdentity -Path $fullPath -IdentityText $result.StdOut
    return (Get-VayujitAgeRecipient -AgeKeygenPath $AgeKeygenPath -IdentityPath $fullPath)
  } catch {
    if (Test-Path -LiteralPath $fullPath -PathType Leaf) { Remove-Item -LiteralPath $fullPath -Force -ErrorAction SilentlyContinue }
    throw
  }
}

function Resolve-VayujitEvidencePath {
  param([Parameter(Mandatory = $true)][string]$Path)
  $fullPath = [System.IO.Path]::GetFullPath($Path)
  $directory = [System.IO.Path]::GetDirectoryName($fullPath)
  if ([string]::IsNullOrWhiteSpace($directory)) { throw "Evidence report directory could not be resolved." }
  if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
    New-Item -ItemType Directory -Path $directory -Force -ErrorAction Stop | Out-Null
  }
  return $fullPath
}

Export-ModuleMember -Function @(
  "Assert-VayujitNativeSuccess",
  "Assert-VayujitPrivateAcl",
  "Get-VayujitAgeRecipient",
  "Invoke-VayujitNativeCapture",
  "Invoke-VayujitNativeChecked",
  "New-VayujitPrivateAgeIdentity",
  "Resolve-VayujitEvidencePath",
  "Set-VayujitPrivateAcl",
  "Test-VayujitNativeFailure",
  "Write-VayujitPrivateIdentity"
)
