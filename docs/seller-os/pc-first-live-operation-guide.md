# PC-first VAYUJIT live-operation guide

Status: prepared for HUMAN activation; no permanent business database was
started by this implementation. The profile is one VAYUJIT seller, one
Windows PC installation, one PostgreSQL database, and one local owner. It is
not a hosted service, multi-tenant deployment, or public internet endpoint.

## Before first activation

- Windows 11 (or a supported Windows 10 installation), WSL 2, and Docker
  Desktop with the Linux container engine are installed and healthy.
- The source checkout is in a stable local folder. Keep it separate from the
  Docker-managed PostgreSQL/media volumes and do not place the checkout under
  a synced/shared folder.
- Windows device encryption/BitLocker is enabled for the OS/data disk.
- A second physical drive is attached, encrypted, and has enough free space for
  the expected database plus media, at least one full backup set, and retention.
- `age` and `age-keygen` are installed from an approved distribution and are
  available in the PowerShell `PATH`.
- The owner has reviewed the security, backup, and approval checklists below.
- No existing development/test database is copied or reused. First-run
  onboarding records the real owner and business; it does not seed demo data.

Docker Compose image builds require access to the configured image/package
registries. Runtime containers share an internal Docker network with internet
egress disabled. This profile intentionally does not perform live provider,
supplier, or marketplace calls.

## Prepare and activate

Open PowerShell in the repository root and set the actual, verified drive letter
for the owner's encrypted second physical disk. A second folder/partition on
the PostgreSQL/media disk is not independent:

```powershell
$BackupDriveLetter = (Read-Host 'Enter the verified backup drive letter').Trim().TrimEnd(':')
if ($BackupDriveLetter -notmatch '^[A-Za-z]$') { throw 'Enter one drive letter only.' }
$BackupRoot = Join-Path ("${BackupDriveLetter}:\") 'VAYUJIT-Encrypted-Backups'
.\scripts\initialize-pc-first.ps1 -BackupRoot $BackupRoot
```

Run with the machine's approved PowerShell policy. If Windows blocks the
script, stop and obtain HUMAN/administrator approval for an approved signing
or execution method; do not lower the machine policy or use a bypass override.

The initializer proves the selected path maps to a different physical disk,
creates a unique `age` identity and secrets with Windows ACLs, writes them
outside the repository under `%LOCALAPPDATA%\VAYUJIT OS\config`, and leaves the
database stopped. Copy the private `backup.agekey` to a separately secured,
offline recovery location. It cannot be recovered from the public recipient;
losing it makes encrypted backups unreadable. Never put it in Git or send it
to VAYUJIT support.

Review `config\pc-install.json`, `config\app.env`, and `config\compose.env`
locally without copying secrets into chat, screenshots, or tickets. Then run:

```powershell
.\scripts\start-pc-first.ps1 -Command start
```

On the first activation only, the script describes the persistent database and
requires typing `START VAYUJIT BUSINESS DATABASE`. This is the explicit HUMAN
activation point. Compose validates configuration, starts PostgreSQL, applies
the checked-in Alembic migrations via the API image entrypoint, and then starts
the worker/web/reverse proxy. No database fixtures are loaded. Readiness is
checked before the local URL is reported.

Open `http://127.0.0.1:8443` on this PC. The listener is bound to loopback;
other computers cannot use it. Complete the application’s first-owner setup
with a unique password and genuine VAYUJIT business information. Do not reuse
the development/test password. Local HTTP is not suitable for a public or
shared network.

## Current certification status (2026-10-15)

The disposable PC profile passed its production-image runtime checks in Docker
Desktop 29.6.2: 17/17 deployment, persistence, and security checks and 25/25
authenticated Chrome assertions passed. Chrome 155 scanned sign-in, dashboard,
product list, product details, product editor, and catalog detail: zero axe
violations. One serious color-contrast check remained `incomplete` for two
textareas because axe detected partial occlusion and could not calculate their
background. The five requested dashboard viewport widths (360, 390, 768,
1024, 1440 CSS pixels) had no horizontal overflow. There were no browser
console errors or third-party resource origins. Evidence is in
[`pc-first-disposable-certification.json`](pc-first-disposable-certification.json)
and the `artifacts/pc-first-*-disposable.png` screenshots.

The test owner, product, cost, stock, and image existed only in a uniquely
named disposable PostgreSQL project, survived a full Compose stop/start, and
were removed with the test volumes afterward. This did not start or write the
permanent owner database. Focused tests: 21 PC-local Python tests passed;
Angular: 227 tests across 64 files passed. The production Angular image built;
its existing initial bundle warning is 514.48 kB against a 500 kB budget
(14.48 kB over). Web lint has no errors and two pre-existing lifecycle warnings.

The disposable encrypted-backup/restore mode is now implemented in the
randomized certification runner, but was not executable in this shell: Docker,
Docker, `age`, `age-keygen`, and `winget` are not available through PATH. WSL
enumeration reports access denied. A read-only physical-disk inventory found
one NVMe disk (disk 0) and no second mounted drive letter. The backup mode must
be run on the owner's PC with the approved tools and a separately attached
physical destination. Until its
report shows an encrypted backup, wrong-key and corruption rejection,
canonical-row/financial-precision comparison, media restore, unchanged source,
and `VERIFIED_DIFFERENT_PHYSICAL_DISK`, do not activate the permanent profile.
The Docker engine/Windows-reboot restart gate is also not witnessed.

Install age only from its official Windows package source. The age project
lists this Windows command in its official [installation instructions](https://github.com/FiloSottile/age#installation):

```powershell
winget install --id FiloSottile.age --exact --source winget --accept-package-agreements --accept-source-agreements
```

Installation is a HUMAN action; this implementation does not install
software. Start a new PowerShell window, verify the binaries and create a
temporary test identity without displaying the private key:

```powershell
Get-Command age, age-keygen
age --version
$ageProbe = Join-Path $env:TEMP ('vayujit-age-check-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $ageProbe | Out-Null
$ageProbeKey = Join-Path $ageProbe 'probe.agekey'
age-keygen -o $ageProbeKey 2>&1 | Out-Null
$ageProbeRecipient = (age-keygen -y $ageProbeKey | Select-Object -Last 1).ToString().Trim()
if ($LASTEXITCODE -ne 0 -or $ageProbeRecipient -notmatch '^age1[0-9a-z]+$') { throw 'age verification failed' }
Remove-Item -LiteralPath $ageProbe -Recurse -Force
```

Attach and unlock a separate encrypted physical drive, then verify the
destination and source disk mapping where Windows permits it:

```powershell
Get-Command age, age-keygen
Get-Volume | Select-Object DriveLetter, FileSystemLabel, Size, HealthStatus
Get-Disk | Select-Object Number, FriendlyName, BusType, Size, OperationalStatus
$BackupDriveLetter = (Read-Host 'Enter the verified backup drive letter').Trim().TrimEnd(':')
if ($BackupDriveLetter -notmatch '^[A-Za-z]$') { throw 'Enter one drive letter only.' }
Get-Partition -DriveLetter $BackupDriveLetter | Select-Object DriveLetter, DiskNumber, Type, Size
```

Use the verified destination drive chosen above. This one
command creates a fresh randomized disposable database, canonical owner,
product, stock, financial, media, and audit fixtures, performs runtime/browser
checks, encrypts a backup, tests wrong-key and corrupted-ciphertext rejection,
restores into a separately marked no-network PostgreSQL container, validates
media in a separate temporary target, compares source/restored canonical rows
including INR decimal precision, checks source rows stayed unchanged, and
records timings and disk-independence status:

```powershell
$BackupCertificationRoot = Join-Path ("${BackupDriveLetter}:\") 'VAYUJIT-Disposable-Backup-Certification'
powershell.exe -NoProfile -File .\scripts\test-pc-first-disposable.ps1 `
  -EvidencePath .\docs\seller-os\artifacts\pc-first-backup-restore-rehearsal.json `
  -BackupDestination $BackupCertificationRoot
```

This writes a separate rehearsal artifact and preserves the existing
runtime/browser certification report.

The report may say `PASS` for disposable runtime tests while classification
remains pending: real-data readiness requires
`backup_restore.status = PASS` **and**
`destination_independence = VERIFIED_DIFFERENT_PHYSICAL_DISK`. `SAME_PHYSICAL_DISK`
or `UNVERIFIED` is not independent protection. Never initialize permanent
data using the disposable project or copy its data. After the full report passes,
use the already verified physical drive and prepare the permanent profile:

```powershell
$BackupRoot = Join-Path ("${BackupDriveLetter}:\") 'VAYUJIT-Encrypted-Backups'
powershell.exe -NoProfile -File .\scripts\initialize-pc-first.ps1 -BackupRoot $BackupRoot
```

Only then, after reviewing the profile and explicitly approving persistent
database creation, use `scripts/start-pc-first.ps1 -Command start`, type the
exact confirmation phrase, and create the real owner account. The intended
local URL after a successful start is `http://127.0.0.1:8443`; it is not
currently active.

## Daily encrypted backup command and scheduling approval

After a future HUMAN-approved activation, use the same destination selection
and validation above; the exact manual backup command is:

```powershell
$BackupRoot = (Get-Content (Join-Path $env:LOCALAPPDATA 'VAYUJIT OS\config\pc-install.json') -Raw | ConvertFrom-Json).backup_root
.\scripts\backup-pc-first.ps1
Get-Content (Join-Path $BackupRoot 'last-backup-status.json')
```

`$BackupRoot` must be the configured path saved during initialization. The
script refuses same-disk or unverified destinations, checks writability,
records secret-free backup status, and rotates completed sets using the
configured retention period. Keep `backup.agekey` separately secured offline;
never store it in the backup destination, repository, synced folder, or chat.

Daily Task Scheduler registration is prepared but not automatic. It requires
separate HUMAN approval after a successful manual backup and restore rehearsal:

```powershell
.\scripts\register-pc-backup-task.ps1 -At '02:00' -ConfirmRegistration
```

Do not run that command until the owner has approved the schedule, missed-run
behavior, interactive sign-in requirement, retention period, and recovery-key
custody.

## Daily use

```powershell
.\scripts\start-pc-first.ps1 -Command status
.\scripts\start-pc-first.ps1 -Command open
.\scripts\start-pc-first.ps1 -Command stop
.\scripts\start-pc-first.ps1 -Command start
```

`stop` preserves the named PostgreSQL and media volumes. Do not run `docker
compose down -v`, `docker volume prune`, or remove `vayujit_pc_business_*`.
Those operations can irreversibly delete the only business data copy. On
startup, inspect the Docker Desktop health state and `status` output; if
readiness fails, inspect service logs with the exact Compose project/file/env
arguments used by the start script. Never troubleshoot by switching the PC
profile to the development database URL.

Normal starts reuse the existing application image. Updating source code and
rebuilding is a separate guarded operation: make a verified encrypted backup
first, then run `scripts/start-pc-first.ps1 -Command start -Rebuild`. A
successful backup from the previous 24 hours is required before the script
will rebuild an already activated installation, because the API image applies
Alembic migrations at startup. Do not manually run an unreviewed migration
against the business database.

For a clean shutdown before Windows updates, use `stop`. Configure Docker
Desktop to start with Windows only if the owner wants automatic service
availability; this setting is not changed by these scripts. Secure the Windows
login and use screen lock. Do not expose port 8443 through router forwarding,
Windows Firewall, a tunnel, or a reverse proxy.

## Data entry and trust

Enter real legal business details, products, variants/SKUs, stock, acquisition
costs, product images, and documented supplier evidence through the normal
authenticated application workflows. Preserve source, currency, observation
date, and HUMAN verification where the UI supports them. Unknown values remain
unknown; do not use zero, demo inventory, test marketplace accounts, fake
orders, or synthetic settlement events to fill them. External writes remain
disabled. Use the canonical readiness and HUMAN decision screens before any
later, separately authorized action.

The local setup does not require or support an `ownerExists` environment
variable. The first-owner setup status is read from the dedicated database;
after the real owner is created, the existing canonical constraint prevents a
second owner.

The Windows profile is for private use on one PC. It is not certified for
multiple Windows accounts, remote browsers, public TLS, live provider research,
or live marketplace connectivity. Move to the HTTPS VPS runbook before access
from another device or person.
