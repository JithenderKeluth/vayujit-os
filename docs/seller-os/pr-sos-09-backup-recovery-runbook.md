# Backup and recovery runbook

1. Keep maintenance mode and the external-mutations emergency stop active.
2. Take a PostgreSQL custom-format dump and encrypted media backup using a
   secret-managed `age` recipient. `scripts/backup-production.sh` fails closed
   if `pg_dump`, `age`, the database URL, or the recipient is missing.
3. Write checksums and retention metadata to the approved off-host destination;
   do not store only on the application volume.
4. Verify the dump and restore it into a disposable marked database. Run
   migrations only after restore preflight and compare representative counts,
   schema revision, owner constraint, media checksums, and health/readiness.
5. Reconstruct login, protected routes, catalog, inventory, marketplace
   read-only state, Action Center, and HUMAN approval boundaries.
6. Record RPO/RTO observations and unresolved evidence. Do not call the restore
   an external certification until the owner witnesses the destination and
   restore.
7. Rotate any exposed credentials and reopen writes only after a HUMAN review.

The existing Operations backup authority remains canonical for local backup
records and restore checks; this runbook does not introduce a second backup
database.
