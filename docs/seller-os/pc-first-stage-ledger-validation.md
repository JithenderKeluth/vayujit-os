# Backup child stage-ledger validation

27 October 2026. **PC-FIRST DEPLOYMENT — IMPLEMENTED / CERTIFICATION PENDING.**

## Finding and bounded correction

The supplied `6ad8b30d36` evidence proves that the child started and exited 1
without its expected report. It does not identify the failing operation. No
retained local evidence for that ID was found in the inspected documentation and
temporary evidence directories. Its actual exception remains **unknown**.

The previous start marker and stderr classifier could not distinguish ordinary
exceptions lacking a recognized signature. The child now emits fixed stage
checkpoints before and after operations; the existing parent diagnostic retains
their allowlisted projection. This changes observability, not backup semantics.

Changed executable files:

- `scripts/backup-pc-first.ps1`: dependency-free disposable checkpoint emitter,
  caught-error checkpoints, startup/runtime/report/recovery/finalization coverage.
- `scripts/pc-first-backup-bootstrap.ps1`: report-write checkpoints.
- `scripts/pc-first-backup-artifacts.psm1`: parse/revalidate the ledger within the
  existing child diagnostic; reuse the canonical runtime operation allowlist.
- `scripts/test-pc-first-disposable.ps1`: supply the exact expected report path to
  diagnostics before cleanup and include the ledger in the certification report.
- `scripts/test-pc-first-backup-stage-ledger.ps1`: focused non-Docker regressions.

No key-security, encryption, restore, marker, destination-independence or recovery
policy was relaxed. There is no new competing backup report authority.

## Checkpoint contract

The 23 fixed startup/support stages are:

1. bootstrap load
2. report boundary initialization
3. key security module import
4. backup artifact module import
5. profile path resolution
6. profile files check
7. disposable argument validation
8. profile configuration
9. recipient validation
10. identity ACL verification
11. age dependency check
12. age keygen dependency check
13. Docker dependency check
14. staging directory creation
15. destination write probe
16. PostgreSQL storage evidence
17. media storage evidence
18. destination independence check
19. runtime initialization
20. runtime staging creation
21. child report write
22. service recovery
23. backup finalization

Runtime operations such as database encryption/verification use the existing
`SafeBackupOperations` authority. A normal stage transition completes the previous
operation. COMPLETE means control returned/advanced normally, **not** independent
proof of backup correctness, healthy recovery, or verified physical independence.
Existing authoritative checks and reports still determine those outcomes.

`stage_ledger` records last entered/completed stage, first failed stage, fixed
failure class, allowlisted source basename/bounded line, process exit code,
expected-report presence and checkpoint count. The first explicit failure remains
recorded even if report-writing or recovery checkpoints follow it.

`expected_report_written` is an observed file-presence boolean after child exit;
it does not certify JSON schema, report completeness or backup integrity. The
existing child-report resolver separately validates those contracts.

Caught terminating errors and errors promoted by `Stop` use `powershell_error`;
existing native-exit lineage uses `native_failure`. Report-write exceptions use
`report_write_failed`. An abrupt exit with no caught checkpoint retains the last
stage and uses `unhandled_process_exit`. This is an inference, not proof that a
particular explicit `exit` statement caused the historical failure. Parse/binding
failures before script execution remain handled by the existing parent classifier.

Only fixed checkpoint tokens are emitted. Raw stdout/stderr are captured in
memory, projected to allowlisted fields, and never persisted. No command arguments,
paths, credentials, database URLs, private keys or customer data enter the ledger.
Unknown stage names and extra nested fields are discarded. Source location is a
known script/module basename and line only, or `unavailable`.

The parent retains the ledger in its existing failure artifact:
`tmp/pc-first-certification/backup-child-<id>.json`, outside disposable cleanup,
and in `backup_child_diagnostic.stage_ledger` of the certification JSON. Existing
safe stdout fallback remains if the parent itself cannot write evidence. Disk
failure or process termination before the parent can persist is not guaranteed
durability and must not be described as successful diagnostic retention.

## Actual execution evidence

Tests executed in Windows PowerShell **5.1.26100.9711**, using process-scoped
`-ExecutionPolicy Bypass`; no persistent execution-policy setting changed.

| Check | Passed | Failed | Skipped | Actual scope |
| --- | ---: | ---: | ---: | --- |
| New stage-ledger suite | 34 | 0 | 0 | Real PS child processes, extracted production checkpoint helpers, synthetic fault injections, real guarded entry-point preflight |
| Existing child-process suite | 20 | 0 | 0 | Startup, parse/binding/import/dependency/report failures, exit handling, redaction and retention |
| Existing artifact/report suite | 75 | 0 | 0 | Report propagation, integrity guards, native probes, recovery mocks |
| Existing target guards | 4 | 0 | 0 | Marked disposable/permanent boundary guards, no database |
| Existing Docker CLI regressions | 13 | 0 | 0 | AST/source/native mocks, not Docker engine execution |
| **Regression total** | **146** | **0** | **0** | Not backup/restore certification |
| PowerShell parser checks | 10 | 0 | 0 | Four changed runtime files, new test, reviewed key-security module and four existing regression scripts |

The new 34 cases include one injected terminating error for each of the 23 stage
names, a promoted nonterminating error, explicit exits 31 and 0, a real native
exit 23, report-write failure, runtime allowlist reuse, rejected/spoofed stage
names, a real missing-config preflight, canonical report preservation, nested-field
redaction and retention after deletion of the test's own disposable profile.
Injected protocol tests do not imply the underlying encryption/storage operations
ran. The actual entry-point preflight failed before Docker and produced its normal
structured preflight report.

Generated local evidence:

- `tmp/pc-first-certification/stage-ledger-focused.json` (34 cases, safe examples).
- `tmp/pc-first-certification/child-diagnostic-with-stage-ledger.json` (20 cases).

No Docker certification, actual backup/restore, permanent database operation,
marketplace access, unrelated cleanup, branch, commit or push occurred.

## Reproduction commands

From repository root in Windows PowerShell:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-backup-stage-ledger.ps1 -EvidencePath .\tmp\pc-first-certification\stage-ledger-tests.json
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-backup-child.ps1
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-backup-artifacts.ps1
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-backup-guards.ps1
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-docker-exec.ps1
```

Only after those focused tests pass, the next owner-run full rehearsal is:

```powershell
$backupDestination = Read-Host 'Approved backup destination folder'
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-disposable.ps1 -BackupDestination $backupDestination -EvidencePath .\tmp\pc-first-certification\disposable-certification.json
```

If it fails again after starting, share only the certification JSON and retained
`backup-child-<id>.json`. The nested ledger will distinguish import, configuration,
key ACL, dependency, destination/storage, runtime, report-write and recovery stages.
A caught error should supply its safe source line; an abrupt exit supplies the
last observed checkpoint. Do not attach identity files or raw process streams.

## Remaining blockers

The historical exit-1 operation is not established. A new full rehearsal with the
checkpoints has not run. Encrypted backup, independent restore, wrong-key and
corruption rejection, source integrity, service recovery in the actual stack,
and physical destination independence remain subject to successful runtime
evidence. No backup/restore certification PASS is claimed.
