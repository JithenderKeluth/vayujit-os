param([Parameter(Mandatory=$true)][string]$Backup, [Parameter(Mandatory=$true)][string]$DatabaseUrl)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Backup)) { throw "Backup file was not found." }
if ([string]::IsNullOrWhiteSpace($DatabaseUrl) -or $DatabaseUrl -match "production|vayujit$") { throw "Restore requires an explicitly disposable target database." }
if (Get-Command pg_restore -ErrorAction SilentlyContinue) {
    & pg_restore --clean --if-exists --no-owner --no-privileges --dbname $DatabaseUrl $Backup
} else {
    $uri = [Uri]$DatabaseUrl.Replace("postgresql+psycopg", "postgresql")
    $user = $uri.UserInfo.Split(':')[0]
    $db = $uri.AbsolutePath.Trim('/')
    $containerFile = "/tmp/vayujit-restore-$([Guid]::NewGuid().ToString('N')).dump"
    & docker cp $Backup "infrastructure-postgres-1:$containerFile"
    & docker exec infrastructure-postgres-1 pg_restore --clean --if-exists --no-owner --no-privileges -U $user -d $db $containerFile
    & docker exec infrastructure-postgres-1 rm -f $containerFile
}
if ($LASTEXITCODE -ne 0) { throw "Disposable restore failed." }
Write-Output "Disposable restore completed. Run migrations and integrity checks before use."