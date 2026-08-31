# Marketplace Runtime

The provider-neutral marketplace runtime supplies durable execution identity,
owner/provider scoping, checkpoints, bounded minute/hour rate windows, and a
LOCAL_FIXTURE-only fault hook. Provider adapters supply normalized discovery;
the runtime owns lifecycle, retry/recovery, and integrity boundaries.

## Execution and checkpoints

MarketplaceExecution records provider, owner, mission/task, correlation and
logical identity, status, attempt, failure and retry metadata, and timestamps.
Supported checkpoints are CLAIMED, BEFORE_PROVIDER, PROVIDER_COMPLETE,
RESULTS_PERSISTED, EVIDENCE_PERSISTED, CHANGE_COMPLETE, ALERT_COMPLETE,
REPORT_COMPLETE, and TERMINAL.

## Rate windows

MarketplaceRateWindow atomically consumes owner/provider-scoped minute and
hour windows under PostgreSQL row locking. Counters reset at window expiry,
remaining values are bounded at zero, and replay must be resolved before
consumption. IndiaMART supplies provider-specific limits through the shared
policy (indiamart_requests_per_minute and indiamart_requests_per_hour).

## Adapter and safety boundary

Adapters are limited to preflight, discovery/normalization, and failure
classification. Contact, messaging, RFQ, order, purchasing, payment, and
unrestricted crawling remain unsupported. Fault injection is an internal test
context and only fires for LOCAL_FIXTURE; it is not a public request field
and cannot affect LIVE_READ_ONLY.

## Certification boundary

The existing IndiaMART deterministic suite and route-level Recovery race remain
the evidence baseline. Full rate-window, provider-crash, repeatability, and
canonical lineage/replay certification must be executed before claiming the
marketplace runtime hard gate closed. AXE, viewport automation, live IndiaMART,
external AI, purchasing, and payments remain separate boundaries.


## Local certification evidence (2026-08-31)

- Marketplace runtime focused certification: 11 passed.
- Canonical replay returns the same owner-scoped execution and does not invoke the provider twice.
- Six LOCAL_FIXTURE crash checkpoints resume to TERMINAL; BEFORE_PROVIDER invokes the provider once after recovery and later checkpoints do not repeat it.
- API regression: 1,101 passed; workflow 5 passed; scheduler 5 passed; workers 2 passed; campaign E2E 2 passed.
- Angular: 127 passed; Electron: 4 passed; build, format, Ruff, Black, mypy, and dependency audits passed.
- Migration 20261014_0093 passes fresh upgrade, downgrade, re-upgrade, and prior-head upgrade.

This is LOCAL_FIXTURE certification only. No live marketplace call, purchasing action, contact action, or payment action is enabled by this runtime.
