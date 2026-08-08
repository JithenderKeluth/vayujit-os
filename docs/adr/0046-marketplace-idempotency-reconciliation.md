# ADR 0046: Durable commerce idempotency and reconciliation

Status: Accepted

Listing and inventory mutations persist owner/account/operation/idempotency keys.
Reconciliation records typed field drift and requires an explicit review policy
before local overwrite, so remote changes are never silently discarded.

