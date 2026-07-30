# ADR-011: Owner-Scoped Publishing Idempotency

**Status:** Accepted

PostgreSQL uniquely constrains `(owner_id, idempotency_key)`. Equivalent retries return the stored
execution and attempts; reuse with another artifact or destination conflicts. Keys remain for the
life of execution history. This prevents duplicate side effects without Redis and remains valid
when a future connector runs asynchronously.
