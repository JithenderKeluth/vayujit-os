$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\")).Path
$releaseRoot = Join-Path $repoRoot "release"
New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw "Application build failed." }
& npm.cmd exec -- electron-builder --win nsis --publish never
if ($LASTEXITCODE -ne 0) { throw "Windows packaging failed." }
Write-Output "Installer output: $releaseRoot"
