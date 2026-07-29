# ADR-016: Structured observability and correlation identifiers

## Status

Accepted

## Decision

The API emits structured JSON request events and propagates a bounded
`X-Correlation-ID`. The identifier is attached to request context, safe error
responses, and audit events. Invalid or oversized client values are replaced.
Known sensitive fields are redacted before serialization.

## Consequences

Operators can trace one request through API and audit records without exposing
credentials. Route templates are logged instead of arbitrary path values.
