param([string]$Artifact = "")
$ErrorActionPreference = "Stop"
$releaseRoot = Join-Path $PSScriptRoot "..\release"
if ([string]::IsNullOrWhiteSpace($Artifact)) {
  $Artifact = (Get-ChildItem -LiteralPath $releaseRoot -Filter "VAYUJIT-OS-*-Setup.exe" | Select-Object -First 1).FullName
}
if (-not $Artifact -or -not (Test-Path -LiteralPath $Artifact)) { throw "Installer artifact not found. Run npm.cmd run package:windows first." }
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Artifact).Hash.ToLowerInvariant()
$checksumPath = "$Artifact.sha256"
"$hash  $(Split-Path -Leaf $Artifact)" | Set-Content -LiteralPath $checksumPath -Encoding ascii
Write-Output $checksumPath
