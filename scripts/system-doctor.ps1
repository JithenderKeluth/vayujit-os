$ErrorActionPreference = "Continue"
$failed = $false
function Check-Command([string]$Name, [scriptblock]$Check) {
    try {
        & $Check | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "$Name exited with $LASTEXITCODE" }
        Write-Host "PASS $Name"
    } catch {
        Write-Host "FAIL $Name"
        $script:failed = $true
    }
}
Check-Command "Node" { node --version }
Check-Command "npm" { npm.cmd --version }
Check-Command "Python 3.12" { py -3.12 --version }
Check-Command "PostgreSQL" { docker exec infrastructure-postgres-1 pg_isready -U vayujit -d vayujit }
Check-Command "Migration" { & "$PSScriptRoot\maintenance.ps1" migration-status }
Check-Command "Angular build" { npm.cmd run build --workspace @vayujit/web }
Check-Command "Electron executable" { & "$PSScriptRoot\..\node_modules\.bin\electron.cmd" --version }
$backup = Resolve-Path (New-Item -ItemType Directory -Force -Path "$PSScriptRoot\..\var\backups")
if ($backup) { Write-Host "PASS Backup directory" } else { Write-Host "FAIL Backup directory"; $failed = $true }
if ($failed) { exit 1 }
