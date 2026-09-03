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

- Marketplace runtime focused certification: 28 passed.
- Canonical replay returns the same owner-scoped execution and does not invoke the provider twice.
- Six LOCAL_FIXTURE crash checkpoints resume to TERMINAL; BEFORE_PROVIDER invokes the provider once after recovery and later checkpoints do not repeat it.
- API regression: 1,101 passed; workflow 5 passed; scheduler 5 passed; workers 2 passed; campaign E2E 2 passed.
- Angular: 127 passed; Electron: 4 passed; build, format, Ruff, Black, mypy, and dependency audits passed.
- Migration 20261016_0095 passes fresh upgrade, downgrade, re-upgrade, and prior-head upgrade.

This is LOCAL_FIXTURE certification only. No live marketplace call, purchasing action, contact action, or payment action is enabled by this runtime.

## Certification closure work (2026-09-01)

The generic runtime certification suite now covers 28 focused cases: a ten-row
failure/retry matrix, bounded Retry-After, PostgreSQL retry-budget contention,
owner-scoped canonical ledger projection, replay, recovery idempotency, and ten
warm samples. The canonical run projects request, result, candidate, supplier,
product, offering, evidence, observation, change, alert, report, history,
product-channel, and calendar ledger identities with one correlation ID. Ledger
identity is unique per owner/provider/entity/logical key; integrity counters are
database-derived.

This remains deterministic LOCAL_FIXTURE evidence. IndiaMART discovery now invokes the shared runtime adapter exactly once per logical identity, persists the execution link on each request, and replays from the existing request without another provider call. The focused IndiaMART certification suite (including adoption and lineage proof) passes 10 tests. The full 97-test IndiaMART suite was attempted on 2026-09-01 but exceeded the local 704-second command timeout. Live IndiaMART access, external credentials, and purchasing/contact/payment operations are not enabled.

## Alibaba adoption

Alibaba uses `execute_marketplace_lifecycle` and does not add provider-specific lifecycle machinery.

## Alibaba Slice 7B.4 local evidence (2026-09-02)

Alibaba now uses the shared runtime with three focused PostgreSQL integration tests passing for deterministic discovery/replay, owner-scoped projections, evidence handoff/replay, and System Doctor visibility. No live provider call or mutation was attempted; strict provider rate/retry/crash/concurrency and live certification remain open.

## TradeIndia adoption (Slice 7C)

TradeIndia is registered as a read-only adapter through `execute_marketplace_lifecycle`. It contributes deterministic `LOCAL_FIXTURE` discovery only; shared rate windows, retry metadata, checkpoints, owner/provider identity, evidence, and integrity projections remain runtime-owned. `LIVE_READ_ONLY` is fail-closed pending official external configuration.

Global Sources adoption (Slice 7D) uses the same Marketplace Runtime contract and owner-scoped persistence. It is disabled by default; LOCAL_FIXTURE is deterministic and read-only, while LIVE_READ_ONLY is fail-closed until approved external configuration exists. No provider-specific runtime, retry, rate limiter, recovery, or mutation framework is introduced.

## Slice 8A — Cross-Marketplace Supplier Intelligence

A provider-independent canonical Supplier projection now consolidates accepted owner-scoped
Supplier, Source, Product, Evidence, verification, capability, certification, risk, and sourcing
records. It is server-derived and read-only against external systems. Exact identities may be
matched deterministically; possible matches remain review-only and are never auto-merged. Price,
MOQ, lead-time, availability, freshness, contradictions, confidence, source diversity, ranking,
reports, Product Channel contribution, Calendar reminders, and Operations/System Doctor summaries
remain lineage-preserving. Supplier contact, RFQ dispatch, purchasing, payments, and live connector
calls remain disabled or separately configured.