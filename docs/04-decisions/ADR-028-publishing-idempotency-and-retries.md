# ADR-028: Publishing idempotency and retries

Status: Accepted

Client idempotency keys deduplicate executions. Every remote transport retry is a distinct durable
attempt. Ambiguous create timeouts are not retried automatically because WordPress does not accept
the local idempotency key natively; operators reconcile before taking another action.
