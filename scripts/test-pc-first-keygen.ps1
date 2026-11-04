$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "pc-first-key-security.psm1") -Force

$runId = [guid]::NewGuid().ToString("N")
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$testRoot = Join-Path $tempRoot "vayujit-keygen-regression-$runId"
$expectedTempPrefix = $tempRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
$passed = 0
$skipped = 0

function Assert-Regression([bool]$Condition, [string]$Message) {
  if (-not $Condition) { throw $Message }
  $script:passed++
  Write-Output "PASS $Message"
}

try {
  New-Item -ItemType Directory -Path $testRoot -ErrorAction Stop | Out-Null
  $privateDirectory = Join-Path $testRoot "private"
  New-Item -ItemType Directory -Path $privateDirectory -ErrorAction Stop | Out-Null
  Set-VayujitPrivateAcl -Path $privateDirectory -Kind Directory
  Assert-Regression (Assert-VayujitPrivateAcl -Path $privateDirectory -Kind Directory) "private directory ACL allows only current owner and SYSTEM"
  Set-VayujitPrivateAcl -Path $privateDirectory -Kind Directory
  Assert-Regression (Assert-VayujitPrivateAcl -Path $privateDirectory -Kind Directory) "reapplying a compliant private directory ACL is idempotent without rewriting its security descriptor"

  # cmd.exe has custom /c quoting rules and does not consume its command tail
  # like a normal Windows argv-based executable. Use the current PowerShell
  # executable as the native probe so this test exercises the shared helper's
  # ordinary Windows argument quoting and redirected stderr behavior.
  $powerShellPath = (Get-Process -Id $PID -ErrorAction Stop).Path
  if (-not $powerShellPath -or -not (Test-Path -LiteralPath $powerShellPath -PathType Leaf)) {
    throw "Could not resolve the current PowerShell executable for native-process regression probes."
  }
  $warningProbe = "[Console]::Out.WriteLine('harmless-output-token'); [Console]::Error.WriteLine('age-keygen: warning: writing secret key to a world-readable file'); exit 0"
  $fakeProcess = Invoke-VayujitNativeChecked -FilePath $powerShellPath -Arguments @("-NoLogo", "-NoProfile", "-NonInteractive", "-Command", $warningProbe) -Operation "stderr warning regression"
  Assert-Regression ($fakeProcess.ExitCode -eq 0 -and -not $fakeProcess.PSObject.Properties["StdOut"] -and -not $fakeProcess.PSObject.Properties["StdErr"]) "successful native stderr warning is captured without becoming a PowerShell error or exposing streams"
  $failedSafely = $false
  $failureProbe = "[Console]::Error.WriteLine('private-sentinel-do-not-log'); exit 23"
  try { Invoke-VayujitNativeChecked -FilePath $powerShellPath -Arguments @("-NoLogo", "-NoProfile", "-NonInteractive", "-Command", $failureProbe) -Operation "test native utility" | Out-Null } catch { $failedSafely = $_.Exception.Message -match "exit code 23" -and $_.Exception.Message -notmatch "private-sentinel" }
  Assert-Regression $failedSafely "native nonzero exit fails closed without including stderr contents"
  $expectedFailureProbe = "[Console]::Error.WriteLine('decrypt-failure-sentinel'); exit 7"
  $expectedFailure = Test-VayujitNativeFailure -FilePath $powerShellPath -Arguments @("-NoLogo", "-NoProfile", "-NonInteractive", "-Command", $expectedFailureProbe)
  Assert-Regression $expectedFailure "expected wrong-key style native failure is recognized without surfacing stderr"

  $testIdentityPath = Join-Path $privateDirectory "acl-fixture.agekey"
  $testIdentityText = "# created: 2026-01-01T00:00:00Z`n# public key: age1regressionfixture`nAGE-SECRET-KEY-1REGRESSIONFIXTURE`n"
  Write-VayujitPrivateIdentity -Path $testIdentityPath -IdentityText $testIdentityText
  Assert-Regression (Assert-VayujitPrivateAcl -Path $testIdentityPath -Kind File) "identity file ACL excludes Everyone, Users, inherited, and other principals"
  Assert-Regression ((Get-Content -LiteralPath $testIdentityPath -Raw).Contains("AGE-SECRET-KEY-1REGRESSIONFIXTURE")) "identity writer stores the captured key only in the protected file"
  $invalidIdentityRejected = $false
  try { Write-VayujitPrivateIdentity -Path (Join-Path $privateDirectory "invalid.agekey") -IdentityText "not-an-age-identity" } catch { $invalidIdentityRejected = $true }
  Assert-Regression ($invalidIdentityRejected -and -not (Test-Path -LiteralPath (Join-Path $privateDirectory "invalid.agekey"))) "missing or invalid private-key output is rejected before writing a file"

  $systemDriveRoot = [System.IO.Path]::GetPathRoot($env:SystemDrive + "\")
  $rootEvidencePath = Join-Path $systemDriveRoot "vayujit-certification-$runId.json"
  $resolvedRootEvidence = Resolve-VayujitEvidencePath -Path $rootEvidencePath
  Assert-Regression ([System.IO.Path]::GetDirectoryName($resolvedRootEvidence).TrimEnd('\') -eq $systemDriveRoot.TrimEnd('\')) "evidence path directly under a drive root resolves without creating the existing root"
  $nestedEvidencePath = Join-Path (Join-Path $testRoot "new-evidence-directory") "certification.json"
  $resolvedNestedEvidence = Resolve-VayujitEvidencePath -Path $nestedEvidencePath
  Assert-Regression ((Test-Path -LiteralPath ([System.IO.Path]::GetDirectoryName($resolvedNestedEvidence)) -PathType Container) -and $resolvedNestedEvidence -eq [System.IO.Path]::GetFullPath($nestedEvidencePath)) "evidence path creates a missing nested report directory"

  $ageKeygen = Get-Command age-keygen -ErrorAction SilentlyContinue
  if ($ageKeygen) {
    $identityOne = Join-Path $privateDirectory "generated-one.agekey"
    $identityTwo = Join-Path $privateDirectory "generated-two.agekey"
    $recipientOne = New-VayujitPrivateAgeIdentity -AgeKeygenPath $ageKeygen.Source -IdentityPath $identityOne
    $recipientTwo = New-VayujitPrivateAgeIdentity -AgeKeygenPath $ageKeygen.Source -IdentityPath $identityTwo
    Assert-Regression ($recipientOne -is [string] -and $recipientTwo -is [string] -and $recipientOne -match '^age1[0-9a-z]+$' -and $recipientTwo -match '^age1[0-9a-z]+$' -and $recipientOne -ne $recipientTwo) "age-keygen creates and validates independent identities without returning private material"
    Assert-Regression ((Assert-VayujitPrivateAcl -Path $identityOne -Kind File) -and (Assert-VayujitPrivateAcl -Path $identityTwo -Kind File)) "real age identities have restrictive NTFS ACLs"
  } else {
    $skipped++
    Write-Output "SKIP real age-keygen integration: age-keygen is not available in PATH."
  }
} finally {
  $resolvedTestRoot = [System.IO.Path]::GetFullPath($testRoot)
  if (-not $resolvedTestRoot.StartsWith($expectedTempPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove a key-generation regression fixture outside the system temp directory."
  }
  if (Test-Path -LiteralPath $resolvedTestRoot) { Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force }
}

Write-Output "PC-first key-generation regression checks: $passed passed; $skipped skipped."
