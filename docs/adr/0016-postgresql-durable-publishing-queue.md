# ADR 0016: PostgreSQL durable publishing queue

Status: Accepted

VAYUJIT OS uses PostgreSQL as the source of truth for scheduled publishing. Jobs are claimed
with `SELECT … FOR UPDATE SKIP LOCKED`, committed before connector I/O, and protected by
renewable leases. This avoids adding Redis or another broker during the single-owner phase while
still allowing multiple worker processes and crash recovery.

At-least-once delivery is intentional. A stable schedule-occurrence key prevents duplicate job
creation, and each connector execution receives a job-derived idempotency key. If a worker loses
its lease during a remote request, recovery records the ambiguous attempt and retries only through
the same idempotent execution boundary.

The API and worker are separate processes. API startup never launches an in-process scheduler.
