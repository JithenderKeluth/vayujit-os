# WP7A-5 defect and limitation register

Earlier failed screenshots, traces and JUnit are retained. Scoped RETESTED means the linked correction passed its latest four browser contexts; it does not close other acceptance conditions or certify the application.

| ID | Priority | Confirmed cause | Correction | Retest | Evidence IDs |
|---|---|---|---|---|---|
| A5-D01 | P2 | Exact activity route used overview instead of activity detail; long unwrapped JSON obstructed mobile navigation. | CampaignVideoComponent now uses existing videoDetail, clears stale views and ignores superseded async responses; JSON wraps. Exact generation deep link is consumed by AI Video. | RETESTED — scoped | R-794214d7 |
| A5-D02 | P2 | Bulk Video could queue work but lacked durable reopen/recovery controls. | Existing operation/history/retry/cancel APIs are exposed with exact query identity, busy guards and reload. No worker or execution authority duplicated. | RETESTED — scoped | L-21 |
| A5-D03 | P2 | SEO metadata lacked scoped edit/reload and safe duplicate-name conflict handling; success used an error banner. | Canonical GET/PUT sets, keyword revision selection and scoped history; save feedback is separate. Unique violations map to 409, unavailable FK to 422, other database failures are not suppressed. | RETESTED — scoped | L-15 |
| A5-D04 | P1 | Video composer sent a generation ID to legacy text-post creation, losing the intended Video handoff contract. | Reuses canonical Video channel preview/prepare and explicit HUMAN confirmation to create a draft only. Exact output/thumbnail/metadata/version are pinned. Confirm response exposes durable social_post_id, including replay. | RETESTED — scoped | L-22 |
| A5-D05 | P1 | Failed image job left ImageOutput queued, hiding canonical recovery. Retry success also left its attempt observation incomplete. | finish_ai_job persists image state and failure count once across projections; recovery resets exact unprocessed output. Success records current attempt checkpoint/completion without rewriting failed attempts. No output is auto-approved. | RETESTED — scoped | L-12 |
| A5-D06 | P1 | Bulk-text status polling and concurrent retry acquired conflicting projection locks (observed SQLSTATE 40P01). | Status/retry/cancel serialize on the same owned parent before touching children. Eight-request regression preserves two exact jobs and artifact identities. | RETESTED — scoped | L-13 |
| A5-D07 | P1 | Bulk-Video status polling and retry similarly deadlocked (observed SQLSTATE 40P01). | Status/retry/cancel/projection routes lock the owned parent before children; mixed poll/retry regression and real-browser concurrent replay added. | RETESTED — scoped | L-21 |
| A5-D08 | P1 | Populated observation list returned ORM instances inside list[Any], causing PydanticSerializationError; verification/provenance were not visible. | List validates rows with existing TrendObservationResponse before serialization. UI shows exact verification or UNKNOWN, synthetic flag and provenance. Decimal API values and arithmetic remain unchanged. | RETESTED — scoped | R-184826c3 |
| A5-D09 | P2 | Persisted marketing-plan version/budget review lacked a discoverable supported update path. | Existing detail/recommendation/history and budget preview/HUMAN confirmation are exposed; Decimal input remains text, expected version/fingerprint and idempotency remain canonical. | RETESTED — scoped | L-23 |
| A5-D10 | P2 | Long Social account options widened the mobile fieldset and put Next outside the usable viewport. | Fieldsets/grid tracks and native controls now allow shrinking within the viewport; long bound identifiers wrap. Browser assertions check actual document width without force-clicks. | RETESTED — scoped | L-22 |

## Harness corrections (not application defects)

The first backend run exposed missing seeded AI templates, disabled intelligence metadata and absent ephemeral credential encryption in isolated test fixtures. Fixtures now opt into only the local metadata/fake transport configuration they test. Real mutation remains disabled and socket egress remains blocked. Amazon/Flipkart fake positive controls temporarily exercise their explicit emergency-stop negative cases; production settings were not relaxed.

Browser assumptions corrected: lowercase marketplace enums; exact supported content types; server-pinned Activity artifact version; unchanged SEO fingerprint reuses the analysis ID; implicit select labels include option text; Video approval waits for the selected generation. Decimal values are compared using Decimal rather than incidental fixed-scale string formatting. These corrections are not counted as production defect resolutions.

## Remaining local coverage and inspection concerns

- R-55e822d5: Configured-only overview checked; connected/revoked/expired account projections not fully exercised.
- R-551d2f8c: Exact draft/reload checked; full prerequisite correction and missing/expired/revoked/stale HUMAN authorization permutations unexecuted.
- R-db243c36: Exact draft/reload checked; supported manual preparation/readiness/review permutations incomplete. No invented Meesho OAuth or dispatch.
- R-d6a495d5: Exact draft/reload checked; full readiness and HUMAN authorization permutations incomplete. Authorization/readiness guard requires separate focused reproduction.
- R-3feda36d: Video draft with exact thumbnail/metadata is targeted; separate image-only draft and stale review permutations remain incomplete.
- L-16: Exact binding and disabled-destination recovery tested; artifact-version replacement and dependency ordering still require browser evidence.
- L-17: Local fake account/wizard checked; content/image creative and missing/expired/disabled authorization permutations remain unexecuted.

Amazon authorization/readiness inspection concern: issue_listing_execution_authorization validates approved review/fingerprint but does not invoke listing_readiness. This needs a narrowly scoped negative runtime reproduction and contract review before any guard change; it is not represented as a reproduced external-write vulnerability. Existing submission/worker gates remain in force; no submission was attempted.

Historical Ads502, unattributed PostgreSQL timestamp drift, financial history/reconciliation limitations, repository-wide static debt, manual/incomplete accessibility and parked PC-first backup are not closed by this package.
