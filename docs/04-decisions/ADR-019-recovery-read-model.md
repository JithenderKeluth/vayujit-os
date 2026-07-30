# ADR-019: Recovery as a read model

## Status

Accepted

## Decision

The recovery API projects retryable workflow and publishing failures into a
bounded, owner-scoped read model. It returns safe failure details, attempt
counts, related application URLs, and named capabilities. It does not mutate
records or mark work successful.

## Consequences

The operations UI can guide an owner to existing domain retry actions without
creating a second orchestration path or bypassing domain invariants.
