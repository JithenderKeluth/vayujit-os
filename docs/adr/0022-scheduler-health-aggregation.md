# ADR 0022: Scheduler Health aggregation

Status: Accepted

Scheduler Health aggregates bounded PostgreSQL counts for schedules, due/retrying/dead-letter
jobs, workers, leases, and connector backlog. Worker identifiers are hashed before display.
Credentials, environment dumps, paths, payloads, database URLs, and Artifact content are excluded.
