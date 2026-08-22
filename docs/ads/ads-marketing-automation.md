# Ads & Marketing Automation

## Local Slice 1 boundary

VAYUJIT OS uses one normalized, owner-scoped Ads domain for Meta and Google.
The local adapters are deterministic and network-free. They never spend money,
call live provider APIs, or return credentials. Live Meta Ads and live Google Ads
remain explicitly **not validated**.

## Architecture

The API exposes `AdAccount`, `AdCampaign`, `AdGroup` (Meta Ad Set / Google Ad
Group), `AdCreative`, `Ad`, `AdAudience`, `AdBudget`, `AdSchedule`, `AdMetric`,
`AdConversion`, `AdRemoteMapping`, and `AdJob`. Products, Brands, AI artifacts,
Image/Video media, Campaigns, Calendar, Audit, owner authentication, and the
existing durable-job conventions remain the sources of truth; Ads does not add
another scheduler, worker, media store, credential vault, or Campaign engine.

Provider capability metadata comes from `/api/v1/ads/capabilities`. Angular
does not duplicate objective, placement, media, budget, currency, or text-limit
rules.

## Accounts and credentials

`POST /api/v1/ads/accounts` creates a disabled local account. Credentials are
write-only, encrypted (or one-way hashed when local encryption is unavailable),
and represented only by safe metadata. Validate, enable, disable, replace or
remove credentials, archive, inspect diagnostics, and view owner-scoped history
through the account routes. A disabled account blocks queued mutations.

## Campaign and creative lifecycle

Campaign mutations follow `preview -> explicit confirm -> durable job -> worker
-> fake connector -> local finalization`. Preview responses contain a stable
fingerprint and `mutates: false`; stale fingerprints are rejected. Budgets are
versioned and preview responses show current/proposed amounts, currency, and
difference. Destination URLs require HTTPS and reject script, data, file,
localhost, and malformed schemes.

Creatives preserve exact approved Content Artifact, Image, or Video lineage and
never resolve ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œlatestÃƒÂ¢Ã¢â€šÂ¬Ã‚Â during execution. Readiness and preview responses expose
blockers/warnings and a fingerprint. Metrics are deterministic, replay-safe,
and labeled `synthetic`; unavailable external metrics are not invented.

## Connectors and recovery

The transport-injected connector contract covers validation, capabilities,
campaign/group/creative/ad mutations, pause/resume/archive, lookup,
reconciliation, metrics, and failure simulation. The Meta adapter supports
Facebook/Instagram feed, story, reel, image, video, copy, CTA, destination,
audience, budget, and schedule metadata. The Google adapter supports Search,
Display, YouTube-style video, keywords/negative keywords, audiences, bidding,
budget, and schedule metadata.

Normalized failure codes include `ads.account_disabled`,
`ads.invalid_credentials`, `ads.unsupported_objective`, `ads.invalid_budget`,
`ads.invalid_audience`, `ads.invalid_creative`, `ads.invalid_destination`,
`ads.throttled`, `ads.ambiguous_result`, `ads.remote_not_found`, and connector
availability/time-out classes. Recovery is owner-scoped and confirmation-gated;
reconciliation marks drift for review rather than silently overwriting remote
state.

## Security and privacy

Audience definitions use abstract segments only. Fake connector payloads contain
no buyer emails, phone numbers, addresses, payment data, Orders, marketplace or
social credentials, AI tokens, database URLs, or local paths. All routes require
the existing owner session and Origin protection.

## UI and verification

The authenticated `/ads` workspace provides Overview, Accounts, Campaigns,
Analytics, Recovery, and Settings routes. Synthetic data is visibly labeled;
native controls provide keyboard access and responsive static layouts for small,
tablet, and desktop widths. Axe automation and viewport automation are not
configured in this local slice.

Focused acceptance coverage is in the Ads acceptance modules under
`apps/api/tests/test_ads_*_acceptance.py` plus the foundation and hard-closure
suites. The exercised local matrix covers server-driven capabilities,
owner-scoped audience validation, write-only credentials, account lifecycle,
preview/confirm and budget version safety, durable worker execution, retry and
recovery idempotency, synthetic metrics, destination security, creative
lineage/version safety, Product Channel projections, Meta and Google fake
provider flows, cross-provider isolation, and private failure projections.
remain explicitly unvalidated rather than being reported as passing.
The local evidence is limited to deterministic, network-free Meta and Google
adapters. Dedicated acceptance suites now cover crash-before and crash-after
checkpoint recovery, all 16 failure-code/action combinations, sequential and
concurrent recovery idempotency, Meta/Google image and video lineage, exact
creative version safety, worker account-disable safety, provider isolation, a
38-case security matrix, privacy payload assertions, Commerce-backed
profitability and ROAS semantics, Product Channel actions, Campaign/Calendar
lineage, and storage-integrity counters. The suites are runnable with
`npm run test:ads:crash`, `npm run test:ads:recovery-matrix`,
`npm run test:ads:media`, `npm run test:ads:isolation`,
`npm run test:ads:lineage`, `npm run test:ads:version-safety`,
`npm run test:ads:security-matrix`, and `npm run test:ads:profitability`. Scheduler/workflow constituents were run independently (`test:scheduler`, `test:workers`, `test:workflow`, and `test:scheduler:integration`); the aggregate integration command is runtime-heavy and is characterized separately rather than treated as an automatic pass.
Live-provider calls and real spend remain unvalidated by design.

## Future boundary

Amazon Ads, Flipkart Ads, Meesho Ads, live conversion APIs, advanced autonomous
optimization, and live provider credentials belong to later slices.

## Slice 1A backend closure

The hard-closure API keeps the frozen normalized domain and adds the following
server-authoritative contracts:

- Audiences persist geography, locale/language, age, gender, interests,
  demographics, custom/remarketing references, exclusions, and keyword intent.
  Validation stores provider compatibility and rejects unknown owner-scoped
  references without ingesting customer PII.
- Google Search campaigns can bind an exact owner-scoped Keyword Set, locale,
  positive/negative keywords, and provenance. External volume, CPC,
  competition, and impression values remain unavailable unless supplied by a
  provider fixture.
- Content, image, and video creatives bind immutable approved identities and
  versions. Readiness checks owner, Product, approval, locale, MIME/checksum,
  dimensions/size metadata, media identity, placement, CTA, destination, and
  provider/objective compatibility; execution never resolves a latest version.
- Budget changes use preview -> explicit confirmation -> versioned durable Ads
  job -> fake provider -> checkpoint/local finalization. The preview is
  non-mutating and stale fingerprints are rejected. Remote version and
  confirmation fingerprint are retained.
- Ads jobs are claimed with PostgreSQL row locks and leases and are dispatched
  by the existing publishing worker loop. Idempotency keys are unique per
  owner; retryable failures expose Retry-After/backoff metadata and bounded
  attempts. Ambiguous fake mutations persist the remote entity and require
  deterministic reconciliation instead of blind replay.
- The 16 normalized failure codes are exposed at `/api/v1/ads/failures/catalog`.
  Every execution failure records a safe message, retryability, recovery
  actions, entity identity, and correlation ID. Recovery requests are explicit,
  owner-scoped, confirmation-gated, and idempotent.
- Reconciliation returns typed drift findings. Refresh, keep-remote, review,
  and confirmation-gated overwrite actions resolve findings without silent
  remote replacement.
- Conversion fixtures persist provider, Campaign/group/ad/Product identity,
  type, timestamp, value, currency, source, attribution type, and attribution
  window. ROAS is only calculated for compatible positive spend and known
  revenue; profitability remains `Unavailable` whenever COGS, fees, or another
  required Commerce value is absent.
- Product Channel and Calendar projections expose Ads account/provider,
  campaign/group/ad, exact creative versions, budget, synthetic metrics,
  remote state, update availability, drift, failures, recovery, schedule,
  timezone, and server-derived action states.

Focused closure tests live in `apps/api/tests/test_ads_hard_closure.py` in
addition to the foundation suite. Dedicated acceptance modules cover audience,
budget, worker/concurrency, failure taxonomy, Meta, Google, creative, Product
Channel, and security/privacy behavior. They cover the 16-code catalog,
capability separation, audience validation, idempotent recovery,
non-mutating budget preview/confirmation, explicit ROAS semantics, Product
Channel projection, and ambiguous remote identity preservation.

The local certification boundary is deterministic Meta/Google fake providers;
no live provider API, real spend, customer PII, credentials, AI tokens, Order
payloads, database DSNs, or filesystem paths enter connector payloads.

## Slice 1B operational UX

The Angular Ads workspace is available at `/ads` and keeps the complete owner-scoped flow in one accessible, responsive surface:

- `/ads/accounts` supports local Meta/Google account creation, write-only credential entry, validation, enable/disable, credential removal, and safe status presentation. Account IDs and history links never expose credential values.
- `/ads/campaigns` provides bounded search and provider/state filters. `/ads/campaigns/:id` shows server-returned campaign state, budget version, reconciliation state, exact creative lineage, safe failure information, pause/resume, and reconciliation actions.
- `/ads/create` is a six-screen operational wizard containing the requested twelve review concepts: account, product, audience, creative, exact artifact/media version, destination, budget, bidding, schedule, review, preview, and explicit confirmation. Provider objectives, bidding strategies, and creative types come from `/api/v1/ads/capabilities`; readiness and preview are server calls.
- `/ads/analytics`, `/ads/calendar`, `/ads/recovery`, and `/ads/settings` expose source-labeled metrics, profitability/ROAS as unavailable when inputs are absent, schedule lineage/timezone, confirmation-gated recovery, and the local fake-provider boundary.
- The presentation uses semantic headings, native controls, visible focus, keyboard-safe buttons/links, `aria-live` loading/status messages, table captions, responsive grids, and horizontal table scrolling at narrow widths. Duplicate mutation clicks are disabled while a request is in flight and confirmations are required for destructive actions.

This slice is local/synthetic only. Automated Axe and automated browser viewport harnesses are not configured in the repository; static accessibility review and Angular component tests are the local evidence. Existing lint/build/format/performance checks remain the certification baseline. Live Meta and Google Ads are intentionally not validated.
## Local optimization and intelligence slice

The optimization layer is deterministic and local-only. It normalizes metric evidence into owner-scoped recommendations with stable fingerprints, severity, confidence, explanations, action options, and stale-context protection. Rules are versioned, provider/objective scoped, and bounded by metric window, cooldown, daily action limit, and explicit allowed actions. `recommend_only` is the default; bounded auto-apply is limited to low-risk actions and still records a decision.

Use the Angular Ads optimization workspace at `/ads/optimization` (or its Recommendations, Rules, Anomalies, Experiments, History, and Comparison tabs). Every recommendation has a non-mutating preview. A confirmed action creates an `AdJob`, `AdOptimizationDecision`, and `AdOptimizationExecution`; the existing Ads worker and fake connector finalize it. Repeating the same idempotency key reuses the existing execution. Rollback is preview/confirm gated and queued through the same durable worker; unsupported rollback actions are safely rejected.

Anomaly and creative-fatigue signals are thresholded from available local metrics and labeled synthetic. Experiments require valid variant allocations and deterministic winner evidence. Cross-provider comparison never mixes currencies, objectives, attribution windows, or unavailable metrics. Responses are owner-scoped, omit credentials and prompts, and expose only safe operational metadata.
## Ads Slice 2 final local certification closure

The optimization certification suite is `apps/api/tests/test_ads_optimization_certification.py` and is runnable with `npm.cmd run test:ads:optimization-certification`. It exercises all 22 normalized recommendation actions, direct evidence/explanation/confidence/risk/actionability/provider-compatibility fields, recommendation fingerprint reuse, stale confirmation safety, rule CRUD/version/lifecycle, validation rejection, and bounded engine timing. Existing closure and privacy/security suites remain part of the matrix.

The deterministic intelligence boundary includes budget opportunity heuristics, provider-aware bid/keyword/audience compatibility, creative fatigue states, anomaly types (including spend spike, delivery stopped, missing ingestion, and budget exhaustion), deduplicated alerts with acknowledge/dismiss and cleared-condition resolution, experiment safety/result semantics, durable experiment winner adoption, cross-provider currency/objective warnings, Product Channel/Campaign projections, and optimization calendar dates. Failure taxonomy includes `ads.optimization_stale`, `ads.rule_invalid`, `ads.guardrail_blocked`, `ads.insufficient_data`, `ads.experiment_invalid`, and `ads.rollback_conflict`, each with a safe message and bounded recovery actions.

All local metrics, recommendations, anomalies, fatigue signals, experiment results, comparison values, jobs, and audit metadata are explicitly marked `synthetic`/`synthetic_local`. Provider payloads, credentials, tokens, cookies, database URLs, local paths, prompts, buyer PII, and unrelated Product/Order data are not returned. Axe and automated viewport harnesses are not configured; keyboard-native controls and static responsive/accessibility review remain the local evidence. Live Meta/Google calls and real spend remain not validated.

## Ads Slice 3 Marketplace Ads

Marketplace Ads reuse the normalized Ads Core, durable jobs/workers, recovery, metrics, conversions, Product Channel, Campaign, Calendar, analytics, and audit projections. Amazon and Flipkart are deterministic local fake connectors only; no live provider calls or real spend are performed. Meesho is explicitly exposed as not supported because no honest normalized capability is modeled.

Marketplace campaigns bind an owner-scoped Product to an exact marketplace listing and immutable listing version. Readiness and non-mutating preview validate the account, Product, listing/version, objective, supported targeting, creative lineage, budget, bidding, destination, provider capability, and currency before explicit confirmation queues a durable job. The fake connectors provide deterministic remote IDs, checkpoint-safe worker finalization, persisted mapping reconciliation, normalized synthetic metrics (including sales/revenue), conversions, ROAS/profitability availability, failure simulation, and provider-isolated state.

The `/api/v1/ads/marketplace` API exposes capabilities, listing registration/version lookup, readiness, preview/confirm, campaign/detail, reconciliation, metrics, conversions, analytics, Product Channel, comparison, failure simulation, and history. `apps/web` keeps these providers in the existing `/ads` workspace and surfaces provider filters and the local fake boundary. Privacy responses exclude credentials, tokens, cookies, DSNs, paths, prompts, buyer PII, raw Orders, and unrelated Products. Automated Axe and viewport harnesses remain not configured; static accessibility, keyboard, and responsive review are the local evidence.

### Marketplace Ads closure evidence

Slice 3 marketplace acceptance is maintained separately from the normalized Ads Core. `test_ads_marketplace_acceptance.py` verifies the core Amazon/Flipkart/Meesho boundary and `test_ads_marketplace_closure.py` verifies crash-before, crash-after, ambiguity reconciliation, throttling, target/listing-version safety, replacement, Product Channel, Calendar, analytics, privacy, storage, and cross-marketplace isolation. The local certification uses only deterministic fake Amazon and Flipkart connectors; Meesho is represented as `not_supported` and has no Ads connector.

A remote checkpoint is written before local finalization. Recovery uses the existing durable Ads worker and unified Recovery actions; retryable failures are bounded and expose safe retry metadata. Exact listing and immutable creative versions flow through readiness, preview, confirmation, mapping, Campaign, Product Channel, Calendar, and history. Synthetic metrics are labeled and never implicitly converted across currencies. Live marketplace latency, credentials, buyer data, Orders, DSNs, filesystem paths, and provider APIs are outside this local certification boundary.

## Slice 4 cross-channel automation

The local Slice 4 foundation adds an owner-scoped Marketing Plan projection at `/api/v1/ads/marketing`. Plans are version-pinned, preview-first, explicitly confirmed, and idempotent. Readiness reports per-channel blockers and warnings using server-owned capabilities; Meesho Ads remains unsupported.

The plan stores exact Product IDs, channel selection, budget envelope, objective, creative mapping, targeting, schedule, automation mode, correlation ID, and channel execution states. Budget changes, version updates, rollback, and catch-up policy changes are guarded by preview/confirm contracts. Analytics, Product Channel, Calendar, history, and recovery projections reuse the normalized plan/channel records and remain synthetic/local. No live provider calls or autonomous spend redistribution are enabled.

Migrations 20260913_0061 and 20260913_0062 persist versioned plans and durable per-channel execution. Focused integration coverage validates capability honesty, Meesho rejection, readiness, stale preview rejection, explicit confirmation, sequential idempotency, channel state projection, history, cancellation, worker materialization, checkpoints, rescheduling, catch-up safety, and privacy/security evidence. Live providers, browser Axe automation, and viewport automation remain outside local validation.
### Durable cross-channel execution closure

Migration `20260913_0062` adds immutable `marketing_plan_revisions`, durable
`marketing_plan_executions`, and owner-scoped `marketing_channel_executions`.
Confirmation now records the exact plan version and creates one local child
execution per selected channel; it does not call a provider from the HTTP
request. Each child has a stable job identity, correlation ID, dependency/state
projection, retryability, safe failure message, and provider-mutation checkpoint.

The execution API is available at `/api/v1/ads/marketing`: materialize a plan,
inspect its execution and revisions, run deterministic local worker outcomes,
inspect Recovery actions, and apply retry/reconcile/cancel actions. Plan state is
derived from child states, including mixed/partial completion and ambiguous
recovery. Readiness now returns exact owner-scoped account/listing/product,
creative, budget, targeting, schedule, and dependency projections; account and
plan currencies must match and no FX conversion is performed.

Validation evidence for this closure: the focused Marketing Plan suite reports
5 passed tests (including materialization, partial success, ambiguity recovery,
and revision visibility); the API regression suite reports 312 passed tests;
Ruff, Black, mypy, Angular tests/build, Electron smoke, migrations, formatting,
and diff checks pass. Provider calls remain outside this HTTP materialization
boundary and live providers remain unvalidated.

### Slice 4 execution and safety closure

### Slice 4 final acceptance evidence

The dedicated PostgreSQL acceptance suite tests/test_marketing_plan_slice4_acceptance.py now covers the local six-channel materialization path (Meta, Google, Amazon, Flipkart, Social, Campaign), persisted Product/plan lineage, one durable job per channel, fake remote identities, and channel-isolated partial outcomes with server-provided Recovery actions. The focused suite passes 2 tests. Existing Ads crash, concurrency, version-safety, security, privacy, optimization, marketplace, and worker suites remain separate regression coverage; live providers, Axe, and viewport automation remain outside the local deterministic boundary.


Marketing Plan channel jobs now use the existing Ads worker entry point. The HTTP
confirmation/materialization path only creates owner-scoped durable AdJob and
channel-execution records; run_next_ads_job delegates marketing_plan_channel
jobs to a deterministic local adapter. Meta, Google, Amazon, and Flipkart use the
existing fake Ads connectors; Social uses the existing fake Social connector;
Campaign uses a deterministic local Campaign Activity identity. Each worker
persists the plan/version, channel execution, Job, correlation ID, product and
creative lineage, checkpoint, provider mutation flag, and remote identity. A
checkpoint is reused on retry, and completion audit is guarded by execution
identity so lease recovery cannot duplicate the event.

Plan-level rescheduling is confirmation-gated and idempotent. Previous schedule
identities remain in schedule_history, while the current schedule identity is
projected on the channel. Catch-up policies (skip_missed, bounded
grace_period, and manual_confirmation) are persisted without provider mutation.
Dependency resolution supports explicit resume or safe terminal failure.
Recovery exposes state-authorized channel actions plus the plan-level review
matrix. Budget reallocation materializes one deterministic budget Job per
channel; optimization and creative updates use stale-safe preview/confirm
contracts and append plan history.

The local closure API also exposes deterministic Security (44 safe cases),
Privacy, Performance, and Storage Integrity evidence at
/api/v1/ads/marketing/security/matrix,
/api/v1/ads/marketing/privacy/matrix,
/api/v1/ads/marketing/performance, and
/api/v1/ads/marketing/storage/integrity. The Angular Marketing Plan surface
contains a keyboard-native twelve-step wizard and owner-scoped plan review
entry point. Automated Axe and viewport harnesses are not configured, and live
providers, Meesho Ads, real spend, and external credentials remain outside the
local deterministic boundary.


## Slice 4 final certification evidence (2026-08-22)

The final bounded evidence run did not claim the unavailable hard gates. The
following evidence is reproducible on the local disposable PostgreSQL database:

- Auto-reallocation: one bounded approved 55/45 INR action succeeded, the same
  idempotency key returned `idempotent_reuse=true`, and a 1% per-channel guardrail
  rejected an 80/20 proposal before mutation. The implementation uses the
  existing preview/confirm budget path, durable jobs, worker checkpoint, history,
  and audit.
- Concurrent budget reallocation: two concurrent HTTP confirmations using
  independent database sessions produced one logical version change, two provider
  channel jobs, one audit event, and one idempotent reuse response. The focused
  PostgreSQL test passed.
- Six-channel timing: confirmation 154.195 ms; time to first downstream job and
  first completion 72.710 ms; materialization/worker run 323.366 ms; total
  confirmation-to-completion 477.663 ms. Six channels, six jobs, six attempts,
  six deterministic fake mutations, zero duplicate jobs/mutations, zero retries,
  zero reconciliations, and zero recovery operations were observed.
- Warm API harness: 10 samples per operation. Median/p95 milliseconds were: list
  15.271/21.237, detail 14.743/16.284, readiness 14.373/16.578, preview
  14.171/16.934, confirmation 20.637/22.320, channel status 15.195/18.402,
  analytics 12.518/14.413, optimization 14.339/15.416, recovery
  15.735/17.209, history 15.808/19.123, calendar 16.090/22.107,
  Product Channel 15.851/21.397, and budget preview 13.652/15.664.
- Storage endpoint/test now reports owner-scoped counts for plans, revisions,
  channel executions, projected schedules, jobs, attempts, provider mappings,
  recovery, optimization executions, audit, and history, plus duplicate/orphan/
  lineage/leakage counters. The focused one-plan integrity assertion passed with
  every reported counter at zero. A full canonical six-channel growth delta was
  not captured; no file/byte delta is claimed.
- UX: the focused Angular matrix covers 20 user-visible states and native wizard
  control semantics; the complete web suite passed 88 tests. Static source review
  covers headings, labels, native buttons, alerts, focus/keyboard flow, and the
  390px media-query layout. Axe and automated viewport runs are not configured.

The requested final-proof gates are now represented by focused local tests:

- Concurrent reschedule produced one replacement schedule/job lineage and one idempotent reuse response.
- Crash-before and crash-after provider checkpoint recovery each completed with one provider mutation.
- Marketplace, creative, and schedule rollback restored the fake provider state; concurrent rollback confirmations for creative and schedule produced one durable rollback job and one provider mutation.
- The 15-case auto-reallocation guardrail matrix passed, and concurrent auto-reallocation produced one logical action.
- The canonical one-plan storage-growth test passed with exact plan/revision/channel/job/attempt/schedule deltas and all integrity counters at zero. The Marketing Plan flow does not write filesystem artifacts, so filesystem byte deltas are not applicable.
Validation closure: API unit `312 passed`; campaign connector E2E `2 passed`; Marketing Plan core `6 passed`; complete Slice 4 final-proof matrix `28 passed`; additional rollback/crash/storage proofs `7 passed`; performance `1 passed`; web `88 passed`; desktop `4 passed`; Electron smoke passed; build, lint, format, production audit, System Doctor, Ruff, Black, mypy, migrations, and `git diff --check` passed. The split core integration command exceeded its 604-second harness timeout and is not treated as PASS.

The local deterministic hard-gate proof set is complete for Ads Slice 4. The honest boundary remains
**LOCAL PERSONAL MVP ? CONDITIONAL GO for deterministic plan execution only**;
Meta, Google, Amazon, and Flipkart are local fake-certified for the exercised
forward path, Meesho Ads is unsupported, and live providers are not validated.

## Slice 4 closure implementation update

The final closure pass now persists deterministic replacement schedule identities and replacement AdJobs in the existing Marketing Plan channel execution/AdJob tables. The previous schedule identity remains in channel history, stale executions are refused by schedule comparison, and repeated confirmations reuse the recorded operation. Budget and rollback jobs now call the existing fake Ads connector for supported Ads channels; repeated identical provider updates are no-ops, and the Meta budget rollback acceptance proves forward and reverse provider state restoration with one call each. Rollback confirmation records an idempotent rollback operation and durable rollback jobs routed through the existing Marketing worker. The integrity endpoint reports reschedule, rollback, reallocation, auto-reallocation, and usage ledger counts.

Focused core, Slice 4, durable reschedule, rollback, crash-boundary, guardrail, concurrency, and storage-integrity suites are green after these changes.
