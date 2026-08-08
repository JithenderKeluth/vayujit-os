param([string]$Artifact = "")
$ErrorActionPreference = "Stop"
$releaseRoot = Join-Path $PSScriptRoot "..\release"
if ([string]::IsNullOrWhiteSpace($Artifact)) {
  $Artifact = (Get-ChildItem -LiteralPath $releaseRoot -Filter "VAYUJIT-OS-*-Setup.exe" | Select-Object -First 1).FullName
}
if (-not $Artifact -or -not (Test-Path -LiteralPath $Artifact)) { throw "Installer artifact not found." }
$checksum = "$Artifact.sha256"
if (-not (Test-Path -LiteralPath $checksum)) { throw "Checksum file not found." }
$expected = (Get-Content -LiteralPath $checksum -Raw).Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)[0].ToLowerInvariant()
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Artifact).Hash.ToLowerInvariant()
if ($expected -ne $actual) { throw "Checksum mismatch." }
$resources = Join-Path (Split-Path -Parent $Artifact) "win-unpacked\resources"
$entries = @()
if (Test-Path (Join-Path $resources "app.asar")) {
  $asar = Join-Path $PSScriptRoot "..\node_modules\.bin\asar.cmd"
  $entries += & $asar list (Join-Path $resources "app.asar")
}
$entries += Get-ChildItem -LiteralPath $resources -Recurse -Force | ForEach-Object { $_.FullName.Substring($resources.Length) }
foreach ($pattern in @('.env', 'vayujit_test', 'test credentials', 'private key', 'session cookie', 'api key')) {
  if ($entries -match [regex]::Escape($pattern)) { throw "Forbidden package marker found: $pattern" }
}
Write-Output "Package checksum and forbidden-content scan passed: $(Split-Path -Leaf $Artifact)"
