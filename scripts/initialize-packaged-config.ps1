param([string]$DataRoot = "")
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($DataRoot)) { $DataRoot = Join-Path $env:LOCALAPPDATA "VAYUJIT OS" }
$configRoot = Join-Path $DataRoot "config"
foreach ($folder in @($configRoot, (Join-Path $DataRoot "logs"), (Join-Path $DataRoot "backups"), (Join-Path $DataRoot "media"), (Join-Path $DataRoot "tmp"))) {
  New-Item -ItemType Directory -Path $folder -Force | Out-Null
}
$keyPath = Join-Path $configRoot "credential-encryption.key"
if (-not (Test-Path -LiteralPath $keyPath)) {
  $bytes = New-Object byte[] 32
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  $encoded = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
  [System.IO.File]::WriteAllText($keyPath, $encoded, [System.Text.UTF8Encoding]::new($false))
  & icacls.exe $keyPath /inheritance:r /grant:r "${env:USERNAME}:(R,W)" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Could not restrict encryption-key permissions." }
}
Write-Output $keyPath
