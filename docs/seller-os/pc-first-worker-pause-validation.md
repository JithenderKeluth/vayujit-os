# PC-first worker-stop failure: correction and focused validation

27 October 2026. **PC-FIRST DEPLOYMENT — IMPLEMENTED / CERTIFICATION PENDING.**

## Evidence and demonstrated root causes

The retained local `tmp/pc-first-certification/disposable-certification.json`
matches supplied backup `829102f460`: first failed stage `worker pause`, original
source line 511, PowerShell error, exit 1, missing child report, and last entered
stage `service recovery`. No raw subprocess streams were retained. The historical
Docker exit status and exact stderr text therefore remain unknown.

Two defects were reproduced in real Windows PowerShell 5.1 without Docker:

1. The former line 511 was:
   `& $docker.Source @composeArgs stop --timeout 45 worker 2>$null | Out-Null`.
   With `$ErrorActionPreference = "Stop"`, stderr can produce
   `NativeCommandError` **even when the native process exits zero** and stderr is
   redirected to null. A synthetic stderr-writing native child reproduces that
   exact behavior. The exception precedes `Assert-BackupNativeExit`, so no genuine
   native exit is available to the old failure handler. This is a demonstrated
   PowerShell invocation defect consistent with the runtime ledger, not evidence
   that Docker itself failed or timed out.
2. The catch handler used `$statusFailure = $failure.Clone()` before writing the
   expected child report. `New-VayujitBackupFailureReport` returns
   `System.Collections.Specialized.OrderedDictionary`, which has no `Clone`
   method. Calling it reproduces `MethodNotFound`. It replaces the original
   failure before report creation, although `finally` still attempts recovery.

The old recovery start calls had the same native-stderr pattern, so successful
Compose progress could also be misreported as failed recovery. No historical
worker/container state can be reconstructed from the supplied safe ledger alone.

## Service identity and bounded correction

The canonical service is `worker` in
[`docker-compose.pc.yml`](../../infrastructure/docker-compose.pc.yml:47), with
entrypoint `python -m vayujit_api.publishing.worker`, command `run`, a heartbeat
health check, and 45-second stop grace. The backup label "worker pause" means
**Compose stop**, not `docker pause`; recovery uses Compose start.

Changes:

- [`backup-pc-first.ps1`](../../scripts/backup-pc-first.ps1): capture lifecycle
  command stdout/stderr in memory through the existing native helper, inspect
  actual exit codes, and wrap failures using existing canonical stage exceptions.
  Preserve `stop --timeout 45 worker` and `stop --timeout 30 api` as exact argument
  arrays. Copy failure-report fields into a separate ordered dictionary rather
  than calling `Clone`.
- Worker preflight requires a single identified, running, unpaused, non-restarting,
  healthy worker. An already stopped/paused/unhealthy or missing worker fails
  before maintenance is enabled; backup does not silently start an operator-stopped
  worker. Malformed state and native inspection failures fail closed.
- After successful worker stop, inspect the same container and require explicit
  boolean `Running=false`, `Paused=false`, `Restarting=false`, and status `exited`.
  Exit zero alone cannot authorize database work. Failed quiescence prevents API
  pause, snapshot, dump, and encryption.
- [`pc-first-key-security.psm1`](../../scripts/pc-first-key-security.psm1:114):
  optional bounded native-process timeout. Default zero preserves existing callers;
  encryption/key-generation behavior is unchanged. Worker stop has a 90-second
  client deadline around the existing 45-second Compose grace. Timeout terminates
  only the owned client process and throws a fixed safe timeout exception. It
  never kills unrelated processes/containers or fabricates a Docker exit code.
- [`pc-first-backup-artifacts.psm1`](../../scripts/pc-first-backup-artifacts.psm1):
  allowlist `worker_pause_timeout` and `worker_not_quiescent`; preserve safe native
  exits when recovery callbacks throw. Existing report authority remains intact.

## Recovery and original-error preservation

Recovery flags remain armed before service stops. The original failure report is
written before `finally`. API recovery and worker start/health checks use captured
commands with explicit deadlines. Recovery callback failures keep their own safe
exit information; the original stop exit and stage remain authoritative in the
child report. Recovery failures are recorded independently in `cleanup_failure`.

Even when the API was not stopped, fresh API health is checked before clearing
owned maintenance. Maintenance is cleared only when API and worker health are
confirmed and no service stop timed out. Pre-existing maintenance is never cleared.
Maintenance responses must contain actual JSON booleans; missing or ambiguous
values cannot enable backup or report restoration success.

A Docker-client timeout does not prove the server-side stop was cancelled. Recovery
is attempted, but maintenance remains enabled even if a later health probe passes.
`maintenance_marker_preserved_because_service_stop_timed_out` explicitly records
that manual reconciliation is required. Unhealthy recovery similarly preserves
maintenance. Failed maintenance clearing remains visible and does not replace the
original backup failure.

Only the existing allowlisted stage names/codes, safe source lines, numeric exits
and cleanup codes are retained. No raw stdout/stderr, command argument values,
credentials, private identities or backup contents are persisted by diagnostics.

## Actual validation

Actual final results on Windows PowerShell **5.1.26100.9711**:

| Check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| New worker-pause/native/lifecycle suite | 25 | 0 | 0 |
| Artifact/report/recovery regressions, including two new callback-exception cases | 77 | 0 | 0 |
| Docker CLI regression checks (source/native probes, not Docker engine) | 13 | 0 | 0 |
| Child-process/report/redaction suite | 20 | 0 | 0 |
| Stage-ledger suite | 34 | 0 | 0 |
| Target-isolation guards | 4 | 0 | 0 |
| Key security/ACL/native checks | 10 | 0 | 1 |
| **Regression total** | **183** | **0** | **1** |

The skipped check is real age-keygen integration: the executable is unavailable
in this shell's PATH. Twelve PowerShell parser checks passed. `git diff --check`
passed with existing LF-to-CRLF notices. Process-scoped execution-policy bypass
was used for tests; machine/user execution-policy settings were not modified.

Safe generated evidence:

- `tmp/pc-first-certification/worker-pause-final-safe-timeout.json`: final 25 cases,
  per-scenario failures/events/maintenance status and allowlisted stage ledgers.
- `tmp/pc-first-certification/worker-fix-child-tests.json`: 20 child cases.
- `tmp/pc-first-certification/worker-fix-stage-tests.json`: 34 stage cases.

Test/documentation changes in addition to the three runtime files above:

- `scripts/test-pc-first-worker-pause.ps1` (new).
- `scripts/test-pc-first-backup-artifacts.ps1` (two new recovery-exception cases).
- `scripts/test-pc-first-docker-exec.ps1` (same lifecycle/flag assertions updated
  for captured argument-array calls rather than direct invocation).
- `docs/seller-os/pc-first-worker-pause-validation.md` (this report).
- `docs/seller-os/pc-first-backup-recovery.md` (focused correction/run guidance).

The new suite executes extracted production command, quiescence, catch, recovery
and finalization code with a fake Docker client. It uses real Windows PowerShell
native subprocesses, real exit codes and real bounded timeout probes. The fake
client emits stderr progress on lifecycle commands, validates stop arguments, and
persists deterministic synthetic service/maintenance state in its own temporary
directory. It never invokes Docker, a database or encryption.

The positive quiescence case intentionally ends at an artificial pre-database
failure boundary. It proves progression and recovery, **not** a successful backup.
Only the timeout scenario shortens the extracted call-site deadline to two seconds;
the production helper executes unchanged. Other scenarios retain 90 seconds.

Covered cases: success; stopped/paused/unhealthy/missing workers; native inspection
failure; malformed state; stop exit 37; stop exit zero with worker still running;
real client timeout; maintenance enabled before failure; healthy recovery; recovery
start exit 29 while original stop exit 37 survives; API stop exit 43; failed
maintenance clearing; pre-existing maintenance; failure-report creation; safe
stage retention and stream redaction.

Early test runs exposed test-adapter defects: direct inspection needed the fake
client's transport prefix, temporary cleanup events were incorrectly counted as
service mutations, and a universal one-second test deadline could spuriously time
out ordinary fake-client startup. These were corrected without weakening production
checks or assertions; per-scenario evidence and genuine native timeouts remain.
Earlier failed local evidence was not overwritten.

## Commands

From repository root in Windows PowerShell:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-worker-pause.ps1 -EvidencePath .\tmp\pc-first-certification\worker-pause-tests.json
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-backup-artifacts.ps1
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-docker-exec.ps1
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-backup-child.ps1
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-backup-stage-ledger.ps1
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-backup-guards.ps1
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-keygen.ps1
```

Next full owner-run disposable rehearsal, after focused tests pass:

```powershell
$backupDestination = Read-Host 'Approved backup destination folder'
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-disposable.ps1 -BackupDestination $backupDestination -EvidencePath .\tmp\pc-first-certification\disposable-certification.json
```

Share only safe certification/report artifacts, not raw subprocess streams or age
identity files. For a timeout/recovery warning, keep maintenance enabled until the
actual disposable project's stop/start completion and health have been reconciled.

## Remaining limitations

Docker was unavailable in this shell's PATH and at its usual installation path;
no actual Docker service operation, build or full backup rehearsal was performed.
The historical worker's actual Docker exit/status remains unrecorded. Real
`age-keygen` integration was unavailable in this shell; NTFS ACL/native regression
checks were executable. Physical destination independence remains UNVERIFIED.

No permanent database, production profile, encryption/restore semantics, marketplace,
unrelated Docker resources, branch, commit or push was changed. Encrypted backup,
independent restore and runtime recovery certification still require a successful
full disposable rehearsal.
