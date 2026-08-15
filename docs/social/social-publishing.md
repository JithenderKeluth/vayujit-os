# Social Content and Multi-Channel Publishing

## Architecture

Social publishing is owner-scoped and local-first. It reuses canonical Brands, Products, approved Content Artifacts, approved Media Assets, Campaign Activities, the PostgreSQL scheduler, durable publishing jobs/attempts, lease recovery, and the existing worker runtime. Instagram, Facebook, and YouTube are represented by the server-driven platform registry; no second Campaign or scheduler subsystem exists.

The deterministic `social_fake` connector is network-free and supports success, processing, rejected, throttled, timeout, ambiguous-result, credential, policy, unavailable, and remote-missing scenarios. The current milestone certifies deterministic local behavior, not live platform connectivity.

## Accounts and credential model

`social_accounts` stores platform identity, capabilities, validation state, and a write-only encrypted credential reference. Create, validate/revalidate, enable, disable, credential replacement, and archive are owner-scoped. Credential replacement increments `credential_version`, resets validation to `unknown`, and emits metadata-only audit events. API responses, history, worker logs, analytics, and recovery projections never return credentials or raw payloads. Disabling or archiving blocks new worker publication while retaining historical posts, remote IDs, metrics, Campaign links, and Audit events.

## Formats and exact-version semantics

Each SocialPost records platform, format/content type, account, exact approved Content Artifact ID/version, selected Media IDs, locale, Campaign, correlation ID, schedule, timezone, and idempotency key. A later approved Artifact or Media version never changes an existing post. Repurposing records `source_artifact_id` and `source_artifact_version`; generated text is independent per target platform and does not invent views, CTR, ranking, engagement guarantees, follower growth, or sales promises.

## Lifecycle, preview, approval, and scheduling

The lifecycle is draft -> preview -> approved -> scheduled -> publishing -> published, with failed, cancelled, and reconciliation states. Preview is non-mutating and returns platform-specific metadata, readiness blockers/warnings, exact identity, schedule information, and a confirmation fingerprint. Scheduling and Publish Now require that fingerprint. Publish Now creates a durable schedule/job; it never calls a connector synchronously.

DST gap and fold handling uses the existing scheduler timezone utilities. Local wall times are converted to UTC only after validation, with explicit fold selection for overlaps.

## Durable workers and exactly-once behavior

The existing worker claims leases and records attempts. A remote identity checkpoint is committed before local finalization. A lease-loss restart finalizes from that checkpoint without a second connector call. Idempotency is enforced by SocialPost identity, Publishing job identity, and fake connector remote logical publication tracking. A stale worker cannot finalize after lease loss.

Ambiguous outcomes are reconciled before retry. If the remote identity exists, reconciliation finalizes the same publication; if it is missing, only then is a retry eligible. Recovery projection exposes safe failure codes/messages and retry, reconcile, or cancel actions.

## Campaign integration and readiness

A Campaign-linked SocialPost projects into the real `CampaignActivity` model. The projection persists SocialPost ID, exact Artifact/version, Media IDs, platform, account, format, schedule, timezone, correlation ID, dependency policy, readiness, status, job, attempt, and execution linkage. Campaign dependency/readiness/completion/failure/recovery semantics remain canonical.

## Unified Calendar and Product Channel

`GET /api/v1/social/calendar` returns normalized event type, platform/channel, Brand, Product, Campaign, status, local/UTC datetime, timezone, readiness, and failure state. Filters compose by Brand, Product, Platform, Channel, Campaign, Status, and date range. Existing Campaign and marketplace calendar projections remain the source for their own activity types; the Angular Calendar presents them with Social items in the same operating view. Product Channel Social projections expose platform posts, exact versions, update availability, latest publication, next schedule, failures, metrics availability, warnings, and blockers.

## Repurposing and bulk generation

Repurposing is lineage-preserving and platform-specific. Durable AI bulk generation is reused for Social channels: a 5-Product x Instagram/Facebook request creates ten stable logical child outputs, one parent operation, and one durable AI job per child. Parent/child status, partial failure, retry-failed-only, selected retry, cancellation, restart recovery, idempotency, and owner scope are inherited from the AI bulk architecture. Social channels use bounded deterministic generator rules; no Social-specific bulk engine is introduced. Approved SocialPosts can then be scheduled through the existing bulk scheduling endpoint.

## Metrics and analytics

Metrics use explicit availability states: `available`, `unavailable`, `not_supported`, and `not_synced`. Unknown values remain null rather than zero. Fake connector metrics carry `source=synthetic_test_data`; analytics only aggregates available numeric values and exposes platform/Brand/Product/Campaign/content-type/date filters.

## Privacy and security

AI context and connector payloads are Social-only and exclude buyer identity, orders, payments, settlements, marketplace credentials, AI credentials, database DSNs, local paths, and unrelated Product data. Captions, titles, hashtags, CTA values, hostile markup, prompt injection, and credentials are treated as untrusted data. Destination URLs require HTTPS, reject credentials, localhost, loopback, link-local, reserved, and private IP targets, and are never fetched for validation. Cross-owner account, post, Artifact, Media, bulk, recovery, and history access returns safe not-found/forbidden behavior.

## Performance and validation

Measure enqueue latency separately from fake connector publication, checkpoint persistence, reconciliation, and metrics synchronization. The repository includes focused Social unit, integration, worker, E2E, recovery, bulk, security, and acceptance suites plus Ruff, Black, mypy, Angular, Electron, migration, security, System Doctor, performance, and diff checks.

## Fake certification boundary

This milestone certifies deterministic local workflow behavior only. It does not claim live Instagram/Facebook/YouTube connectors, platform-policy approval, pixel-perfect previews, real engagement analytics, video generation, Ads, or production credentials. Future connectors can be added through the typed platform/connector registry without changing canonical Product, Campaign, Artifact, or Media models.



## Slice 3A final Social Video UX certification

The Social workspace now presents owner-scoped connected accounts, ready/draft/scheduled/published/failed/recoverable Video post counts, upcoming schedules, recent posts and failures, and a clearly labelled Synthetic analytics boundary. The compose wizard is a ten-step, keyboard-capable flow for platform, backend-declared format, Product/Brand, approved Video, metadata Artifact, thumbnail, Caption Track, account, publish/schedule, and final confirmation. Every review surface shows exact IDs and versions; newer versions are never substituted.

Post detail shows Product, Video output/version, metadata, thumbnail, captions, account, status, remote ID, correlation ID, and a safe chronological history. Recovery actions are rendered only from the backend projection and require confirmation. Calendar and Product Channel routes reuse the existing Social API projections. Empty, loading, retry, disabled-account, and safe-error states are explicit.

Static accessibility certification: PASS for semantic headings, labels, fieldsets, native controls, tables, status/alert text, keyboard navigation, and non-color-only state cues. Automated axe: NOT CONFIGURED. Static responsive certification: PASS at 390px, 768px, and 1280px+ through fluid grids, wrapped actions, stacked forms, contained tables, and responsive detail layouts. Automated viewport harness: NOT CONFIGURED.

Deterministic local Social Video timing samples (disposable PostgreSQL, five warm samples unless noted): readiness 15.1ms median / 15.8ms p95; handoff preview 18.1ms / 20.1ms; handoff confirmation 24.8ms (single mutation sample); SocialPost detail 11.0ms / 12.9ms; schedule creation 65.5ms (single mutation sample); Product Channel 13.1ms / 14.6ms; Calendar 13.3ms / 14.5ms; history 13.3ms / 14.5ms; metrics 14.7ms / 15.1ms; analytics 12.0ms / 12.5ms; Recovery 11.9ms / 12.1ms; replacement-preview request 15.1ms / 17.2ms. These are local deterministic observations, not production SLOs.

The bounded benchmark created one disposable SocialPost and one schedule, with zero jobs, attempts, metrics, duplicate rows, orphan rows, or fake remote publications. Development data is reset through the test-database safety guard. The local certification covers fake connector behavior only; live Instagram, Facebook, and YouTube connectors and live analytics remain outside this milestone.
