$ErrorActionPreference = "Stop"
$container = "infrastructure-postgres-1"
$database = "vayujit_migration_test"
$marker = "vayujit-os-disposable-test-database-v1"
$apiRoot = Resolve-Path (Join-Path $PSScriptRoot "..\apps\api")

function Test-Marker {
    $hasMarker = docker exec $container psql -U vayujit -d $database -tAc `
        "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='test_database_marker'"
    if ("$hasMarker".Trim() -ne "1") { return $false }
    $value = docker exec $container psql -U vayujit -d $database -tAc `
        "SELECT project_identifier FROM test_database_marker WHERE marker_id=1"
    return $LASTEXITCODE -eq 0 -and "$value".Trim() -eq $marker
}

$exists = docker exec $container psql -U vayujit -d postgres -tAc `
    "SELECT 1 FROM pg_database WHERE datname='$database'"
if ("$exists".Trim() -eq "1") {
    if (-not (Test-Marker)) {
        throw "Refusing migration cleanup: marker missing or invalid at 127.0.0.1/$database"
    }
    docker exec $container dropdb -U vayujit $database
}
docker exec $container createdb -U vayujit $database
docker exec $container psql -U vayujit -d $database -v ON_ERROR_STOP=1 -c `
    "CREATE TABLE test_database_marker (marker_id integer PRIMARY KEY, project_identifier text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), suite_token text NOT NULL); INSERT INTO test_database_marker VALUES (1, '$marker', now(), 'migration-local');" |
    Out-Null
Write-Host "Test database confirmed: 127.0.0.1/$database"

$env:VAYUJIT_ENV = "test"
$env:VAYUJIT_DATABASE_URL = "postgresql+psycopg://vayujit:vayujit_dev@127.0.0.1:5432/$database"
Push-Location $apiRoot
try {
    & ".\.venv\Scripts\alembic.exe" upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Clean migration upgrade failed." }
    & ".\.venv\Scripts\alembic.exe" downgrade 20260729_0009
    if ($LASTEXITCODE -ne 0) { throw "Migration downgrade failed." }
    & ".\.venv\Scripts\alembic.exe" upgrade 20260730_0010
    if ($LASTEXITCODE -ne 0) { throw "Migration re-upgrade failed." }
} finally {
    Pop-Location
}
if (-not (Test-Marker)) {
    throw "Refusing migration cleanup: marker disappeared at 127.0.0.1/$database"
}
docker exec $container dropdb -U vayujit $database
Write-Host "Migration cycle passed; disposable database removed."
