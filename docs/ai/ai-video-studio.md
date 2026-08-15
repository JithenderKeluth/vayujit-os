# AI Video Studio

AI Video Studio is an owner-scoped, durable single-video workflow. It reuses the existing AI durable-job worker, Media storage, approval events, and audit records.

## Slice 2 lifecycle

1. Choose an exact approved Product and Content Artifact version.
2. Create or edit a versioned Storyboard, optionally selecting a versioned Video Style and Video Preset.
3. Preview the request; the response includes the exact source lineage and context fingerprint.
4. Queue a durable Video Generation. Duplicate owner/idempotency requests reuse the original generation.
5. The worker validates the captured context before provider execution, checkpoints output, verifies checksum, and persists a Media-backed output.
6. Review the generated output, compare generations, add captions, approve or reject, and regenerate from a rejected generation with an explicit reason.
7. Export approved caption tracks as plain text or WebVTT.

All queue and approval operations are owner-scoped, exact-version checked, row-version checked, and safe to retry. Rejection and stale-context failures expose taxonomy codes and safe messages without prompts, provider credentials, local paths, or database details. Crash-before-provider and crash-after-checkpoint recovery use the existing durable worker lease/checkpoint path.

## API surface

- `GET /api/v1/ai/video/diagnostics`
- `POST /api/v1/ai/video/preview`
- `POST /api/v1/ai/video/queue`
- `GET /api/v1/ai/video/generations`
- `GET /api/v1/ai/video/generations/{generation_id}`
- `POST /api/v1/ai/video/generations/{generation_id}/approve`
- `POST /api/v1/ai/video/generations/{generation_id}/reject`
- `POST /api/v1/ai/video/generations/{generation_id}/regenerate`
- `GET /api/v1/ai/video/generations/compare`
- `GET/POST /api/v1/ai/video/storyboards`
- `GET/PATCH /api/v1/ai/video/storyboards/{storyboard_id}`
- `POST /api/v1/ai/video/storyboards/{storyboard_id}/approve`
- `POST /api/v1/ai/video/storyboards/{storyboard_id}/preview`
- `GET/POST /api/v1/ai/video/presets`
- `GET/POST /api/v1/ai/video/styles`
- `POST/GET /api/v1/ai/video/captions`
- `POST /api/v1/ai/video/captions/{caption_id}/approve`
- `GET /api/v1/ai/video/captions/{caption_id}/export`

The existing AI Content generation API remains the source of approved script/content artifacts; this slice does not add a second script generator or duplicate ORM models.

## Validation

Focused Slice 2 acceptance covers storyboard version and approval safety, exact generation lineage, rejection and regeneration, caption locale/format validation, compare/version safety, exact unapproved-artifact rejection, and stale-context rejection before provider execution. Existing Video unit, integration, worker, E2E, and security suites remain separate commands.

## Operational UI and certification boundary

The Angular Video workspace now provides authenticated owner-scoped Overview, 14-step Generate, Storyboards, Videos, Review, Presets, Captions, Usage, and Diagnostics views. It uses server-owned Video API data, native accessible controls, keyboard-capable buttons, responsive grids, contained table scrolling, safe Media-backed playback, and duplicate-submit protection. Local metrics show `Unavailable` when cost or provider telemetry is unknown. Static accessibility and responsive review are source-level certifications; automated Axe and viewport runners are not configured.

## Explicit limitations

The local provider is deterministic and network-free. It currently emits a bounded MP4-signature fixture for workflow certification rather than a fully decoded motion-video stream. Deep container metadata, duration/frame-rate validation, FFmpeg/ffprobe integration, real audio/voice, thumbnail generation, bulk orchestration, social/marketplace/Campaign handoff, live providers, and Ads workflows are deferred. Do not use the fixture as production media.


## Slice 2 final certification

Certification used disposable PostgreSQL test data and the local deterministic provider. The workflow produced inspectable MP4 output, persisted deep container metadata and SHA-256 checksums, created one durable job/output/media row per successful generation, and verified crash-before-provider and crash-after-checkpoint recovery paths. Recovery and retry behavior, Script, Storyboard, Style, Preset, Audio, Captions, Thumbnail, Review, comparison, rejection, regeneration, cleanup, security, privacy, and the dedicated Product Showcase, Slideshow, Short-form, Promotional, and Regeneration E2Es are covered by separate suites.

The Video performance baseline recorded request medians/p95s, one-shot worker/render/inspection timings, durable completion, detail/review, comparison, captions, usage, diagnostics, and recovery projections. The bounded storage-growth run recorded exact Video Project, Generation, Output, Media, Caption, file, byte, temp, and checkpoint deltas with no duplicate work or orphan Video resources observed. The baseline is a local pathological-behavior detector, not a production SLO declaration.

Static accessibility validation and keyboard-capable controls passed for Overview, Generate, Script, Storyboard, Videos, Review, Comparison, Captions, Presets, Usage, and Diagnostics. Automated Axe and viewport testing are not configured. The certification boundary is local deterministic single-video workflow behavior only; live Video providers, real visual-quality assessment, audio/voice providers, and Social, Marketplace, Campaign, Bulk, and Ads handoffs remain outside Slice 2.

## Slice 3 channel integration boundary

Slice 3 adds a normalized, owner-scoped channel-handoff contract at /api/v1/ai/video/channels. Every handoff follows preview, review, and explicit confirmation. The persisted handoff records the exact Product, Video Generation, approved Video Output, ready MediaAsset, version/lineage, target resource, readiness fingerprint, handoff fingerprint, actor, correlation ID, and idempotency key. Preview is non-mutating; confirmation rejects stale fingerprints and never resolves a newer approved Video implicitly.

The social readiness registry exposes local fake-certified rules for YouTube Video/Short, Instagram Reel/Story, and Facebook Reel/Story. The deterministic local provider adapts the checked-in valid MP4 fixture into inspectable 16:9, 9:16, and square variants with requested dimensions and duration. The registry covers six local fake-certified Social targets. Confirmed handoffs create exact SocialPost drafts, persist the selected metadata Artifact/version plus approved thumbnail and caption lineage when supplied, and preserve the existing Social durable publication flow; no live connector is called and auto-publish remains disabled. Dedicated durable Social Video crash/recovery/replacement certifications remain follow-up work.

Marketplace and Campaign channel contracts are represented in the normalized handoff boundary and readiness responses, but remote attachment workers, Campaign Activity lineage, reconciliation, and cross-channel E2E certification are not implemented in this slice. They remain explicit follow-up work rather than implied support.

Slice 3 also adds video_bulk_generation parent/child records and preview, enqueue, status, retry, and cancellation APIs. Children reuse the existing durable Video queue and stable owner/idempotency keys; bulk generation never auto-approves or publishes outputs. Provider billing remains unavailable and live provider/API certification is not claimed.

## Social Video channel UX certification

Social Video handoffs now remain exact-version and server-authoritative through compose, preview, confirmation, scheduling, Product Channel update detection, Calendar projection, Post detail, Recovery, history, and Synthetic analytics. The Angular workspace reuses backend platform capability data rather than duplicating format rules. Local fake certification is deterministic and network-free; live connector credentials and live analytics are not implied.
