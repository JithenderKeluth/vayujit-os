# ADR 0029: Unified calendar projection

The Content Calendar returns bounded owner-scoped projections over Campaign activities. Queries
are limited to 90 days and expose safe navigation identifiers, status, readiness, timezone, and
conflict flags rather than unrestricted persistence records.
