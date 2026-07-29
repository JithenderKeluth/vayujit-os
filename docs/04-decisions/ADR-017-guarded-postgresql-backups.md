# ADR-017: Guarded PostgreSQL backups

## Status

Accepted

## Decision

Local backups use PostgreSQL custom format, generated bounded filenames, a
canonical configured directory, SHA-256 verification, and a metadata sidecar.
The web API supports creation, listing, verification, and restore preflight
only. Destructive restore execution remains an operator-run procedure.

## Consequences

Backup artifacts are inspectable and tamper-detectable. Restore cannot be
triggered accidentally from the application. Current local backups are not
encrypted and must be protected by host access controls.
