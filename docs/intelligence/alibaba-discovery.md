# Alibaba read-only supplier discovery

Alibaba discovery uses the shared Marketplace Runtime and is disabled by default. `LOCAL_FIXTURE` provides deterministic, bounded supplier listings for development and certification. `LIVE_READ_ONLY` is fail-closed until an approved Alibaba read-only provider is configured; no network call is made by this slice.

Supported operations are preflight, bounded supplier/product search, normalization, owner-scoped evidence and history, integrity, and idempotent replay. Provider claims are explicitly unverified and never imply a quote, availability guarantee, or commercial commitment. Contact, messaging, RFQ, ordering, purchasing, payments, scraping, and mutations are not implemented.

Configuration variables are `ALIBABA_ENABLED`, `ALIBABA_MODE`, `ALIBABA_BASE_URL`, `ALIBABA_TOKEN_REF`, `ALIBABA_TIMEOUT_SECONDS`, `ALIBABA_MAX_RESULTS`, `ALIBABA_REQUESTS_PER_MINUTE`, `ALIBABA_REQUESTS_PER_HOUR`, `ALIBABA_DAILY_QUOTA`, `ALIBABA_RETRY_MAX_ATTEMPTS`, and `ALIBABA_KILL_SWITCH`.

## Slice 7B.4 local proof ledger (2026-09-02)

Executed evidence:

- Provider unit proof: 3/3 passed (disabled default, deterministic fixture replay,
  and LIVE fail-closed configuration).
- PostgreSQL integration proof through the focused integration tests with
  `ALIBABA_ENABLED=true` and `ALIBABA_MODE=LOCAL_FIXTURE`: 3/3 passed. This
  covers owner-scoped request/result persistence, shared Marketplace Runtime
  execution, deterministic replay, discovery history, operations, and integrity
  endpoints.
- Pure preflight matrix: `DISABLED`, `LOCAL_FIXTURE`, LIVE missing credentials,
  LIVE malformed configuration, and kill-switch states returned the expected
  fail-closed statuses (`DISABLED`, `READY`,
  `BLOCKED_BY_EXTERNAL_CONFIGURATION`, and `KILL_SWITCHED`). No network call was
  made.
- Focused Alibaba Ruff and Black checks passed. Repository API mypy, Angular
  tests/build, format checks, migrations, and dependency audits were previously
  green on this branch.

The Alibaba-specific proof now includes all 13 deterministic normalization cases, duplicate-provider input, shared runtime replay, owner-scoped projections, evidence handoff/replay, System Doctor exposure, and a dedicated five-test Angular accessibility/responsive spec. Full rate/retry/crash/concurrency, cross-source contradiction, storage-integrity, query-count, and live-provider matrices remain outside the local proof and are **not claimed as passed**.

## Certification boundary

`LIVE_READ_ONLY` remains blocked by external configuration and no Alibaba
network request was attempted. Contact, messaging, RFQ, ordering, purchasing,
payments, scraping, and mutations remain disabled or unimplemented. The only
accurate status is:

- ALIBABA PROVIDER ADAPTER — LOCAL PROOF PASSED
- ALIBABA SUPPLIER DISCOVERY — LOCAL PROOF PASSED
- ALIBABA LISTING INTELLIGENCE — LIMITED TO DETERMINISTIC FIXTURE PROOF
- ALIBABA EVIDENCE HANDOFF - LOCAL HANDOFF/REPLAY PROOF PASSED
- SLICE 7B - LOCAL PARTIAL CERTIFICATION (live and strict closure matrices remain open)
## Slice 7B.5 local hard-gate evidence (2026-09-03)

The Alibaba hard-gate suite now exercises the shared Marketplace Runtime locally: retry classification (10/10), bounded rate/retry budgets, six checkpoint crash-recovery stages, three-run repeatability, four persisted cross-source contradiction cases, seven replay-safe changes, six rejected-data states, six alert/replay cases, canonical PostgreSQL lineage/storage/replay, duplicate/orphan/broken-lineage/cross-owner counters, privacy/XSS boundaries, ten-sample endpoint performance/query bounds, Operations/System Doctor, and recovery audit idempotency. The focused hard-gate tests passed after correcting the evidence fixture to include its required autonomous task lineage.

This is LOCAL_FIXTURE evidence only. Live Alibaba remains blocked by external configuration; live latency and external-provider behavior are not certified. AXE and viewport automation remain not configured. No contact, RFQ, order, purchase, payment, or mutation capability is implemented.
