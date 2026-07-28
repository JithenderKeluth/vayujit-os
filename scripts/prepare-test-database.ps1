param(
    [ValidateSet("integration", "migration")]
    [string]$Purpose = "integration"
)
$ErrorActionPreference = "Stop"
$database = if ($Purpose -eq "migration") { "vayujit_migration_test" } else { "vayujit_test" }
$container = "infrastructure-postgres-1"

$exists = docker exec $container psql -U vayujit -d postgres -tAc `
    "SELECT 1 FROM pg_database WHERE datname='$database'"
if ("$exists".Trim() -ne "1") {
    docker exec $container createdb -U vayujit $database
    docker exec $container psql -U vayujit -d $database -v ON_ERROR_STOP=1 -c `
        "CREATE TABLE test_database_marker (marker_id integer PRIMARY KEY, project_identifier text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), suite_token text NOT NULL); INSERT INTO test_database_marker(marker_id, project_identifier, suite_token) VALUES (1, 'vayujit-os-disposable-test-database-v1', '$Purpose-local');" |
        Out-Null
} else {
    $hasMarker = docker exec $container psql -U vayujit -d $database -tAc `
        "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='test_database_marker'"
    if ("$hasMarker".Trim() -ne "1") {
        throw "Refusing existing unmarked database: 127.0.0.1/$database"
    }
    $marker = docker exec $container psql -U vayujit -d $database -tAc `
        "SELECT project_identifier FROM test_database_marker WHERE marker_id=1"
    if ($LASTEXITCODE -ne 0 -or "$marker".Trim() -ne "vayujit-os-disposable-test-database-v1") {
        throw "Refusing existing unmarked database: 127.0.0.1/$database"
    }
}
Write-Host "Test database confirmed: 127.0.0.1/$database"
