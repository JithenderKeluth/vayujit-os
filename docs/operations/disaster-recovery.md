# Disaster recovery runbook

Backups are PostgreSQL custom-format dumps plus a JSON sidecar containing checksum, migration revision, and application version. The database and local media directory are **quiesced and eventually consistent**, not atomic. Pause writes, create both backups, and record the two timestamps.

- DB loss: provision a fresh disposable target, restore with `pg_restore`, verify Alembic and integrity checks, then cut over.
- Media loss: restore the media backup, verify every checksum and owner-scoped lineage row, and quarantine unmatched files.
- Worker crash: restart workers; leases and checkpoints are reclaimed by the durable worker.
- Scheduler crash: restart one scheduler instance; idempotency keys prevent duplicate materialization.
- Provider outage: keep live switches off, preserve safe failure codes, and retry only according to bounded policy.
- Credential compromise: disable the provider switch, revoke credentials, rotate encryption keys, and review audit history.
- Migration/deployment failure: stop writes, preserve the failed release artifacts, restore the latest verified backup, and use the rollback checklist.