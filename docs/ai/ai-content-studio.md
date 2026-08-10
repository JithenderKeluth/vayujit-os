# AI Product Content + SEO Studio

## Scope and architecture

The Studio is an owner-scoped, Product-first workflow. Angular presents generation, review, comparison, bulk, SEO, localization, usage, and diagnostics views. FastAPI validates requests and persists `AIStudioGeneration`, `AIStudioJob`, `AIStudioOutput`, and immutable `GeneratedArtifact` records in PostgreSQL. The durable worker claims jobs with leases, checkpoints provider progress, retries retryable failures, and records audit/usage events. Generation never calls a marketplace connector.

The local certification path uses `deterministic_mock_v1`. The provider registry and remote-provider adapter boundary are implemented, but live remote credentials and live provider calls are deliberately outside this certification.

## Content lifecycle

1. Select a Product and Brand, then optionally select a versioned Brand Voice, Preset, and Keyword Set.
2. Queue one or more channel/content-type outputs. Each output receives an idempotency key and remains queued until a worker claims it.
3. The worker snapshots Product context, Brand Voice version, Preset version, locale, provider, model, and prompt fingerprint before creating an Artifact.
4. Review each exact Artifact version. Human edits create a new immutable Artifact version; approval and rejection are explicit. Rejection feedback can drive a new regeneration whose `parent_artifact_id` and source version preserve lineage.
5. Listing and Campaign handoffs require approved exact Artifact IDs/versions. They persist references only; publishing still occurs through the normal scheduler/connector path.

Artifacts are never overwritten. Regeneration, editing, translation, and localization create new versions/records and preserve the source relationship. Cross-channel outputs are independent: changing one channel cannot mutate another channel's content or version.

## Context and lineage

Product facts, Brand Voice, Preset, Keyword Set, tags, locale, and channel are owner-scoped. Artifact responses expose a context fingerprint and immutable lineage fields (`source_artifact_id`, `source_artifact_version`, `source_locale`, `source_product_context`, `brand_voice_version`, and `preset_version`). A later Brand Voice or Preset edit does not rewrite historical artifacts. Translation requires an approved source Artifact and an exact source version; localized generation uses current Product facts without a source Artifact.

## Durable execution, retries, and recovery

AI jobs use the shared durable-worker conventions: claim/lease, heartbeat, checkpoint, bounded retry, and terminal success/failure. A worker or API restart leaves queued/running state in PostgreSQL and allows another worker to resume safely. Idempotency is enforced at generation and job boundaries, so concurrent requests and retry delivery do not create duplicate generations, outputs, or successful audit events. Failure diagnostics expose safe category/reason codes; secrets, prompts, provider payloads, and database details are excluded from user-facing errors.

Bulk generation expands a request into independently tracked outputs. Preview validates Product/channel/content-type combinations before enqueueing. Partial failure, restart, and retry are represented per output; successful outputs are not duplicated by retry.

## SEO, Search, Tags, and Localization

SEO analysis is deterministic and advisory. It checks title/meta completeness, keyword coverage, readability, factual consistency, and channel rules. Search-volume/competition metrics are not fabricated: unavailable live-search data remains `null` with an explicit unavailable status. Analysis is tied to the requested Artifact/Product context and must be refreshed when the source version changes. Tags and Keyword Sets are normalized, deduplicated, owner-scoped, and included only through validated context.

Localization and translation preserve locale and source lineage. A translated Artifact records the exact approved source Artifact/version and source locale; cross-locale handoffs cannot silently substitute a newer or unrelated version.

## Security and privacy boundaries

Prompt-injection-like text is treated as Product content, never as instructions. Rendered content uses Angular-safe bindings; no unsafe HTML bypass is used for generated text. API responses and diagnostics do not return API keys, connector credentials, cookies, tokens, database URLs, local paths, environment values, SQL, Python tracebacks, or raw provider output. Product, Brand, Voice, Preset, Keyword, Artifact, usage, and audit data are owner-scoped. Production use still requires deployment-managed secret storage, encryption keys, backups, access control, and retention policy.

## Certification boundary

Certified locally: deterministic generation, five-channel end-to-end flow, review/edit/reject/regenerate/approve, exact-version listing and Campaign handoffs, bulk/retry behavior, localization/translation lineage, SEO safety, usage/audit/diagnostics, concurrency, worker/API restart persistence, and database integrity. Marketplace checks use fake connectors only. Remote live AI, live marketplace accounts, automated axe/browser accessibility testing, and Image Studio are not certified by this milestone.

## Operational status

- LOCAL DETERMINISTIC PROVIDER — CERTIFIED
- DURABLE AI EXECUTION — CERTIFIED LOCALLY
- REMOTE PROVIDER ARCHITECTURE — IMPLEMENTED
- REMOTE LIVE PROVIDER — NOT VALIDATED
