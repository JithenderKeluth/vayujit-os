# TradeIndia read-only supplier discovery

TradeIndia discovery uses the shared Marketplace Runtime and is disabled by default. `LOCAL_FIXTURE` provides deterministic, bounded supplier listings for development and certification. `LIVE_READ_ONLY` is fail-closed until an approved TradeIndia read-only provider is configured; no network call is made by this slice.

Supported operations are preflight, bounded supplier/product search, normalization, owner-scoped evidence and history, integrity, and idempotent replay. Provider claims are explicitly unverified and never imply a quote, availability guarantee, or commercial commitment. Contact, messaging, RFQ, ordering, purchasing, payments, scraping, and mutations are not implemented.

Configuration variables are `TRADEINDIA_ENABLED`, `TRADEINDIA_MODE`, `TRADEINDIA_BASE_URL`, `TRADEINDIA_TOKEN_REF`, `TRADEINDIA_TIMEOUT_SECONDS`, `TRADEINDIA_MAX_RESULTS`, `TRADEINDIA_REQUESTS_PER_MINUTE`, `TRADEINDIA_REQUESTS_PER_HOUR`, `TRADEINDIA_DAILY_QUOTA`, `TRADEINDIA_RETRY_MAX_ATTEMPTS`, and `TRADEINDIA_KILL_SWITCH`.

## Slice 7C local proof ledger (2026-09-03)

Executed evidence:

- Provider unit proof: 3/3 passed (disabled default, deterministic fixture replay,
  and LIVE fail-closed configuration).
- Complete focused TradeIndia certification (`npm.cmd run test:intelligence:tradeindia`): 50 passed, 3 deselected. This covers provider defaults, all 15 normalization cases, shared Marketplace Runtime execution, owner-scoped persistence, deterministic replay, evidence handoff, hard-gate safety, rate/retry, crash recovery, contradiction/change/alert handling, integrity, privacy, query bounds, and operational projections.
- Pure preflight matrix: `DISABLED`, `LOCAL_FIXTURE`, LIVE missing credentials,
  LIVE malformed configuration, and kill-switch states returned the expected
  fail-closed statuses (`DISABLED`, `READY`,
  `BLOCKED_BY_EXTERNAL_CONFIGURATION`, and `KILL_SWITCHED`). No network call was
  made.
- Focused TradeIndia Ruff and Black checks passed. Repository API mypy, Angular tests/build, format checks, and dependency audits pass. The migration-head assertion passes; the full migration round-trip remains environment-limited by PostgreSQL `max_locks_per_transaction` during the unrelated deep downgrade.

The TradeIndia-specific proof includes all 15 deterministic normalization cases, duplicate-provider input, shared runtime replay, owner-scoped projections, evidence handoff/replay, System Doctor exposure, rate/retry/crash/concurrency, cross-source contradiction, storage-integrity, query-count, privacy, and recovery matrices. The complete local focused suite passed; live-provider behavior remains outside the certification boundary.

## Certification boundary

`LIVE_READ_ONLY` remains blocked by external configuration and no TradeIndia
network request was attempted. Contact, messaging, RFQ, ordering, purchasing,
payments, scraping, and mutations remain disabled or unimplemented. The only
accurate status is:

- TRADEINDIA PROVIDER ADAPTER — LOCAL PROOF PASSED
- TRADEINDIA SUPPLIER DISCOVERY — LOCAL PROOF PASSED
- TRADEINDIA LISTING INTELLIGENCE — LIMITED TO DETERMINISTIC FIXTURE PROOF
- TRADEINDIA EVIDENCE HANDOFF - LOCAL HANDOFF/REPLAY PROOF PASSED
- SLICE 7C - LOCAL CERTIFICATION (live and strict closure matrices remain open)
## Slice 7C local hard-gate evidence (2026-09-03)

The TradeIndia hard-gate suite now exercises the shared Marketplace Runtime locally: retry classification (10/10), bounded rate/retry budgets, six checkpoint crash-recovery stages, three-run repeatability, four persisted cross-source contradiction cases, seven replay-safe changes, six rejected-data states, six alert/replay cases, canonical PostgreSQL lineage/storage/replay, duplicate/orphan/broken-lineage/cross-owner counters, privacy/XSS boundaries, ten-sample endpoint performance/query bounds, Operations/System Doctor, and recovery audit idempotency. The focused hard-gate tests passed after correcting the evidence fixture to include its required autonomous task lineage.

This is LOCAL_FIXTURE evidence only. Live TradeIndia remains blocked by external configuration; live latency and external-provider behavior are not certified. AXE and viewport automation remain not configured. No contact, RFQ, order, purchase, payment, or mutation capability is implemented.

## Slice 7C certification boundary

TradeIndia is a thin read-only adapter over the shared Marketplace Runtime. The provider defaults to `DISABLED`; `LOCAL_FIXTURE` is deterministic and network-free; `LIVE_READ_ONLY` is fail-closed as `BLOCKED_BY_EXTERNAL_CONFIGURATION` until an approved official integration is configured. No contact, messaging, RFQ, ordering, purchasing, payment, authenticated scraping, CAPTCHA bypass, or mutation path exists.

The local fixture matrix contains 15 required cases (complete, missing fields, identity variants, duplicate, provider claims, changed/disappeared listings, commercial disagreement, and stale commercial observation) represented as source-only claims. Missing values remain null/unknown and are never inferred. Results, evidence handoff, projections, audit events, and replay are owner-scoped and use shared runtime identity; provider claims remain unverified until independent verification.

TradeIndia LOCAL_FIXTURE integration and hard-gate tests pass after adding shared Operations/System Doctor visibility. Live provider behavior, external credentials, browser accessibility automation, and production certification remain unconfigured and unclaimed.