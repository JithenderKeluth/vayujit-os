# ADR-046: Bound Shopify retry backoff

Status: Accepted

Retryable operations use exponential delay, bounded jitter, a ten-second maximum, and bounded
server guidance. Each calculated and applied delay is persisted. Tests inject deterministic jitter
and do not need real-time sleeps.
