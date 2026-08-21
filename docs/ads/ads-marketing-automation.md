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
