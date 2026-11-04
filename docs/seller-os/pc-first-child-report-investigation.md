# Missing child report — investigation and diagnostic validation

27 October 2026. **PC-FIRST DEPLOYMENT — IMPLEMENTED / CERTIFICATION PENDING.**
Diagnostic correction is implemented; full encrypted backup/restore is not certified.

## Root cause: proven diagnostic loss, unknown original exception

The supplied `vayujit-pc-cert-1ad701bbca` evidence establishes exit 1 and a missing
child report, not its triggering exception. No retained stderr/report for that ID
was found in the repository's relevant local JSON/log evidence. Do not attribute
the original exit to age, Docker, quoting, policy or encoding without evidence.

The code demonstrably hid the reason:

- At the [parent capture handoff](../../scripts/test-pc-first-disposable.ps1:219),
  the old parent consumed only a fixed stdout bootstrap token, then discarded
  captured stderr with the process object. Missing report/token therefore became
  the generic `backup_subprocess_nonzero_exit`.
- [Disposable cleanup](../../scripts/test-pc-first-disposable.ps1:370) then deleted
  the profile, including any child report. The parent already read before cleanup;
  the issue was failure to preserve a useful diagnostic outside that profile.
- Bootstrap runs **inside** the child script. Missing script, parse errors,
  argument binding and execution-policy rejection may occur before its first
  statement. No in-script reporter can handle a script that never starts.
- The initializer call itself was outside its protective catch. That separate
  early gap is now [guarded](../../scripts/backup-pc-first.ps1:19), with a safe token
  if initialization fails.

The exact historical `1ad701bbca` exception remains **unestablished**. New tests
reproduce exit-1/no-report using real PowerShell parse/binding failures and verify
the diagnostic fallback. A real repository-entry-point probe writes its expected
preflight report when a marked synthetic profile lacks its Compose configuration,
without proceeding to Docker. This is not backup success.

## Invocation trace and bounded correction

The parent selects `(Get-Process -Id $PID).Path`, with its existing
`powershell.exe`/`pwsh.exe` fallback. Actual tests used
`C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`, **5.1.26100.9711**.
PowerShell 7 was not tested.

Arguments remain `-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File`
followed by the existing backup script and named disposable DataRoot, destination
and report parameters. Their values are never logged. The
[native helper](../../scripts/pc-first-key-security.psm1:114) still uses Windows
argv quoting, `UseShellExecute=false`, redirected streams, concurrent reads and the
actual process exit. Optional `WorkingDirectory` now pins this caller to repository
root; other callers retain their old behavior. Existing synthetic credential/context
environment exclusions remain; no environment/secret snapshot is persisted.

Both processes still agree on the absolute marked-profile `backup-rehearsal.json`
path. Marker, reparse-point, boundary and no-overwrite guards are unchanged.
Valid structured child failures remain authoritative for stage/native/Docker/
recovery information; the new diagnostic does not replace them.

The child emits only `VAYUJIT_BACKUP_CHILD_STARTED=1` after binding and before
bootstrap/imports. Missing token means **startup not observed**, not a proven cause.
The [parent diagnostic classifier](../../scripts/pc-first-backup-artifacts.psm1:477)
retains fixed classifications, allowlisted PowerShell IDs and bounded parser line
numbers. Its read-only parser check never executes the child. Invalid/inaccessible
diagnostic paths cannot erase an already-observed exit.

Classes cover executable/script missing, launch, parse, binding, policy, module/
dependency, report-writing, initialization/preflight, zero exit with warnings, and
unclassified nonzero exit. Unknown/localized signatures are not guessed.

This is **positive allowlisting**, not regex-based promises to redact arbitrary
secrets. Raw stderr/stdout, arguments, paths, passwords, database URLs, tokens,
customer content and private keys are entirely omitted. Diagnostic engine/location
values are fixed contract labels, not raw filesystem evidence. The diagnostic is
not trusted backup certification or authorization.

On backup failure, [parent persistence](../../scripts/test-pc-first-disposable.ps1:324)
retains the safe object in the certification JSON and at
**`tmp/pc-first-certification/backup-child-<id>.json`**, outside cleanup even if
`-EvidencePath` was omitted. The writer revalidates fields and refuses overwrite.
If the parent cannot write even that file, it marks persistence FAILED and emits
only `VAYUJIT_BACKUP_PARENT_DIAGNOSTIC={safe JSON}` on stdout. It does not erase the
original backup failure or claim successful recovery.

Example from a real synthetic parse-failure child:

```json
{
  "classification": "script_parse_failed",
  "process_exit_code": 1,
  "source_line": 1,
  "script_started_token_observed": false,
  "stderr_captured": true,
  "raw_output_persisted": false,
  "diagnostic_is_not_backup_certification": true
}
```

Full safe examples/results: [validation JSON](pc-first-child-report-validation.json).

## Actual verification

| Check | Actual result | Scope |
| --- | --- | --- |
| New child-startup/report tests | **20 passed, 0 failed/skipped** | Real Windows PS 5.1 child processes; all ten requested failure/propagation/redaction categories plus policy, Unicode/argv, initializer and retention checks |
| Existing artifact/report/bootstrap/recovery suite | **75 passed** | Native probes and recovery mocks, no Docker engine |
| Existing target guards | **4 passed** | Fail before runtime/database access |
| Existing Docker exec suite | **13 passed** | AST/source/native probes, not Docker certification |
| Existing private-key security | **10 passed, 1 skipped** | ACL, stderr/exit and path checks; real age-keygen unavailable in this shell's PATH |
| PowerShell 5.1 parser | **6 files passed** | Five touched scripts/modules plus reviewed bootstrap |
| Git whitespace | PASS | Existing CRLF-conversion notices only |
| Actual encrypted backup/independent restore | **NOT EXECUTED** | No certification PASS inferred |

Both backup/bootstrap source files parse in PS 5.1 and contain ASCII source; no
PowerShell 7 syntax or demonstrated source-encoding failure was found. Unicode
script filename/argument, spaces, trailing backslash and explicit working directory
were actually tested. Unicode equality is checked inside the child to avoid
conflating PS 5.1 console-code-page transcoding with argument loss. No encryption
utility encoding or key permissions were weakened.

Initial new-test failures are retained under ignored `tmp/pc-first-certification`:
one assertion confused allowed `safe_stderr_summary` with a forbidden raw `StdErr`
property; a Unicode round-trip oracle also included console transcoding. Corrected
assertions still reject the raw property and verify actual argv in the child.
The failed attempts are not relabelled passes.

The initial no-override test command was denied by this shell's execution policy.
Tests then used process-scoped Bypass, matching the existing child convention.
No persistent Windows policy was changed. A Restricted child additionally proves
policy rejection is diagnosed. This does not establish that policy caused the
owner's original failure, whose parent already specified Bypass. Do not defeat
organizational policy if it forbids execution.

## Exact next commands

From repository root, run the non-Docker startup probe first:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test-pc-first-backup-child.ps1 -EvidencePath .\tmp\pc-first-certification\child-startup-tests.json
```

Only after it passes, approved age tools/Docker and a writable approved destination
are available, run the separate **disposable** rehearsal:

```powershell
$backupDestination = Read-Host 'Approved backup destination folder (prefer a different physical disk)'
.\scripts\test-pc-first-disposable.ps1 -BackupDestination $backupDestination -EvidencePath .\tmp\pc-first-certification\disposable-certification.json
```

If reviewed process-scoped execution is required, invoke that script using the
same explicit `powershell.exe ... -ExecutionPolicy Bypass -File` convention; do not
change persistent policy. Share only sanitized certification JSON and the referenced
`backup-child-*.json`, never raw streams, credentials or age identities.

## Remaining blockers and files

The historical exit's specific cause still needs the new retained diagnostic if
it reproduces. Full encrypted DB/media backup, wrong-key/corrupt-ciphertext rejection,
independent restore, Decimal/media comparison, source integrity and service recovery
have not been executed here. Destination independence is still **UNVERIFIED**.
Real age-keygen integration is unexecuted in this shell. Do not initialize the
permanent database or upgrade the PC-first classification.

Changed files: `backup-pc-first.ps1`, `pc-first-key-security.psm1`,
`pc-first-backup-artifacts.psm1`, `test-pc-first-disposable.ps1`, new
`test-pc-first-backup-child.ps1`, this report/validation JSON and a backup-guide
addendum. Bootstrap was reviewed, not replaced. No backup semantics, encryption,
restore/isolation/physical-independence gates, permanent/golden data, unrelated Docker
resources, marketplace settings, branch, commit or push were changed.
