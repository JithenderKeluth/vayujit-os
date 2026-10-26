# PC-first encrypted backup and recovery

## Encryption tool

Use the maintained `age` project and its Windows package listing. Its official
installation instructions list `winget install --id FiloSottile.age` for
Windows ([upstream instructions](https://github.com/FiloSottile/age#installation)).
Installation is an owner-approved software change; do not download standalone
binaries from mirrors or execute unverified downloads.

```powershell
winget install --id FiloSottile.age --exact --source winget --accept-package-agreements --accept-source-agreements
Get-Command age, age-keygen
age --version
```

The private age identity is recovery material. Keep it in offline, access-
controlled custody separate from the application PC and backup destination;
test custody before relying on encrypted backups. Never put it in Git, a synced
folder, email, chat, or a screenshot.

## Backup design

- PostgreSQL custom-format dump and media archive/manifest are created from the
  active `vayujit-pc-business` Compose project for the permanent profile. The
  same implementation has a separate `-DisposableCertification` mode that
  accepts only the randomized, temporary, marker-protected certification
  project; that mode never targets the permanent profile or its volumes.
- The existing canonical application maintenance marker blocks new business
  writes; the worker is stopped gracefully and the API is stopped during the
  database/media snapshot. Both are restarted and maintenance is cleared in a
  cleanup path. The browser can briefly receive an unavailable response during
  a scheduled backup. An interrupted host may leave the persistent marker in
  place; check `maintenance-status` and service health before reopening edits.
- A short-lived plaintext work directory is used under
  `%LOCALAPPDATA%\VAYUJIT OS\backup-stage`, then removed in a `finally` block.
  Windows device encryption is required to protect that staging location.
- Each DB/media artifact and media manifest is encrypted with `age` to the
  public recipient. Ciphertext, SHA-256 sidecar, and last-run status are written
  to the configured backup destination. No cloud upload occurs. The runner
  probes writability and rejects paths inside the repository, profile, or a
  host-addressable PostgreSQL/media volume. It attempts to map the Docker
  volume backing storage to a Windows physical disk; if Docker Desktop's
  backing VHDX cannot be identified unambiguously, independence is `UNVERIFIED`
  and readiness remains pending.
- The script decrypts to temporary files, restores the database into a new
  PostgreSQL container on Docker's `none` network with a separately marked,
  randomly named temporary volume, checks the migration revision and
  `ck_users_single_owner`, and verifies media file checksums in an isolated
  temporary target. The helper removes only the container/volume it just
  created after validating their run marker. A test on this owner PC is still
  required before this is considered a witnessed restore.
- Default rotation is 90 days. Keep the private identity offline separately;
  never store the only identity alongside the encrypted backup.

## Enable a daily local task

After the profile has been activated, Docker Desktop and `age` are installed,
the separate backup disk is mounted, and a manual backup has been reviewed, the
owner may register a daily 02:00 local-time task:

```powershell
.\scripts\backup-pc-first.ps1
.\scripts\register-pc-backup-task.ps1 -At '02:00' -ConfirmRegistration
```

The task uses the current Windows user's interactive token and limited rights;
that user must be signed in and Docker Desktop running. It starts when a missed
run becomes available, does not start on battery, and ignores overlapping
runs. Task Scheduler history and
`<backup drive>\last-backup-status.json` are the local evidence. This profile
does not send alerts. If the PC is normally powered off or logged out at the
scheduled time, select another schedule or move to managed off-host backup.

Check the latest backup before OS upgrades, source updates, or other planned
maintenance:

```powershell
$BackupDriveLetter = (Read-Host 'Enter the configured backup drive letter').Trim().TrimEnd(':')
if ($BackupDriveLetter -notmatch '^[A-Za-z]$') { throw 'Enter one drive letter only.' }
$BackupRoot = Join-Path ("${BackupDriveLetter}:\") 'VAYUJIT-Encrypted-Backups'
Get-Content (Join-Path $BackupRoot 'last-backup-status.json')
Get-ChildItem (Join-Path $BackupRoot 'pc-backup-*.json') |
  Sort-Object LastWriteTime -Descending | Select-Object -First 5
```

The JSON sidecar contains backup IDs, artifact names, sizes, checksums, restore
status, and disk-independence evidence, not plaintext product/database records.

## Disposable encrypted backup/restore rehearsal

The normal disposable runtime runner can optionally exercise the complete
encrypted backup and independent restore path. It starts a fresh randomized
database, creates canonical owner/product/inventory/finance/media records
through application APIs, confirms audit lineage, writes encrypted artifacts
to the selected destination, rejects a wrong key and modified ciphertext,
restores PostgreSQL to a new `--network none` container/volume, restores media
to an empty temporary directory, compares canonical records and decimal
precision, and verifies the source records did not change. The age identity is
temporary, ACL-restricted, and removed with the disposable profile; it is not
saved with backup artifacts and must never be promoted to business key
material. It writes only into a newly created
`vayujit-disposable-cert-<random-id>` child folder and refuses to reuse that
folder, so it will not overwrite an existing backup status file or artifact.
The report records the generated artifact directory and ciphertext hashes.
After the runner removes its temporary profile, that rehearsal's recipient key
is intentionally gone; the retained ciphertext is certification evidence only,
not a recoverable business backup.

First set a destination path on a separately attached and encrypted physical
disk. Do not use a second folder/partition on the PostgreSQL/media disk. The
script records `SAME_PHYSICAL_DISK` or `UNVERIFIED` as a failed independence
gate; neither can qualify for real-data activation.

```powershell
$BackupDriveLetter = (Read-Host 'Enter the verified backup drive letter').Trim().TrimEnd(':')
if ($BackupDriveLetter -notmatch '^[A-Za-z]$') { throw 'Enter one drive letter only.' }
$backupDisk = Get-Partition -DriveLetter $BackupDriveLetter | Select-Object -First 1
if (-not $backupDisk) { throw 'The selected drive letter is not mounted.' }
$BackupCertificationRoot = Join-Path ("${BackupDriveLetter}:\") 'VAYUJIT-Disposable-Backup-Certification'
powershell.exe -NoProfile -File .\scripts\test-pc-first-disposable.ps1 `
  -EvidencePath .\docs\seller-os\artifacts\pc-first-backup-restore-rehearsal.json `
  -BackupDestination $BackupCertificationRoot
```

The rehearsal report is written to a separate artifact so this command does
not overwrite the existing runtime/browser certification evidence.

The disposable test generates the exact backup and restore commands internally
from the randomized project marker; do not manually point the restore helper
at a business profile or database. For a future activated installation, the
normal encrypted backup command is `.\scripts\backup-pc-first.ps1`; it uses
the protected installation marker's configured destination and refuses to run
unless physical separation is verified. Neither command initializes the
permanent business database.

## Incident response

1. Stop the application cleanly with
   `scripts/start-pc-first.ps1 -Command stop`; do not remove Docker volumes.
2. Preserve the current PC data volume and all backup files for forensic/retry
   purposes. Record the failure time and last known good backup ID.
3. Confirm the correct backup set has three ciphertext artifacts and its JSON
   sidecar; verify `age` can decrypt using the offline identity. Never email or
   upload the identity.
4. Restore only into a new, marker-protected disposable recovery database and
   empty media target first. Verify the schema revision, owner constraint,
   login, business/catalog data, and media checksums. This repository's
   generic disposable restore scripts are not authorized to target the
   permanent PC business database.
5. Compare recovery results and obtain HUMAN owner approval before any
   production restoration. For a real incident, obtain a reviewed
   environment-specific restore procedure before replacing the original data.
6. Preserve the failed originals until the recovered installation has been
   explicitly accepted. Record actual recovery time and lost-work window as
   RTO/RPO evidence.

## Current limitations

The encrypted backup/restore implementation now has a marker-protected
disposable mode, but the complete rehearsal has **not been executed or
certified** in the current shell. Docker, `age`, `age-keygen`, Python, Node,
and WinGet are unavailable here; WSL enumeration is denied. A read-only disk
inventory found one physical disk (`Micron_2450_MTFDKBK1T0TFK`, NVMe, disk 0)
and no second mounted drive letter, so an independent backup destination is
not currently available. Static validation passed for all seven PC PowerShell
scripts' ASTs, the disposable API JavaScript module syntax, persisted JSON
evidence, and `git diff --check`. The focused marker-guard script is present but
could not be invoked because this shell's PowerShell execution policy blocks
script files; no execution-policy override was used. Previous runtime PASS
evidence is not backup/restore evidence. Do not activate the permanent owner
database until the new rehearsal
reports `backup_restore.status = PASS` and
`destination_independence = VERIFIED_DIFFERENT_PHYSICAL_DISK`.

The temporary restore target is designed to be isolated from the business
database but shares the local Docker engine and host disk; it does not protect
against host or disk failure. A second drive in the same location is not
off-site disaster recovery. RPO/RTO remain unmeasured until a backup restore is
witnessed and timed on an independently approved recovery target.
