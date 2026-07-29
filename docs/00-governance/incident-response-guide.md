# Incident response guide

## Triage

1. Record the time, release identifier, affected owner, visible symptom, and a
   correlation identifier from the response or UI.
2. Check liveness, readiness, component health, migration status, and recent
   audit events. Do not copy secrets, cookies, or raw credentials into notes.
3. Classify impact and preserve relevant structured logs and backup metadata.

## Containment

Enable maintenance mode when continued writes could increase damage. Reads,
health inspection, logout, and guarded backup operations remain available.
Revoke affected sessions when identity compromise is suspected.

## Recovery

Create and verify a backup before invasive database work. Use recovery views
and supported domain retry operations first. For restore, complete the
documented preflight and use a disposable target before any approved operator
procedure. The application does not execute destructive restore.

## Closure

Confirm readiness, exercise the affected journey, disable maintenance mode,
and monitor structured request and audit events. Record root cause, scope,
timeline, remediation, and follow-up controls without retaining secrets.
