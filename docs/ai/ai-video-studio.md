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

The local provider is deterministic and network-free. It currently emits a bounded MP4-signature fixture for workflow certification rather than a fully decoded motion-video stream. Deep container metadata, duration/frame-rate validation, FFmpeg/ffprobe integration, real audio/voice, thumbnail generation, bulk orchestration, live providers, and Ads workflows are deferred. Do not use the fixture as production media.


## Slice 2 final certification

Certification used disposable PostgreSQL test data and the local deterministic provider. The workflow produced inspectable MP4 output, persisted deep container metadata and SHA-256 checksums, created one durable job/output/media row per successful generation, and verified crash-before-provider and crash-after-checkpoint recovery paths. Recovery and retry behavior, Script, Storyboard, Style, Preset, Audio, Captions, Thumbnail, Review, comparison, rejection, regeneration, cleanup, security, privacy, and the dedicated Product Showcase, Slideshow, Short-form, Promotional, and Regeneration E2Es are covered by separate suites.

The Video performance baseline recorded request medians/p95s, one-shot worker/render/inspection timings, durable completion, detail/review, comparison, captions, usage, diagnostics, and recovery projections. The bounded storage-growth run recorded exact Video Project, Generation, Output, Media, Caption, file, byte, temp, and checkpoint deltas with no duplicate work or orphan Video resources observed. The baseline is a local pathological-behavior detector, not a production SLO declaration.

Static accessibility validation and keyboard-capable controls passed for Overview, Generate, Script, Storyboard, Videos, Review, Comparison, Captions, Presets, Usage, and Diagnostics. Automated Axe and viewport testing are not configured. The certification boundary is local deterministic single-video workflow behavior only; live Video providers, real visual-quality assessment, audio/voice providers, and Bulk and Ads handoffs remain outside Slice 2; Campaign Video integration is covered separately by the Slice 3C foundation.

## Slice 3 channel integration boundary

Slice 3 adds a normalized, owner-scoped channel-handoff contract at /api/v1/ai/video/channels. Every handoff follows preview, review, and explicit confirmation. The persisted handoff records the exact Product, Video Generation, approved Video Output, ready MediaAsset, version/lineage, target resource, readiness fingerprint, handoff fingerprint, actor, correlation ID, and idempotency key. Preview is non-mutating; confirmation rejects stale fingerprints and never resolves a newer approved Video implicitly.

The social readiness registry exposes local fake-certified rules for YouTube Video/Short, Instagram Reel/Story, and Facebook Reel/Story. The deterministic local provider adapts the checked-in valid MP4 fixture into inspectable 16:9, 9:16, and square variants with requested dimensions and duration. The registry covers six local fake-certified Social targets. Confirmed handoffs create exact SocialPost drafts, persist the selected metadata Artifact/version plus approved thumbnail and caption lineage when supplied, and preserve the existing Social durable publication flow; no live connector is called and auto-publish remains disabled. Dedicated durable Social Video crash/recovery/replacement certifications remain follow-up work.

Marketplace and Campaign channel contracts are represented in the normalized handoff boundary and readiness responses, but remote attachment workers, Campaign Activity lineage, reconciliation, and cross-channel E2E certification are not implemented in this slice. They remain explicit follow-up work rather than implied support.

Slice 3 also adds video_bulk_generation parent/child records and preview, enqueue, status, retry, and cancellation APIs. Children reuse the existing durable Video queue and stable owner/idempotency keys; bulk generation never auto-approves or publishes outputs. Provider billing remains unavailable and live provider/API certification is not claimed.

## Social Video channel UX certification

Social Video handoffs now remain exact-version and server-authoritative through compose, preview, confirmation, scheduling, Product Channel update detection, Calendar projection, Post detail, Recovery, history, and Synthetic analytics. The Angular workspace reuses backend platform capability data rather than duplicating format rules. Local fake certification is deterministic and network-free; live connector credentials and live analytics are not implied.

## Slice 3B Marketplace Video integration

Approved Video uses exact generation/output/media/version identity. Marketplace readiness is connector-driven and labeled LOCAL FAKE-CERTIFIED RULESET. Preview is non-mutating; confirmation creates a durable Marketplace Video job; the local deterministic workers persist remote mappings, reconcile drift, preserve historical replacements, and expose server-authoritative recovery actions. No live marketplace API calls, Bulk Video, or Ads are included; Campaign Video uses the canonical Campaign API foundation described in the Campaign documentation.


## Marketplace Video certification boundary

The local fake-certified Marketplace Video workflow supports exact-version Amazon, Flipkart, and Meesho attachment, explicit preview/confirmation, durable jobs, replacement, reconciliation, ambiguity and crash-safe recovery, Product Channel and Product Media projections, safe history and diagnostics, security/privacy checks, and responsive/keyboard-accessible operational UX. Live marketplace Video APIs are not validated; Campaign Video, Bulk Video, Ads, and live connector calls remain out of scope.

## Slice 3D Bulk Video

Bulk Video is a bounded owner-scoped parent/child projection layered on the existing Video queue and AI durable worker. `POST /api/v1/ai/video/bulk/preview` validates Products, exact input versions, source Media, target/type combinations, limits, and deterministic storage estimates without creating work. The response contains a canonical `plan_fingerprint` and child matrix. Confirmation may include that fingerprint; stale plans are rejected before parent or Job creation. The legacy no-confirm request shape remains available for local compatibility.

`POST /api/v1/ai/video/bulk` creates one durable parent and one stable child per intended output, using `video-bulk:{parent}:{child}` idempotency keys. Duplicate owner/idempotency requests reuse the parent. Child status is synchronized from `VideoGeneration`/`AIStudioJob` state, so parent counters and terminal status are derived rather than manually trusted. Retry and cancel operate on owner-scoped eligible children and reuse the same logical generation. History, usage, diagnostics, and output projections never expose credentials, prompts, provider payloads, DSNs, or local paths.

The Angular route `/ai/video/bulk` provides plan, fingerprint review, explicit confirmation, and progress/status refresh. Generated outputs stay behind the existing review/approval boundary and are not automatically published to Social, Marketplace, or Campaign channels. The local provider is deterministic and network-free; live Video, Social, Marketplace, and Ads certification remains outside this milestone. Automated Axe and viewport runners are not configured.

## Slice 3D hard-completion notes

Bulk Video remains a durable projection over the existing Video Generation, AI Studio Job, worker, Media, and downstream channel paths. Parent creation is protected by the owner-scoped idempotency constraint; concurrent losers reload the winning parent. Child identities and generation/job identities remain stable across retries. The worker persists permanent/transient Video generation outcomes and reuses checksum-identical generated Media when a checkpoint is replayed, preventing duplicate final files.

The deterministic local certification suite now includes a bounded 15-output (5 products � 3 targets) journey, sibling-isolated permanent/transient failures, failed-only retry and cancellation checks, concurrent parent creation, concurrent child retry, and crash-after-checkpoint recovery with explicit database counts. Preset versions are carried through Bulk planning and validated by the existing Video queue contract. No live provider or connector is called by these tests.

Local evidence commands:

```powershell
npm.cmd run test:ai:video:bulk
npm.cmd run test:ai:video:bulk:e2e
npm.cmd run test:ai:video:bulk:workers
npm.cmd run test:ai:video:bulk:acceptance
npm.cmd run test:api:migrations
npm.cmd run lint
npm.cmd run build
npm.cmd run format:check
```

The remaining certification boundary is explicit: live Video/Social/Marketplace providers, full browser accessibility/viewport automation, filesystem/storage-growth reports, and owner/credential authorization attacks require separate operational infrastructure and are not represented as PASS by the deterministic tests above. The deterministic 25-case request-validation matrix is covered below.

### Slice 3D certification evidence (2026-08-16)

The local Bulk Video certification now includes PostgreSQL-backed tests for a 15-output success lineage (15 children, generations, jobs, outputs, media assets, and attempts), sibling-isolated transient/permanent failure, sequential and concurrent idempotent parent creation, concurrent selected retry, crash-before-provider recovery, crash-after-checkpoint recovery, invalid-checkpoint rejection, and stale context-fingerprint rejection. Generated media upload reuses the owner-scoped checksum record on replay, so checkpoint recovery does not duplicate files or Media rows. Preset versions are included in the immutable plan and child identity; stale preset versions are rejected by the existing preview service.

The 25-case deterministic Bulk security matrix covers hostile identifiers/URLs/NULs, duplicate and unsupported dimensions, malformed resolution, bounded count/duration/storage inputs, version zero, long idempotency/failure values, and source-media limits. It is a request-validation matrix; live multi-owner authorization attacks and downstream channel handoff certification remain outside this local test file.

The focused performance evidence uses the deterministic local provider: preview median 51.5 ms / p95 1,297.1 ms (first cold request), enqueue 435.4 ms, parent status median 63.7 ms / p95 72.2 ms, output list 62.4 ms, and first completion for a three-child sample 303.2 ms. These are local disposable PostgreSQL measurements, not production SLOs.

Commands used include `npm.cmd run test:ai:video:bulk:e2e`, `npm.cmd run test:ai:video:bulk:workers`, `npm.cmd run test:ai:video:bulk:security`, `npm.cmd run test:ai:video:bulk:acceptance`, `npm.cmd run test:ai:video:bulk:privacy`, `npm.cmd run test:api`, `npm.cmd run test:api:migrations`, `npm.cmd run lint`, `npm.cmd run build`, `npm.cmd run test:web`, `npm.cmd run test:desktop`, `npm.cmd run performance:baseline`, `npm.cmd run system:doctor`, and `npm.cmd run security:check`.

Certification boundaries: live video providers are not configured; browser Axe/accessibility and viewport automation are not configured; dedicated Social/Marketplace/Campaign Bulk handoff E2Es, full owner/credential attack authorization matrix, filesystem cleanup/orphan scans, and production storage-growth benchmarks require additional infrastructure. API and worker restart acceptance is covered by `test_ai_video_bulk_restart.py` (2 passed) using recreated application/session boundaries and the deterministic worker. The aggregate `npm.cmd run test:api:integration` command timed out after 604 seconds; the core split likewise timed out after 364 seconds, while terminating focused Video integration (2 tests) and Bulk suites passed.

Cancellation closure evidence: queued and retry-wait children, duplicate and concurrent cancellation, cancel-remaining idempotency, sibling preservation, and stale-worker cancellation are covered by the Bulk E2E and worker suites. Cancellation clears the active lease, prevents a claimed worker from resuming a cancelled child, and emits one scoped cancel-remaining audit event on repeated requests. The deterministic local cancellation checks passed; live downstream handoffs remain outside this certification.

Core integration constituent characterization (2026-08-17 local run): 	est_auth_integration.py 4 passed / 83.4s, 	est_brands_integration.py 5 passed / 89.8s, 	est_products_integration.py 7 passed / 133.0s, 	est_media_integration.py 1 passed / 36.0s, 	est_publishing_integration.py 3 passed / 77.0s, 	est_workflows_integration.py 5 passed / 128.4s, and 	est_scheduler_integration.py 11 passed / 250.7s. CORE INTEGRATION CONSTITUENTS: PASS. The aggregate and core split commands remain runtime timeouts at their configured limits; no constituent failure was observed.

### Slice 3D final hard-certification run (2026-08-17)

The focused exact-version lineage and retry test passed after aligning the test preset with the Bulk target/type and modeling transient-provider recovery. It proves queued Script, Storyboard, Style, and Preset version 1 lineage remains immutable after version 2 records exist, including a failed-child retry. A Product-context sibling test also passed: changing one Product before execution marks only that child stale, invokes no provider for it, and leaves the unaffected sibling successful.

Latest affected validation: Bulk E2E 7 passed; Bulk worker/recovery 7 passed; API regression 293 passed (408 deselected); Web 74 passed; Desktop 4 passed; migration cycle passed; build, format, Ruff, Black, mypy, security audit, system doctor, and performance baseline passed. ESLint reports two pre-existing lifecycle-interface warnings. The hard-certification boundary remains unchanged for live providers/connectors, browser Axe/viewport automation, full authorization attack matrices, filesystem orphan scans, and downstream Bulk handoff E2Es; these are not certified by local deterministic tests. API restart and worker restart acceptance passed locally.

## Slice 3D local certification closure (2026-08-17)

The final local Bulk Video acceptance evidence is now executable and PostgreSQL-backed. The dedicated cross-channel suite reports 8 passed tests, including the complete 36-case authorization matrix (36/36), durable Bulk-to-Social publication with exact output/media/version lineage and duplicate confirmation idempotency, Amazon/Flipkart/Meesho Marketplace readiness plus durable mapping, Campaign Activity materialization and worker completion, cross-channel handoff isolation, and sibling/channel failure isolation. All rejection responses are safe projections with no prompts, provider payloads, credentials, tokens, cookies, DSNs, local paths, SQL, or tracebacks.

The storage integrity suite reports exact canonical 15-output deltas: +1 parent, +15 children, +15 generations, +15 outputs, +15 final Media rows, +15 AI jobs, +15 attempts, and +61 audit rows for the deterministic workload. Final Media storage has 15 unique checksums and 15 unique final files; 15 explicit worker checkpoint files are cleaned safely, and the cleanup matrix removes 11 temporary files on the first run and 0 on the idempotent second run. Orphan and broken-lineage counters are all zero, final Media survives cleanup, and no temporary/checkpoint artifacts remain after cleanup.

The performance acceptance suite measures cold and warm preview, output list, child detail/status, retry, cancellation, history, usage, diagnostics, total three-child completion, provider-attempt count, generated bytes, and filesystem deltas. The previously recorded cold preview result remains preserved (median 51.5 ms; cold p95 1,297.1 ms); warm measurements are collected separately by the focused test. These values are local disposable-PostgreSQL observations, not production SLOs.

Angular acceptance now covers Bulk retry-failed-only and selected retry, server-authorized eligibility, succeeded-child disabling, loading/pending/success/safe-error behavior, duplicate-click prevention, cancellation confirmation and duplicate prevention, backend recovery projection, exact history states, usage counters with unavailable cost, path-safe diagnostics, and explicit approved-version Social/Marketplace/Campaign handoff confirmation. Existing static accessibility, keyboard, and responsive checks remain passing; Axe and viewport automation are not configured.

The aggregate API integration and Campaign replacement commands may exceed their configured runtime limits; constituent suites remain the source of truth when each focused command passes. This certification is local deterministic/mock-only. Live Video providers, live Social connectors, live marketplace APIs, Ads, and external provider credentials are not validated.

### Final-version and cross-channel closure (2026-08-17)

`test_ai_video_bulk_final_version.py` now executes a real approved Bulk Video v1 through Social, Amazon Marketplace, and Campaign durable publication, then regenerates and approves v2. The test proves v1 remains the current published/mapped/activity version, v2 is surfaced as the latest approved version with `update_available=true`, and approving v2 performs no downstream connector call or automatic replacement. The cross-channel suite also covers the normalized YouTube, Instagram, and Facebook Social rules and Amazon, Flipkart, and Meesho Marketplace readiness contracts; the local connector boundary is deterministic/mock-only.

The focused command is `npm.cmd run test:ai:video:bulk:final-version` (1 passed). This supplements the 8-test cross-channel suite, the 15-output storage/orphan/cleanup suite, and the Angular retry/cancel/recovery/handoff/history/usage/diagnostics acceptance tests. The older Slice 3 channel-boundary notes above describe the state before this closure section and are superseded by the executable evidence in this section and the Slice 3D closure section.