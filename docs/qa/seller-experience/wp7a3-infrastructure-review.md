# WP7A-3 — PostgreSQL lifecycle review

Read-only investigation on 2026-10-31. Evidence: `tmp/qa-wp7a3/infrastructure-review.json`; reproducible command: `apps/api/.venv/Scripts/python.exe -m qa.wp7a3_infrastructure` from the repository root.

## Observed facts

- Approved QA instance: `vayujit-qa-postgres`, container ID `a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23`, instance UUID `389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`, PostgreSQL 17.10, `127.0.0.1:55432`, non-superuser role `vayujit_qa_admin`.
- Only harness-created, signed/marker/token/OID/role-verified `vayujit_qa<16-hex>_test` databases are eligible for this task's lifecycle. No permanent/golden database is a target. An existing connection string alone is not authorization.
- Application container `/infrastructure-postgres-1` has the same container identity, image, mount definitions and network memberships as the retained baseline. Its `StartedAt` and `FinishedAt` differ. This is not evidence of container recreation.
- Read-only inspection reports restart count 0, OOM flag false and exit code 0. Those current fields do not identify a historical restart initiator.
- The bounded Docker event query retained no matching lifecycle events. In the bounded in-memory log sample, recognized categories were ready=1, crash-recovery=1 and redo-complete=1; shutdown-request=0, clean-shutdown=0 and checkpoint-error=0. Raw logs, SQL, event actor attributes and command arguments were not persisted.

## Attribution and data integrity

**UNATTRIBUTED.** The available evidence cannot distinguish an authorized setup, Docker Desktop lifecycle, harness action, another local action or another initiator. Timestamps alone are not attribution. Current restart count 0 is not proof that no earlier stop/start occurred.

No demonstrated row-level data loss was established, and absence of loss is not certified. There is no historical business-row hash baseline or authorized authenticated business-data comparison in this investigation. Recovery log categories cannot substitute for that evidence.

No start, stop, restart, recreation, container exec, configuration change or business-database connection was issued against the application PostgreSQL container. No attempt was made to make historical timestamps match. The strict historical Docker preservation comparison remains a drift warning, separately from task-owned database cleanup.

## Safety and preserved uncertainty

QA runs use the approved dedicated instance with egress guards and external-mutation kill switches. No provider credential, real marketplace operation or synthetic-to-production promotion was introduced. PC-first backup certification remains parked. The earlier two-token tombstone/recovery approvals are not general recovery authority and were not reused for this package.

Historical Ads 502 remains **UNREPRODUCED / CAUSE UNCLASSIFIED**. A campaign activity HTTP 500 observed here is separately attributed to a duplicate sequence constraint; it is not a reproduction or explanation of the Ads 502.
