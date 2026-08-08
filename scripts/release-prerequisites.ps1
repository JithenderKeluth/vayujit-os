$ErrorActionPreference = "Stop"
$failures = [System.Collections.Generic.List[string]]::new()
if ($env:OS -ne "Windows_NT") { $failures.Add("Windows is required.") }
$version = $null
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $version = (& $py.Source -3.12 --version 2>$null) }
if ($version -notmatch "Python 3\.12\.") {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) { $version = (& $python.Source --version 2>$null) }
}
if ($version -notmatch "Python 3\.12\.") {
  $failures.Add("Python 3.12 is required; found $version.")
}
$postgres = Test-NetConnection -ComputerName 127.0.0.1 -Port 5432 -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $postgres) { $failures.Add("PostgreSQL is not reachable at 127.0.0.1:5432.") }
$pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
if (-not $pgDump) { $failures.Add("pg_dump is required for backup-before-upgrade.") }
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\")).Path
foreach ($path in @((Join-Path $repoRoot "apps\api"), (Join-Path $repoRoot "apps\api\alembic"), (Join-Path $repoRoot "release"))) {
  if (-not (Test-Path -LiteralPath $path)) { $failures.Add("Required path is missing: $path") }
}
$pythonExe = Join-Path $repoRoot "apps\api\.venv\Scripts\python.exe"
if (Test-Path -LiteralPath $pythonExe) {
  & $pythonExe -m alembic --help *> $null
  if ($LASTEXITCODE -ne 0) { $failures.Add("Alembic is not available in the repository API environment.") }
}
if ($failures.Count -gt 0) {
  $failures | ForEach-Object { Write-Error $_ }
  exit 1
}
Write-Output "Windows, Python 3.12, PostgreSQL 127.0.0.1:5432, pg_dump, API paths, and migration tooling are available."
