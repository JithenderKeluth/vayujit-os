# Operations Guide

AI operations are detailed in `ai-operations-guide.md`. Status and usage
commands are safe routine diagnostics. Validation makes an explicit provider
request and should use the local fake provider first; any paid call requires an
operator-supplied credential and authorization.

The authenticated `/operations` area links Health, Recovery, Backups, and Audit. Recovery
normalizes existing failures and links to existing domain actions; it never forces success.
Backups use owner-scoped metadata, bounded filenames, SHA-256, and compatibility preflight.
Audit exposes a safe projection with correlation filtering and formula-safe bounded CSV.

Use `npm.cmd run system:doctor` for PASS/WARN/FAIL runtime checks.
