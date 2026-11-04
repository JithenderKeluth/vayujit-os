# WP7A-4 — Defects and scope limits

| ID | Severity | Original entries | Root cause/evidence | Minimal correction | Resolution rule |
|---|---|---|---|---|---|
| WP7A4-APP-01 | P2 | R-a8d8b217 | Destination editor included immutable connector_key in PATCH; canonical DestinationUpdate forbids extra fields. | Send name, brand_id and configuration only on edit; preserve the create contract. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |
| WP7A4-APP-02 | P2 | L-18, L-19 | Plain asynchronous Brand Voice/Preset fields did not notify zoneless Angular change detection; POST 201 succeeded while lists remained empty. | Notify ChangeDetectorRef after asynchronous loads/actions, including error paths; no backend authority change. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |
| WP7A4-APP-03 | P1 | R-9dc8a702, R-5e241b88 | Named generic workflow/comparison divs lacked an appropriate ARIA role. | Use role=group with the existing accessible names; no axe suppression. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |
| WP7A4-APP-04 | P1 | R-75d260b7, R-541d7261, L-25 | Review serialization forced every GeneratedArtifact into legacy ProductContent; channel-specific Studio content caused ValidationError and HTTP 500, including comparison versions. | Keep strict legacy generation validation; expose exact persisted Studio dictionaries in review responses and render all saved fields without invented SEO/caption data. Edits retain the correct field names. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |
| WP7A4-APP-05 | P1 | R-551d2f8c, R-db243c36 | Flipkart/Meesho selectors treated paginated Products/Brands response objects as iterable arrays, producing Angular TypeError. | Unwrap canonical items at the HTTP boundary. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |
| WP7A4-APP-06 | P2 | L-25 | Legacy product_content offered a Studio translation action despite not being an accepted Studio content type; POST returned 422. | Disable that incompatible action with an explanation. Exercise translation with genuinely supported channel-specific Studio content; do not relabel legacy content to force acceptance. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |
| WP7A4-APP-07 | P2 | R-8f16bd41, L-12, L-21 | Unbroken image checksum/Video fingerprint text overflowed the mobile document. Screenshots establish overflow; it is not assumed to explain every click timeout. | Wrap long code/pre identifiers in the relevant existing layouts. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |
| WP7A4-APP-08 | P2 | L-23 | Wizard repeated the entire total for every channel. Retained traces show INR 250.50 total with two INR 250.50 allocations; the API persisted a blocked plan. No spend occurred. | Expose explicit manual channel allocations; omit unknown blanks rather than inserting zero. Reuse the existing canonical budget validator for initial plan input, as for later budget changes. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |
| WP7A4-APP-09 | P1 | R-eb4987ba | Parallel events/product-channel projections raced on the same unique audit idempotency key (SQLSTATE23505). | Lock the exact owned portfolio row before snapshotting keys/emitting its existing projection; shared audit authority and immutable history are unchanged. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |
| WP7A4-APP-10 | P2 | R-184826c3 | Trend route contextId was ignored; the page remained unselected or followed a different active journey. | Resolve the exact owned context from the route; missing IDs never substitute another context or create new research. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |
| WP7A4-APP-11 | P2 | R-a8d8b217 | Destination form was editable before its asynchronous data load completed, allowing later patchValue to overwrite seller input. Retained mobile traces additionally show Save pointer interception and an overflowing form. | Render/accept saves only after successful initialization; failed initialization remains blocked. Constrain grid tracks, labels and controls to available form width; use normal browser clicks rather than force-clicking. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |
| WP7A4-APP-12 | P2 | L-14 | Bulk image Retry was inside an overflowing mobile table without a focusable horizontal scroll container. | Use the existing table-scroll layout with a named keyboard-focusable region. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |
| WP7A4-APP-13 | P1 | R-eb4987ba | Populated portfolio dimension limitations failed color contrast; supplier/history scroll regions were not keyboard-focusable. | Use the existing dark muted palette and named focusable table regions; no axe-rule suppression. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |
| WP7A4-APP-14 | P2 | L-14 | The bulk-image Queue CTA remained enabled after the canonical preview reported missing-source blockers, although the backend rejected ineligible work. | Disable Queue and guard its handler while the current preview contains blockers; retain authoritative backend validation. | FIX_ASSERTIONS_RETESTED; this does not close missing broader workflow coverage |

## Remaining workflow gaps

- WP7A4-GAP-01 (P2; R-794214d7): Campaign Video activityId route uses the overview component, which does not read activityId. A focused activity detail/rejection contract is not established. Retain partial; do not claim a populated overview proves activity-specific navigation.
- WP7A4-GAP-02 (P2; L-21): Bulk Video component holds operation identity only in memory and does not expose all canonical retry/cancel/reopen controls. Canonical API and deterministic worker behavior are separate from missing browser recovery/reload proof.
- WP7A4-GAP-03 (P2; L-15): SEO save actions do not establish a complete scoped keyword/tag/history management journey; tag list is not rendered by this component. Retain partial rather than fabricate a saved-list UI assertion.

## Harness/environment findings (not automatically application defects)

- WP7A4-HARNESS-01: Orphaned response waiter could reject after a failed click and terminate Node before later entries ran. Observe the pending rejection without suppressing its actual awaited assertion; regression executed.
- WP7A4-HARNESS-02: Transient UNKNOWN file-open error interrupted the ledger writer. Atomic bounded replacement and retry for Windows sharing failures; persistent write failures still fail closed.
- WP7A4-HARNESS-03: Repeated destination names, wrong catalog-vs-marketplace IDs, wrong social content type, inactive/missing-price test Products, unselected current brand, incorrect waiter paths/status expectations, and an absent local Video HUMAN-approval allowlist produced false blockers. Use exact canonical identities/contracts, unique fixture names, active explicit priced synthetic Products, correct current-brand activation, awaited action completion and safe worker-ID projection. Allow only the existing local feedback-only HUMAN Video review in WP7A4, not provider dispatch or approval bypass.
- WP7A4-HARNESS-04: Initial responsive-width contexts were not touch-emulated. Arbitrary Tab focus-count assertion could fail at the browser chrome boundary. Final mobile contexts enable isMobile/hasTouch. Focus a visible named control before bounded Tab/Shift+Tab checks; do not claim exhaustive keyboard coverage.
- WP7A4-HARNESS-05: Run 412436d33a219d5f DROP timed out, leaving a signed exact OID tombstone. After explicit HUMAN approval, existing non-FORCE resume_drop completed in 1.672s with all guards intact. No general recovery authority added.

A new maintenance GET502 in the 346ac65c280b5d93 Edge1440 context was observed during Brand Voice work. It is retained as a transport/runtime failure, not falsely attributed to Brand Voice persistence or used to close the historical Ads502. No unrelated container was restarted.

The budget defect persisted blocked local plans only; no real spend or provider call occurred. Explicit allocations remain human-entered, and blank unknowns are omitted. The existing validator is reused; no marketplace fee schedule or new financial authority is invented.

| Original ID | Route | Outcome | Exact remaining disposition |
|---|---|---|---|
| R-184826c3 | `/intelligence/trends/:contextId` | PARTIAL | Owned context/reload verified; populated observation/source analysis remains unverified. |
| R-8a5edab2 | `/` | PASS | VERIFIED_LOCAL_SCOPE |
| R-7e93fba0 | `/login` | PASS | VERIFIED_LOCAL_SCOPE |
| R-17b7d214 | `/ads/accounts/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-66842e70 | `/ads/campaigns/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-794214d7 | `/campaigns/:id/video/:activityId` | PARTIAL | Exact approved Video binding and reload verified; the activityId route renders an overview rather than an activity-specific detail. |
| R-ec41ffe0 | `/campaigns/:id/video` | PASS | VERIFIED_LOCAL_SCOPE |
| R-8522d9c2 | `/campaigns/:id/activities/new` | PASS | VERIFIED_LOCAL_SCOPE |
| R-f4ba2c21 | `/campaigns/:id/dependencies` | PASS | VERIFIED_LOCAL_SCOPE |
| R-e4940841 | `/campaigns/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-3feda36d | `/social/posts/:id` | PARTIAL | Canonical social draft and persisted identity checked; image/video-specific and stale-review permutations remain. |
| R-55e822d5 | `/marketplaces/overview` | PARTIAL | Overview and reload checked; full configured-channel snapshot requires remaining account fixtures. |
| R-551d2f8c | `/marketplaces/listings/:id/flipkart` | PARTIAL | Exact catalog-linked draft/default-deny reviewed; complete channel readiness/review authorization transitions remain. |
| R-db243c36 | `/marketplaces/listings/:id/meesho` | PARTIAL | Exact catalog-linked draft/default-deny reviewed; complete channel readiness/review authorization transitions remain. |
| R-d6a495d5 | `/marketplaces/listings/:id/amazon` | PARTIAL | Exact catalog-linked draft/default-deny reviewed; complete channel readiness/review authorization transitions remain. |
| R-8f16bd41 | `/ai/images/assets/:outputId` | PASS | VERIFIED_LOCAL_SCOPE |
| R-5e241b88 | `/ai/studio/artifacts/:id/compare` | PASS | VERIFIED_LOCAL_SCOPE |
| R-75d260b7 | `/ai/artifacts/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-2e8db403 | `/settings/publishing/connectors` | PASS | VERIFIED_LOCAL_SCOPE |
| R-756ae8b2 | `/publishing/destinations/shopify` | PASS | VERIFIED_LOCAL_SCOPE |
| R-af04ee8c | `/publishing/destinations/wordpress` | PASS | VERIFIED_LOCAL_SCOPE |
| R-730f1388 | `/media/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-a8d8b217 | `/publishing/destinations/:id/edit` | PASS | VERIFIED_LOCAL_SCOPE |
| R-9b0fb4bc | `/publishing/destinations/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-68adcdc8 | `/publishing/executions/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-2b4d90d2 | `/publishing/schedules/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-30072869 | `/publishing/jobs/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-e309647e | `/operations/workers/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-9dc8a702 | `/workflows/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-541d7261 | `/approvals/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-eb4987ba | `/intelligence/supplier-portfolios/:portfolioId` | PASS | VERIFIED_LOCAL_SCOPE |
| R-8d64a30d | `/**` | PASS | VERIFIED_LOCAL_SCOPE |
| L-09 | `/ai/generate` | PASS | VERIFIED_LOCAL_SCOPE |
| L-10 | `/ai/studio` | PARTIAL | Completed snapshot retained; queued old-context work rejects as stale after a Product change. Provider retry/supersession permutations remain. |
| L-12 | `/ai/images` | PARTIAL | Image regeneration/reload/source approval retained; injected provider failure/recovery still requires exact child controls. |
| L-13 | `/ai/studio/bulk` | PARTIAL | Canonical cancellation/reload exercised; partial success/provider retry combinations remain. |
| L-14 | `/ai/images/bulk` | PASS | VERIFIED_LOCAL_SCOPE |
| L-15 | `/ai/studio/seo` | PARTIAL | Keyword/tag creation and tag reload executed; analysis history/reanalysis/context permutations remain. |
| L-16 | `/campaigns/new` | PARTIAL | Canonical product/approved-content activity binding persisted; full recovery/stale binding permutations remain. |
| L-17 | `/ads/campaigns/:id` | PARTIAL | Persisted fake Ads campaign, explicit HUMAN confirmation and reload checked; creative/stale/expired-authorization permutations remain. |
| L-18 | `/ai/brand-voices` | PASS | VERIFIED_LOCAL_SCOPE |
| L-19 | `/ai/presets` | PASS | VERIFIED_LOCAL_SCOPE |
| L-20 | `/ai/usage` | PASS | VERIFIED_LOCAL_SCOPE |
| L-21 | `/ai/video/bulk` | PARTIAL | Actual local deterministic bulk Video preview, fingerprint, queued child and worker completion executed; cancel/retry/partial and browser reload identity remain. |
| L-22 | `/social/compose` | PARTIAL | Supported composer and persisted text draft exercised; Video composer needs a canonical approved Video output. |
| L-23 | `/ads/marketing` | PARTIAL | Manual persisted plan preview/confirmation/reload exercised; recommendation/version/change permutations remain. |
| L-24 | `/settings/ai/providers` | PASS | VERIFIED_LOCAL_SCOPE |
| L-25 | `/ai/artifacts/:id` | PASS | VERIFIED_LOCAL_SCOPE |
