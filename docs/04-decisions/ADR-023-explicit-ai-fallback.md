# ADR-023: Explicit AI fallback

## Status

Accepted

## Decision

Real-to-mock fallback is owner-configured, request-visible, and restricted to
retryable availability failures. Attribution always records the final provider.
