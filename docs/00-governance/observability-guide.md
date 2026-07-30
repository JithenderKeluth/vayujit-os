# Observability Guide

The API emits structured JSON request start, completion, and failure events with service,
environment, request ID, bounded correlation ID, route template, method, status, and duration.
`X-Correlation-ID` permits 1-64 letters, digits, `.`, `_`, or `-`; invalid values are replaced.
Audit writes capture the active correlation ID independently of logs.

Passwords, hashes, cookies, authorization values, tokens, database URLs, prompts, generated
content, and Publishing snapshots must not be logged. The centralized processor redacts known
secret fields. API errors return safe codes and correlation IDs without stack traces.
