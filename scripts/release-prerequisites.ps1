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
$resolver = Join-Path $PSScriptRoot "resolve-pg-dump.ps1"
$postgresTools = @{}
foreach ($tool in @("pg_dump.exe", "pg_restore.exe", "psql.exe")) {
  $resolved = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $resolver -Tool $tool -Optional
  if ([string]::IsNullOrWhiteSpace("$resolved")) {
    $failures.Add("$tool is required. Install PostgreSQL 17 client tools or set VAYUJIT_PG_DUMP_PATH to a validated pg_dump.exe path.")
    continue
  }
  $toolVersion = (& $resolved --version 2>&1 | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $toolVersion -notmatch "PostgreSQL(?:\)|\s)+(\d+)") {
    $failures.Add("$tool did not return a valid PostgreSQL version.")
    continue
  }
  $postgresTools[$tool] = @{ Path = $resolved; Version = $toolVersion; Major = [int]$Matches[1] }
  if ($postgresTools[$tool].Major -ne 17) {
    $failures.Add("$tool major version $($postgresTools[$tool].Major) does not match the supported PostgreSQL 17 runtime.")
  }
}
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
Write-Output "Windows, Python 3.12, PostgreSQL 127.0.0.1:5432, pg_dump/pg_restore/psql PostgreSQL 17 tooling, API paths, and migration tooling are available."
