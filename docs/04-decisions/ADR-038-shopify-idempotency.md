# ADR-038: Shopify application idempotency

Status: Accepted.

VAYUJIT owns idempotency across owner, destination, Artifact version, action, and execution.
Ambiguous creates reconcile before retry; known remote IDs are persisted and reused.
