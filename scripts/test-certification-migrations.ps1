param([int]$Runs = 5)
$ErrorActionPreference = "Stop"
$container = "infrastructure-postgres-1"
$database = "vayujit_migration_certification_test"
$marker = "vayujit-os-disposable-test-database-v1"
$apiRoot = Resolve-Path (Join-Path $PSScriptRoot "..\apps\api")

function Invoke-Postgres([string]$Database, [string]$Sql) {
  docker exec $container psql -U vayujit -d $Database -v ON_ERROR_STOP=1 -tAc $Sql
  if ($LASTEXITCODE -ne 0) { throw "PostgreSQL command failed for $Database." }
}

function Confirm-Marker {
  $value = Invoke-Postgres "postgres" "SELECT 1 FROM pg_database WHERE datname='$database'"
  if ("$value".Trim() -ne "1") { return $false }
  $markerValue = Invoke-Postgres $database "SELECT project_identifier FROM test_database_marker WHERE marker_id=1"
  return "$markerValue".Trim() -eq $marker
}

function Stop-TestSessions {
  Invoke-Postgres "postgres" "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$database' AND pid<>pg_backend_pid();" | Out-Null
}

for ($run = 1; $run -le $Runs; $run++) {
  $exists = Invoke-Postgres "postgres" "SELECT 1 FROM pg_database WHERE datname='$database'"
  if ("$exists".Trim() -eq "1") {
    if (-not (Confirm-Marker)) { throw "Refusing unmarked migration test database: 127.0.0.1/$database" }
    Stop-TestSessions
    docker exec $container dropdb -U vayujit $database
    if ($LASTEXITCODE -ne 0) { throw "Could not drop disposable migration database." }
  }
  docker exec $container createdb -U vayujit $database
  if ($LASTEXITCODE -ne 0) { throw "Could not create disposable migration database." }
  Invoke-Postgres $database "CREATE TABLE test_database_marker (marker_id integer PRIMARY KEY, project_identifier text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), suite_token text NOT NULL); INSERT INTO test_database_marker(marker_id, project_identifier, suite_token) VALUES (1, '$marker', 'migration-certification');" | Out-Null
  $env:VAYUJIT_ENV = "test"
  $env:VAYUJIT_DATABASE_URL = "postgresql+psycopg://vayujit:vayujit_dev@127.0.0.1:5432/$database"
  Push-Location $apiRoot
  try {
    & ".\.venv\Scripts\alembic.exe" upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Migration run $run upgrade-head failed." }
    & ".\.venv\Scripts\alembic.exe" downgrade 20261021_0100
    if ($LASTEXITCODE -ne 0) { throw "Migration run $run focused downgrade failed." }
    & ".\.venv\Scripts\alembic.exe" upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Migration run $run re-upgrade failed." }
  } finally {
    Pop-Location
  }
  Stop-TestSessions
  if (-not (Confirm-Marker)) { throw "Migration marker disappeared after run $run." }
  docker exec $container dropdb -U vayujit $database
  if ($LASTEXITCODE -ne 0) { throw "Could not dispose migration database after run $run." }
  Write-Host "Migration fixture stability run $run/$Runs passed."
}