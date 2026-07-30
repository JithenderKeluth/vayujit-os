# ADR-018: File-backed maintenance mode

## Status

Accepted

## Decision

Maintenance state is represented by a marker at a canonical configured path.
Only explicit CLI commands with confirmation may enable or disable it.
Middleware blocks state-changing application requests while preserving health,
system inspection, backup inspection, logout, and read operations.

## Consequences

Maintenance mode works without introducing another infrastructure service and
survives API restarts. Operators must manage the marker on each deployed host.
