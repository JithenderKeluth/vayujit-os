# ADR 0019: Scheduler crash-recovery reconciliation

Status: Accepted

Expired leases are not blindly reset. Recovery checks worker freshness and the stable connector
execution idempotency key. Confirmed remote success completes the job; a known retryable absence
waits with bounded backoff; an ambiguous running result requires manual reconciliation. Every
decision is persisted and audited.
