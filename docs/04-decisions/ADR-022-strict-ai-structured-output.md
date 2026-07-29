# ADR-022: Strict AI structured output

## Status

Accepted

## Decision

Remote output must parse as JSON and satisfy the existing strict Product-content
schema before artifact creation. At most one bounded repair attempt is allowed.
