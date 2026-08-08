param(
  [ValidateSet("pg_dump.exe", "pg_restore.exe", "psql.exe")]
  [string]$Tool = "pg_dump.exe",
  [switch]$Optional
)

$ErrorActionPreference = "Stop"

function Test-PgToolExecutable {
  param([string]$Path)
  if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
  if ([IO.Path]::GetFileName($Path) -ne $Tool) { return $false }
  $item = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
  return $null -ne $item -and -not $item.PSIsContainer
}

$candidates = [System.Collections.Generic.List[string]]::new()
if ($env:VAYUJIT_PG_DUMP_PATH) {
  if ($Tool -eq "pg_dump.exe") {
    $candidates.Add($env:VAYUJIT_PG_DUMP_PATH)
  } else {
    $configuredDirectory = Split-Path -Parent $env:VAYUJIT_PG_DUMP_PATH
    if ($configuredDirectory) { $candidates.Add((Join-Path $configuredDirectory $Tool)) }
  }
}
$pathCommand = Get-Command $Tool -ErrorAction SilentlyContinue
if ($pathCommand) { $candidates.Add($pathCommand.Path) }
foreach ($programFiles in @(${env:ProgramFiles}, ${env:ProgramFiles(x86)})) {
  if ($programFiles) {
    Get-ChildItem (Join-Path $programFiles "PostgreSQL") -Recurse -Filter $Tool -File -ErrorAction SilentlyContinue |
      Sort-Object FullName -Descending |
      ForEach-Object { $candidates.Add($_.FullName) }
  }
}

foreach ($candidate in $candidates | Select-Object -Unique) {
  if (Test-PgToolExecutable $candidate) {
    Write-Output (Resolve-Path -LiteralPath $candidate).Path
    exit 0
  }
}

if ($Optional) { exit 0 }
Write-Error "$Tool was not found. Install PostgreSQL 17 client tools or set VAYUJIT_PG_DUMP_PATH to a validated pg_dump.exe path."
exit 1