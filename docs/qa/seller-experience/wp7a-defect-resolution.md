# WP7A — bounded defect remediation

## SE-WP7A-VIDEO-QUEUE-001 — P1

Root cause: Migration 0030 explicitly supplied nullable=None for six ORM-optional AI job recovery fields, resulting in NOT NULL PostgreSQL columns. Normal queued jobs omitted them and failed.

Correction: Migration 0150 drops only those NOT NULL constraints; verifies exact column types/defaults, retains every row/value and refuses unsafe downgrade.

Evidence: Original 50/51 run retains NotNullViolation. Retest 56/56 includes empty roundtrip, NULL rollback refusal and historical non-NULL value preservation; L-01 browser queue/replay.

Status: RESOLVED_IN_SCOPED_INDEPENDENT_RETEST

Files:

- `apps/api/alembic/versions/20261207_0150_ai_job_optional_recovery.py`
- `apps/api/tests/test_seller_wp7a.py`
- `apps/api/tests/test_seller_wp6a_migration.py`

## SE-WP7A-RESEARCH-EMPTY-001 — P1

Root cause: An explicit category with no local fixture reached an uncaught LookupError in execute_run; HTTP 500 replaced a legitimate no-results outcome.

Correction: Persist PARTIAL / NO_USEFUL_PRODUCT_CANDIDATES, failed discovery checkpoint and no external writes, matching the existing blocked-research architecture. Never relax the category or add fake candidates.

Evidence: Sanitized LookupError frames in 900ec8ca748fa174; two unavailable categories start/start/retry/reload and database zero opportunities; B-06 actual UI.

Status: RESOLVED_IN_SCOPED_INDEPENDENT_RETEST

Files:

- `apps/api/vayujit_api/intelligence/business_agent_service.py`
- `apps/api/tests/test_seller_wp7a.py`

## SE-WP7A-SELECTOR-CONTEXT-001 — P1

Root cause: Business context selector loaded active-brand products only and changing its Brand did not reload products, so later brands could not choose their actual product.

Correction: Request the explicit brand, clear old product/artifact/media identities on user brand change, ignore late superseded context responses. Backend ownership guards unchanged.

Evidence: 0b083ed8209c786d mobile/Edge L-01 failure; two new Angular cases plus independent four-context browser retest.

Status: RESOLVED_IN_SCOPED_INDEPENDENT_RETEST

Files:

- `apps/web/src/app/shared/business-entity-selectors.component.ts`
- `apps/web/src/app/shared/business-entity-selectors.component.spec.ts`

## SE-WP7A-CAPTION-FEEDBACK-001 — P2

Root cause: addCaption retained previous error/success notices across a new request, so a persisted successful caption still displayed its previous rejection.

Correction: Clear prior feedback at the next valid caption attempt, retain authoritative failure and pending HUMAN review semantics.

Evidence: 900ec8ca748fa174 L-02 before evidence; invalid then valid actual caption save/reload, focused Angular failure/retry test.

Status: RESOLVED_IN_SCOPED_INDEPENDENT_RETEST

Files:

- `apps/web/src/app/ai/ai-video.component.ts`
- `apps/web/src/app/ai/ai-video.component.spec.ts`

## SE-WP7A-STORYBOARD-CONTEXT-001 — P2

Root cause: Storyboard cards showed version but no board/product identity; same-version drafts were ambiguous.

Correction: Display exact board ID and product ID; no new selection/version authority.

Evidence: 84b191290279edf4 L-03 before evidence; two same-version cards regression; actual editor save and stale row-version conflict.

Status: RESOLVED_IN_SCOPED_INDEPENDENT_RETEST

Files:

- `apps/web/src/app/ai/ai-video.component.ts`
- `apps/web/src/app/ai/ai-video.component.spec.ts`

## SE-WP7A-RESEARCH-CONTRAST-001 — P1

Root cause: Secondary-action anchors received a dark background but were omitted from the shared button foreground rule; axe measured blue #0000ee on #42616a at 1.4:1.

Correction: Include action-link in the existing accessible foreground/padding/theme rule and responsive sizing; no rule suppression.

Evidence: a2626483fc580c9f B-02/B-03/B-06 serious axe findings; later populated-state scans.

Status: RESOLVED_IN_SCOPED_INDEPENDENT_RETEST

Files:

- `apps/web/src/app/intelligence/business-agent-workspace.css`
- `qa/unit/wp7a-safety.test.mjs`

## SE-WP7A-RESEARCH-HEADINGS-001 — P2

Root cause: Decision brief embeds a shared H3 evidence card under an H4 section, followed by H5 summaries, skipping levels.

Correction: Configurable semantic heading level with unchanged H3 default; this nested card requests H5.

Evidence: 0b083ed8209c786d B-03 heading-order findings in all four contexts; explicit heading regression and actual axe rescans.

Status: RESOLVED_IN_SCOPED_INDEPENDENT_RETEST

Files:

- `apps/web/src/app/shared/evidence-card.component.ts`
- `apps/web/src/app/shared/evidence-card.component.spec.ts`
- `apps/web/src/app/intelligence/business-agent-workspace.component.ts`

## Harness corrections, not production defects

QA snapshot incorrectly read nonexistent VideoGeneration.output_media_id; it now queries owner/generation-scoped VideoOutput. Early goal creator and label locators raced lazy loading or assumed exact label text despite select options; canonical body/IDs and actual accessible names are now used. Draft storyboard editing increments row_version, not immutable version: assertion corrected to the actual contract while stale409, exactscene persistence and draft state remain required. Ads Next is a navigation control, not validation: Back preserves entered values and the real server preview rejects missing fields422. Initial Angular selector tests failed because they invoked a selection before allowing ngOnInit to settle; they now flush the initial lifecycle read before testing changes, without relaxing any assertion. Failed-run evidence is retained.

The subprocess coordinator clears its owned completed cleanup timer; SQL timeouts and deletion guards are unchanged. Safe exception telemetry records only path/type/SQLSTATE/metadata-column allowlist/source frames, never SQL, bound parameters or raw output. The read-only audit scans generated metadata and trace contents for current protected credential values/encodings. No key/credential is printed or copied into these reports.

## Changed-file scope

Production changes are limited to the files above. QA foundation additions: `qa/wp7a-baseline.mjs`, `qa/wp7a-browser.mjs`, `qa/wp7a-checks.mjs`, `qa/wp7a-preserve-run.mjs`, `qa/wp7a-report.mjs`, `qa/wp7a-safety.mjs`, `qa/wp7a_fixture.py`, `qa/wp7a_probe.py`, `qa/wp7a_final_audit.py`, `qa/unit/wp7a-safety.test.mjs`, `scripts/test-seller-wp7a.ps1`. Existing QA lifecycle/proxy/launcher integration: `qa/fixture_server.py`, `qa/server.mjs`, `qa/safety.mjs`, `qa/seller-browser-explore.mjs`, `qa/seller-browser-session.mjs`, `qa/wp7-run.mjs`, `qa/wp4_final_audit.py` (read-only package scope only). Other pre-existing dirty repository files do not belong to this work package. No commit/push/branch.
