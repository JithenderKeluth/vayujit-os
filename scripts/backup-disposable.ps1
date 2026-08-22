param([string]$DatabaseUrl = $env:VAYUJIT_TEST_DATABASE_URL, [string]$Destination = "var/backups")
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { throw "A disposable PostgreSQL URL is required." }
$uri = [Uri]$DatabaseUrl.Replace("postgresql+psycopg", "postgresql")
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$output = Join-Path (Resolve-Path $Destination) "disposable-$stamp.dump"
$user = $uri.UserInfo.Split(':')[0]
$db = $uri.AbsolutePath.Trim('/')
$env:PGPASSWORD = [Uri]::UnescapeDataString($uri.UserInfo.Split(':')[-1])
if (Get-Command pg_dump -ErrorAction SilentlyContinue) {
    & pg_dump -Fc --no-owner --no-privileges -h $uri.Host -p $uri.Port -U $user -d $db -f $output
}
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $output)) {
    $containerFile = "/tmp/vayujit-disposable-$stamp.dump"
    & docker exec infrastructure-postgres-1 sh -c "pg_dump -Fc --no-owner --no-privileges -U $user -d $db > $containerFile"
    & docker cp "infrastructure-postgres-1:$containerFile" $output
    & docker exec infrastructure-postgres-1 rm -f $containerFile
}
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $output) -or (Get-Item $output).Length -eq 0) { throw "Disposable backup failed." }
Write-Output $output