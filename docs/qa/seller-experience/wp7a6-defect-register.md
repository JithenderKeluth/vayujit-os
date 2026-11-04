# WP7A-6 defect and gap register

## WP7A6-D01 — Amazon incomplete-listing review (P1)

Confirmed by a schema-valid persisted test: readiness false/media_missing but review returned 200. Initial test run 57c2123925eb489f: 1 pass/1 fail. Root: amazon_router.review_listing and issue_listing_execution_authorization did not consult existing listing_readiness. Minimal fix reuses it at both boundaries; no new authority or schema. Rejections expose only JSON-safe blocking issues. The first guard returned nested UUIDs in HTTPException.detail, causing a 500; retained browser evidence caught it and the response was corrected to code + blocking issues. Final focused run 5740623d2b3c4fc8: 3 passed, including removal of a real synthetic persisted price after review; final four-context browser rejection passed as a subcheck. Historical approvals remain unchanged; no live submission. **Resolved for tested missing-readiness behavior; full authorization/concurrency permutations NOT closed.**

## WP7A6-D02 — Image-only Social composer absent (P2)

Initial Chrome trace 9a74ecea883faa8d shows only a Video composer; source ready()/previewPost() unconditionally require Video identity. Added a separate image draft path using existing SocialPost create/update/preview APIs, matching owner/product/content/media and explicit preparation-not-publication text. Detail labels distinguish Content Artifact from Video. Draft edits clear the old preview; changed unsaved captions cannot be previewed. Stable accessible account naming was corrected after a real select timeout. Final four contexts saved, previewed, edited and reloaded actual persisted image-only drafts without Video, schedule or remote publication IDs. **Specific draft defect retested; HUMAN review, failure/recovery, first-create concurrency and full authorization coverage remain open.** Media UUID entry remains a usability limitation, not a complete image picker.

## WP7A6-H01 — Harness phase registration / initialization cleanup

WP7A6 was initially missing from inherited fixture and browser safety allowlists. Startup failed, and its app engine pool remained open during cleanup. Added exact phase registration and dispose-on-finally, keeping owner/marker/OID/active-session guards. Initial b52354e8cd471427 was later normally dropped only after process exit and all existing guards passed; no FORCE/resume bypass. Initial invalid review payload (missing product_type) and Meesho call to Amazon/Flipkart-only connectivity endpoint were corrected as harness errors, not app bugs. Eight focused gate/safety self-tests pass. Audit priority now reports CLEANUP_PENDING rather than implying database absence when historical Docker runtime drift also exists.

## WP7A6-I01 — Exact QA DROP timeout (RECOVERED / independently verified)

HUMAN-approved recovery completed on 4 November 2026 (Asia/Calcutta). The exact QA database `vayujit_qa0e63cd34fede26e1_test` (OID 13516456) was removed using the existing non-FORCE `resume_drop` after fresh instance/container, signed lifecycle, owner/OID, zero-session and no-active-QA-process checks. [Recovery evidence](../../../tmp/qa-wp7a6/recovery-0e63cd34fede26e1.json); previous failure reports are preserved in `tmp\qa-wp7a6\before-approved-recovery-20261104T015051Z`. A fresh process independently confirms all 9 run databases absent and signed DROPPED. The historical session-final CLEANUP_BLOCKED record was retained unchanged. No other database, Docker resource, or normal app process was modified by recovery.

## Remaining coverage, not speculative closure

- **R-3feda36d (PARTIAL)**: duplicate_concurrent, failure_recovery, approval_no_publish, owner_isolation.
- **R-55e822d5 (PARTIAL)**: missing_credentials, fake_validated_label, invalid_expired_revoked, account_mismatch, reload_recovery, default_deny.
- **R-551d2f8c (PARTIAL)**: legitimate_resolution, human_review, authorization_states, exact_fingerprint, stale_mismatch, repeat_concurrent, reload_failure_recovery, no_submission, owner_isolation.
- **R-db243c36 (PARTIAL)**: manual_resolution, review_boundaries, unsupported_live_truthful, stale_duplicate, reload_failure_recovery, no_dispatch, owner_isolation.
- **R-d6a495d5 (PARTIAL)**: legitimate_resolution, authorization_states, exact_fingerprint, stale_mismatch, repeat_concurrent, reload_failure_recovery, no_submission, owner_isolation.
- **L-16 (PARTIAL)**: artifact_versions, dependency_graph, changed_preview_stale, fingerprint_confirmation, concurrent_replay, interrupted_recovery, no_release.
- **L-17 (PARTIAL)**: creative_content_image, exact_versions, missing_invalid_prerequisites, authorization_states, preview_fingerprint, human_confirm, stale_concurrent, failure_recovery_latest, reload_owned, no_spend.

Amazon draft variant/base-price preparation needs a separate contract decision: current Amazon POST variants/media/price handlers are remote-ID operations; variant/price prerequisites are needed by readiness before submit. Do not solve this by faking remote IDs or granting approval to incomplete listings. Catalog/image handoffs must be audited before any metadata-only preparation correction. This work did not implement a new preparation authority. Campaign and Ads remaining version/dependency/creative/authorization permutations are **not executed**, not falsely classified as live-provider-only blockers.

Historical Ads 502 remains UNREPRODUCED / CAUSE UNCLASSIFIED. No application-owned historical finding is silently closed.
