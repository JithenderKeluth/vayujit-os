$ErrorActionPreference = "Stop"
& npm.cmd run package:checksum
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& npm.cmd run package:verify
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& npm.cmd run release:prerequisites
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& npm.cmd run security:check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output "Release artifact, prerequisites, package contents, and production security checks passed."
