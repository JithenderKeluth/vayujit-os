# WP7A-3 — Defect resolution and architecture impact

Date: 2026-10-31. Final scoped browser evidence: `tmp/qa-seller-browser/95a8b3bab0282fa7/wp7a3-browser.json`; persisted regression evidence: `tmp/qa-wp7a3-backend/431e5e4d04a84f79/backend-results.xml` (94 passed). Historical failures remain available; they are not overwritten by successful retests.

## Confirmed application defects

| Stable ID / priority | Root cause and observed evidence | Smallest correction | Retest disposition |
| --- | --- | --- | --- |
| SE-WP7A3-CONTENT-001 / P2 | `ai/provider.py` passed product/brand punctuation directly into keywords, violating `ProductContent`'s existing pattern/length contract. A non-DB reproduction identified `keywords[0/1]` pattern errors; the initial browser stayed on generation with no artifact. | Normalize only mock keywords to the existing supported syntax/length, retaining original product/brand identity elsewhere. Do not relax validation of provider output. | RESOLVED_BOUNDED: five punctuation/Unicode/length cases plus unsafe-output rejection; L-09 passes 4/4. |
| SE-WP7A3-STUDIO-001 / P1 | AI Studio kept a transient queued response, had no persisted job refresh/retry path and lost job identity on reload. Initial L-10 could see backend failure but no seller-visible failure. | Preserve generation ID in the route; query existing owner-scoped status API; expose status/failure and existing recovery API. Retry each exact failed job, not the first generation job repeatedly. Busy guard prevents in-flight duplicate UI requests. | RESOLVED_BOUNDED: provider failure → failed → HUMAN retry → completed, identical request replay, refresh/reload and persisted outputs, 4/4 browsers. Changed-product/superseded permutations remain a coverage gap. |
| SE-WP7A3-CONTENT-002 / P2 | `AIArtifactComponent.saveEdit()` ignored the new revision response and reloaded the old source route. | Navigate to the returned revision identity, reload its canonical projection and send `expected_source_version`. Preserve query context; do not mutate the source. | RESOLVED: L-11 4/4; source content unchanged, new draft pending review, stale version409; Angular service/navigation regressions. |
| SE-WP7A3-IMAGE-001 / P1 | Image review had no image preview, displayed missing size as zero/requested dimensions as actual, and ignored the identity returned by regeneration. Static contract inspection confirmed these omissions; the initial before browser did not reach populated image review because its media locator was wrong. | Render the existing private media preview, show UNKNOWN for absent actual facts, disable unseen-output approval, follow the actual queued child identity after regeneration. | RESOLVED_BOUNDED: populated private preview, anonymous401, exact HUMAN approval/reload and child lineage/unapproved state in all four browser contexts. Before populated screenshot is not claimed. |
| SE-WP7A3-IMAGE-BULK-001 / P1 | `queue_generation(commit=False)` queried planned outputs before flushing them. The actual application session has `autoflush=False`; older fixtures used autoflush=True and missed this. Real UI bulk enqueue failed after a valid plan. | Flush planned rows within the existing transaction before building the response. No new commit, worker path, fabricated output or verification bypass. | RESOLVED: regression explicitly uses the real no-autoflush setting; bulk enqueue/replay and actual worker output identities pass; L-14 positive path 4/4. |
| SE-WP7A3-IMAGE-BULK-002 / P2 | Bulk operation status was memory-only. Earlier assertion checked API persistence but did not prove UI reload recovery. The retained reload screenshot returned to the empty planning form. | Persist operation ID in the URL; restore through existing owner-scoped status API; provide explicit status refresh and fail visibly on invalid context. | RESOLVED_BOUNDED: strengthened L-14 asserts completed UI status both before and after reload, 4/4. Unit tests cover exact restore, missing context and duplicate enqueue guard. |
| SE-WP7A3-CONTENT-003 / P1 | The human-edit duplicate check was not serialized. Actual concurrent identical requests returned200/200 and created two revisions. | Lock the exact owned source row before duplicate-edit/stale checks and revision creation, using existing SQLAlchemy transaction semantics. Preserve one200 and conflicting409; approved-source edits still409. | RESOLVED: real PostgreSQL concurrent regression passes in final94; source immutable and approval boundary preserved; browser revision journey4/4. This is not a proof for every other independent version writer. |
| SE-WP7A3-IMAGE-002 / P1 | Decision POST returns an output summary, but the UI assigned it as rich review detail; Angular then read absent `lineage.length`/readiness. Before traces contain TypeError despite earlier assertions passing. | After the existing approval/rejection POST, reload the exact canonical rich projection instead of rendering a mismatched response type. | RESOLVED: summary-only response regression; final L-12 and global scan checks reject runtime TypeError/page errors and pass4/4. |
| SE-WP7A3-CAMPAIGN-001 / P2 | A second checkpoint using the already-used sequence reached the database unique constraint and returned500. Sanitized evidence identifies SQLSTATE23505 and `campaign_activities`, not a provider/gateway fault. | Reuse `owned_campaign(..., lock=True)`; check the sequence within that lock and return actionable409. Keep the unique constraint and explain unused sequence in the form. | RESOLVED_BOUNDED: concurrent duplicate sequence gives201/409; replay409; one persisted activity. Browser uses explicit sequences1/2, saves dependency and reloads it4/4. |

No destructive migration, ownership-model change, duplicate approval authority, provider authorization or monetary arithmetic change was introduced. `ck_users_single_owner` is preserved. Real providers, publishing, scheduling, supplier actions and marketplace writes were not enabled.

## Application files changed by this package

- `apps/api/vayujit_api/ai/provider.py`
- `apps/api/vayujit_api/ai/image_service.py`
- `apps/api/vayujit_api/ai/studio_router.py`
- `apps/api/vayujit_api/campaigns/activity_service.py`
- `apps/web/src/app/ai/ai-studio.component.ts`
- `apps/web/src/app/ai/ai-artifact.component.ts`
- `apps/web/src/app/ai/ai-image-review.component.ts`
- `apps/web/src/app/ai/ai-image-bulk.component.ts`
- `apps/web/src/app/ai/ai.service.ts`
- `apps/web/src/app/campaigns/activity-form.component.ts`
- `packages/shared/src/index.ts`

## Test and harness corrections

New tests: `apps/api/tests/test_seller_wp7a3.py` (nine cases including parameterization); `apps/web/src/app/ai/ai-wp7a3.spec.ts`; `ai-image-review.component.spec.ts`; `ai-image-bulk.component.spec.ts`; one addition to `ai.service.spec.ts`. Thirteen Angular tests were added overall (387 → 400). Existing bulk-image and Studio E2E modules explicitly import their intended `test_ai_integration.client` fixture so their global worker factory and HTTP client cannot resolve to different fixtures. This fixes fixture identity, not application assertions.

New scoped harness: `qa/wp7a3-browser.mjs`, `wp7a3-safety.mjs`, `wp7a3_fixture.py`, `wp7a3-audit.mjs`, `wp7a3-gate.mjs`, `wp7a3_infrastructure.py`, `wp7a3_final_audit.py`, three Node test files, and `scripts/test-seller-wp7a3.ps1`. Shared integration changes: `qa/fixture_server.py`, `server.mjs`, `safety.mjs`, `seller-browser-session.mjs`, `seller-browser-explore.mjs`, `wp7-run.mjs`, `wp7a_fixture.py`, `wp7a2_fixture.py`, `wp4_final_audit.py`.

QA-only corrections retained in evidence: media upload already navigates to detail; image generation GET expects the studio generation ID; SEO analyze returns201, not200; wrapping select labels include option text; waiting for the first recovery POST is not waiting for all failed outputs to be requeued. Browser assertions now wait for the complete UI operation and reject runtime errors. Mixed QA/API Black checks explicitly select `apps/api/pyproject.toml` rather than switching formatting configuration by common parent directory.

## Open findings

The nine repairs above have bounded retests; this does not close all application operations. SE-WP7-COVERAGE-001/P1 remains open. Exact remaining entries and dependencies are in the new matrix addendum/JSON. Historical Ads502 remains unreproduced/unclassified. Eighteen axe incomplete occurrences and broader manual keyboard/state permutations remain unverified. No unrelated historical finding is silently resolved.
