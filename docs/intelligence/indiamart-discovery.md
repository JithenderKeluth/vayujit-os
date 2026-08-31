# IndiaMART read-only supplier discovery (Slice 7A)

This slice adds a provider-neutral IndiaMART boundary to Intelligence. It is
disabled by default and currently certified only against the deterministic local
fixture. No official IndiaMART endpoint or credential contract is asserted by
this repository.

## Runtime boundary

The provider supports `DISABLED`, `LOCAL_FIXTURE`, and `LIVE_READ_ONLY` modes.
`LIVE_READ_ONLY` remains blocked until an official base URL and token reference
are supplied through deployment configuration. Preflight is network-free and
returns `DISABLED`, `READY`, `NOT_CONFIGURED`, `BLOCKED_BY_EXTERNAL_CONFIGURATION`,
or `KILL_SWITCHED`. The local certification status is:

> INDIAMART LIVE DISCOVERY — BLOCKED BY EXTERNAL CONFIGURATION

Only normalized discovery is implemented. Contact, RFQ, order, payment, buyer
authentication, and supplier modification are deliberately absent.

## Configuration

All settings use the `VAYUJIT_` environment prefix:

```text
VAYUJIT_INDIAMART_ENABLED=false
VAYUJIT_INDIAMART_MODE=DISABLED
VAYUJIT_INDIAMART_BASE_URL=
VAYUJIT_INDIAMART_TOKEN_REF=
VAYUJIT_INDIAMART_TIMEOUT_SECONDS=15
VAYUJIT_INDIAMART_MAX_RESULTS=10
VAYUJIT_INDIAMART_REQUESTS_PER_MINUTE=10
VAYUJIT_INDIAMART_DAILY_QUOTA=500
VAYUJIT_INDIAMART_RETRY_MAX_ATTEMPTS=2
VAYUJIT_INDIAMART_KILL_SWITCH=false
```

Token values are never returned by API, logs, audits, operations, or the UI.
The local fixture does not make network calls and does not require credentials.

## Normalized storage and lineage

`IndiaMartDiscoveryRequest` and `IndiaMartDiscoveryResult` retain bounded
request/result lineage, provider result identity, supplier/listing identity,
location, category, explicit commercial claims, provider verification claims,
freshness, correlation, and evidence references. Raw marketplace payloads are
not persisted or exposed.

Results reuse `Supplier`, `SupplierSource`, `SupplierProduct`, and
`SupplierEvidence`. Supplier and Product/Offering matches are deterministic and
classified as `MATCH`, `POSSIBLE_MATCH`, `NO_MATCH`, or `UNKNOWN`; possible
matches are never auto-merged. Marketplace prices, MOQ, lead time,
availability, and badges remain claims (`DISCOVERY_ONLY` / provider claimed)
until independent verification accepts them.

A normalized result may be handed to the existing autonomous Evidence verifier through POST /discoveries/{result_id}/evidence. The handoff preserves owner, mission, task, provider-result, Supplier, Product/Offering, correlation, and freshness lineage. IndiaMART provider claims are classified as SUPPORTED or REJECTED; the marketplace badge alone never produces VERIFIED.

## Endpoints

All endpoints require the existing authenticated owner session and exact local
Origin policy:

* `GET /api/v1/intelligence/indiamart/preflight`
* `GET /api/v1/intelligence/indiamart/operations`
* `GET /api/v1/intelligence/indiamart/operations/summary`
* `POST /api/v1/intelligence/indiamart/discover`
* `GET /api/v1/intelligence/indiamart/discoveries`
* `GET /api/v1/intelligence/indiamart/discoveries/{request_id}`
* `POST /api/v1/intelligence/indiamart/discoveries/{result_id}/evidence`
* `GET /api/v1/intelligence/indiamart/integrity`
* `GET /api/v1/intelligence/indiamart/product-channel/{product_id}`
* `GET /api/v1/intelligence/indiamart/calendar`
* `GET /api/v1/intelligence/indiamart/report`
* `GET /api/v1/intelligence/indiamart/storage/inventory`

The Angular entry point is **Intelligence → IndiaMART Discovery**. It exposes
loading, empty, error, history, normalized result, claim, freshness, and
discovery-only states. Marketplace text is rendered as inert text; no contact
or purchasing action is present.

## Safety and operations

Requests are owner-scoped and idempotent. PostgreSQL advisory locking protects
concurrent request replay. Operations and System Doctor expose mode, readiness,
bounded quotas, kill switch state, recovery registration, live-validation state,
and owner-scoped counts without secrets. Integrity reports cover request/result
orphan and cross-owner lineage checks. Calendar and Product Channel projections
are informational only.

No live provider validation, external latency, AXE, or viewport automation is
claimed by local certification. Those remain explicit environment gaps.

## Slice 7A.3 local certification ledger

The durable lifecycle surfaces are certified locally against disposable PostgreSQL and
use existing autonomous research ledgers; IndiaMART remains discovery-only.

| Area | Result | Evidence |
| --- | --- | --- |
| Cross-source identity and match states | PASS (deterministic) | Owner-scoped Supplier, website-candidate, manufacturer-candidate, Product, and offering comparisons return MATCH, POSSIBLE_MATCH, NO_MATCH, or UNKNOWN without auto-merge. |
| Evidence verifier handoff | PASS | `/discoveries/{result_id}/evidence` persists SUPPORTED/REJECTED verifier decisions with mission/task/provider-result lineage and idempotent replay. |
| Observation replay | PASS (bounded claims) | PRICE, MOQ, LEAD_TIME, VERIFICATION_CLAIM, and AVAILABILITY snapshots are retained in append-only `observation_history`; exact replay does not append. |
| Recovery catalog and safety | PASS (shared runtime) | Operations advertises only existing autonomous recovery actions and retryable failure classes; no contact, RFQ, ordering, or payment action exists. |
| Storage/integrity projections | PASS (owner-scoped) | IndiaMART integrity reports request/result plus autonomous evidence/change/alert/contradiction/recovery/report counts, duplicates, orphans, and lineage status. |
| API, Angular, Electron, migrations, lint, format, audits | PASS | Focused IndiaMART, full API, web, build, migration, desktop smoke, lint, format, and audit commands pass locally. |

The following remain explicit local-certification gaps rather than implied provider
capabilities: a true external IndiaMART connector, multi-session PostgreSQL race
harness for every lifecycle stage, crash injection after each stage, measured query
count/performance tables, AXE automation, and browser viewport automation. These
require dedicated harnesses or external environments and are not represented as
passing provider behavior.
## Slice 7A.4 proof ledger (local, deterministic)

- PostgreSQL proof suite: `16 passed` (`test_indiamart_discovery.py`, `test_indiamart_certification.py`, `test_indiamart_proof.py`).
- Identity matrix: 6/6 PASS (exact Supplier, linked website identity, Manufacturer, possible, unrelated, insufficient).
- Supplier/Product/Offering match states: MATCH, POSSIBLE_MATCH, NO_MATCH, UNKNOWN; possible matches remain advisory and are not merged.
- Observation replay: PRICE, MOQ, LEAD_TIME, VERIFICATION_CLAIM, AVAILABILITY each retain T1 and append T2; exact replay adds zero rows.
- Evidence verifier: stale/expired evidence is rejected; IndiaMART-only confidence remains below the maximum threshold.
- Source diversity: same-provider IndiaMART listings collapse to one provider/domain source class; independent Website and Manual sources increase provider diversity.
- Recovery: catalog advertises the registered failure/action vocabulary; identical retry requests return `idempotent_reuse` on replay.
- Angular UX proof: 2 focused IndiaMART tests pass; full web suite remains green (35 files, 124 tests).
- Existing API, migration, build, desktop smoke, lint, format, audit, Ruff, Black, mypy, and diff checks remain green from this validation pass.
- Not certified by local fixtures: live IndiaMART credentials/traffic, provider-specific crash injection, multi-process recovery concurrency, query-count/N+1 benchmarks, AXE automation, and viewport automation.

## Slice 7A.5 closure ledger

- Focused PostgreSQL proof: 4/4 tests pass. Persisted identity matrices are 6/6; Supplier/Product/Offering states cover MATCH, POSSIBLE_MATCH, NO_MATCH, UNKNOWN; POSSIBLE_MATCH remains non-merging.
- Persisted observation proof covers PRICE, MOQ, LEAD_TIME, VERIFICATION_CLAIM, and AVAILABILITY with T1/T2 history and zero exact-replay delta.
- Recovery catalog and retry idempotency are proven for the registered timeout/retry path; full action, rate-limit, crash, and concurrent recovery matrices are not implemented by this pass.
- Materiality/confidence/diversity helper behavior is covered for supported deterministic cases; IndiaMART alert/risk/contradiction matrices, full storage lineage counters, performance/query counts, XSS/privacy automation, and viewport/AXE harnesses remain pending.

## Slice 7A.8 certification status

The expanded local suite contains 96 parameterized IndiaMART integration tests; the captured full-suite run recorded 95 passes, and the focused Recovery rerun recorded 22 passes, including
the four-row contradiction matrix, all eight autonomous recovery actions, bounded
Retry-After parsing, six checkpoint stages, nine durable execution-identity
concurrency cases, a two-session Recovery service race, zero-valued exposed integrity
counters, and focused Angular landmark, live-region, table-scope, and focus-style
checks. This remains LOCAL_FIXTURE evidence only.

The strict 7A hard gate is not claimed closed: minute/hour rate-limit exhaustion, provider-stage crash injection, three-run repeatability, one-test canonical end-to-end lineage, and full canonical replay require a dedicated follow-up harness. AXE, real viewport automation, and live IndiaMART credentials remain unconfigured.

### 7A.9 evidence ledger

| CASE | EVIDENCE | RESULT |
| --- | --- | --- |
| Minute available/exhausted | Existing minute-window guard; no new 7A.9 matrix run | NOT CLOSED |
| Hour available/exhausted | Shared runtime hour-window guard exists; IndiaMART-specific route proof remains pending | PARTIAL |
| Retry/provider budgets | Shared autonomous budget guards tested separately | PASS (existing) |
| Retry-After within/above maximum | Focused parser assertions | PASS |
| Route Recovery concurrency | Two authenticated HTTP submissions; 23 focused tests pass | PASS |
| Provider crash injection | No test-only provider crash hooks | NOT CLOSED |
| Repeatability 3/3 | Not run independently three times | NOT CLOSED |
| Canonical E2E/lineage/replay | No single production-service scenario | NOT CLOSED |
| Accessibility regression | Focused IndiaMART spec: 5 tests pass | PASS (focused) |

## Shared runtime evidence (2026-08-31)

IndiaMART is registered with the provider-neutral marketplace runtime for local
fixture execution. The runtime proves durable owner-scoped identity, nine checkpoint
states, minute/hour limits, fresh-session recovery across six injected boundaries,
and idempotent replay (11/11 focused runtime tests; 97/97 IndiaMART regression).
Live provider access remains unconfigured and no purchasing, contact, RFQ, payment,
or credential-bearing operation is exposed.
