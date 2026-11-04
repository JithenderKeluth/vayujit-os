# WP7A remaining seven — blocker classification and decision review

4 November 2026 · Asia/Calcutta · **Decision review only**

## Decision in brief

Keep **WP7A INCOMPLETE: 48 original entries, 41 closed, seven PARTIAL**. Recommend **three TARGETED FIX, three TARGETED TEST, and one ACCEPTANCE CLARIFICATION REQUIRED**. None of the seven needs a real provider merely to test its existing local behavior. Genuine connectivity, publication and provider authorization expiry are separate, uncertified outcomes.

The principal execution problem is not a missing database approval: the saved recovery evidence confirms cleanup PASS and nine absent QA databases. The A6 scenario implementation deliberately returns PARTIAL in every branch and omits the missing tests. Rerunning that implementation unchanged cannot close these entries.

This review read saved artifacts and source contracts. It **did not** connect to a database, inspect live Docker/process state, run tests, replay browsers, change application/harness code, or alter previous evidence. Only this Markdown report and its [structured JSON companion](wp7a-remaining-seven-decision.json) are new deliverables. Environment availability today is not inferred from old health checks.

## Seven-row decision table

One recommended next disposition is assigned to each original ID. Secondary risks do not silently change that disposition or its acceptance requirement. Effort is incremental engineering time after shared harness work, not measured test runtime or a delivery guarantee.

| Stable ID / original route | Classification of remaining gap | Exactly one next disposition | Smallest next action / closure boundary | Incremental estimate |
|---|---|---|---|---|
| **R-3feda36d** · `/social/posts/:id` | Static-confirmed image approval UI gap; unexecuted stale/HUMAN/replay/recovery/security tests | **TARGETED FIX** | Expose the existing owned Social approval authority after explicit image review; reproduce stale-review behavior before any backend correction. Verify approval without scheduling/publication. | 4–6 h |
| **R-55e822d5** · `/marketplaces/overview` | Missing local state-transition and linked-account browser evidence; no established new runtime defect | **TARGETED TEST** | Exercise configured/missing/invalid/expired/revoked states using existing guarded synthetic account controls; verify overview → Accounts → channel/reload and truthful non-live status. | 2–4 h |
| **R-551d2f8c** · `/marketplaces/listings/:id/flipkart` | Missing true-draft prerequisite correction and HUMAN authorization matrix | **TARGETED TEST** | Use the actual Flipkart draft creator/local writes, then review, issue/revoke/expire and reject stale/mismatched contexts; no submit/transport. Reproduce potential late-readiness/expiry projection issues before fixing them. | 4–6 h |
| **R-db243c36** · `/marketplaces/listings/:id/meesho` | Static-confirmed unpublished-draft price dependency cycle; missing manual-flow evidence | **TARGETED FIX** | Reproduce with `remote_listing_id=None`; reuse existing pricing policy/model for local draft pricing, then test actual manual readiness/review. Do not invent Meesho OAuth or listing execution authorizations. | 4–6 h |
| **R-d6a495d5** · `/marketplaces/listings/:id/amazon` | Static-confirmed local draft/variant/base-price preparation gap; missing authorization matrix and ambiguous aggregate test ordering | **TARGETED FIX** | Reproduce the unpublished path, reuse catalog/mapping authorities for local preparation, preserve repaired readiness guards, then prove exact review/authorization semantics without SP-API. | 6–10 h |
| **L-16** · `/campaigns/new` and exact campaign/activity/dependency routes | Missing version replacement, dependency, stale-preview and recovery execution | **TARGETED TEST** | Exercise existing artifact handoff preview/confirmation and DAG editor; map every fingerprint assertion to the actual authority. Reproduce dependency-sensitive preview risks; do not add a new campaign version/approval system. | 4–8 h |
| **L-17** · `/ads/campaigns/:id` | Undefined mapping of “expired authorization” to actual Ads model; all exact creative/detail scenarios also unexecuted | **ACCEPTANCE CLARIFICATION REQUIRED** | Owner defines the expiry condition against an existing authority, or retains it open and separately scopes an actual expiry capability. Then test local content/image creative and HUMAN confirmation on the exact detail route. | Decision 0.5–1 h; tests 4–8 h afterward |

No row is classified AUTHORIZATION REQUIRED merely because this particular task is read-only. Future implementation/testing still needs an execution instruction. No row is primarily EXTERNAL DEPENDENCY: the original local acceptance must not be displaced by real-provider onboarding.

## Evidence and acceptance rules

Sources read: A5 and A6 coverage ledgers, closure reports, defect registers and browser evidence; A6 closure plan, scenario/safety/snapshot/report code; saved final browser/JUnit, recovery and independent audit artifacts; relevant Social, marketplace, Campaign and Ads backend/UI contracts.

- The exact original acceptance strings below are copied from [A5's ledger](wp7a5-coverage-ledger.json), preserved in [A6's ledger](wp7a6-coverage-ledger.json). The JSON also preserves their original closure requirements. Nothing is excluded or marked PASS by this review.
- Final A6 run `befaa935c05fac4a` attempted seven entries in installed Chrome/Edge at 1440×900 and 390×900: **28 PARTIAL, zero complete acceptance passes**. Screenshots/traces are linked per ID in [A6 browser evidence](wp7a6-browser-evidence.md). They were not replayed during this review.
- A6 has owned row snapshots for six entry types; Ads lacks exact campaign/creative persisted proof. `human_review` on Amazon means **incomplete review denied**, not a positive HUMAN review or authorization. Image preview invalidation is not proof of stale HUMAN approval rejection.
- Four-context UI actions, negative/recovery behavior, exact persisted lineage and applicable accessibility/keyboard evidence are still necessary. API-only fixtures, route rendering and static source inspection cannot supply missing browser acceptance.
- One owner per installation remains authoritative. Prove owner-scoped rows, unauthenticated denial and invalid-resource handling without disabling `ck_users_single_owner`. Do not fabricate a second owner in the same database to force a multi-tenant test.

## Per-entry assessments

### R-3feda36d — image-only Social review

**Original acceptance:** “Prepare image and approved-Video drafts, preview/review exact references, reject stale versions, retain unavailable external state and no remote publication.”

**Supported workflow and existing evidence.** Existing SocialPost APIs create, update, preview and approve an owned post. A5 established a separate exact approved-Video draft path. A6 demonstrated image-only creation, product/content/media identity, preview, edit-induced fingerprint change, save/reload and absent Video/schedule/remote publication IDs in four contexts.

**Exact missing assertions:** `duplicate_concurrent`, `failure_recovery`, `approval_no_publish`, `owner_isolation`. In particular, no completed image-only HUMAN approval or stale approval rejection is proved.

**Classification and impact.** The image detail template has Save draft caption and Preview image draft, but no approval call. The backend's existing `POST /social/posts/{id}/approve` is not exposed by the inspected Social service/UI. This is a source-confirmed workflow gap, **not newly runtime-reproduced**. The seller reaches “Ready for review” without a discoverable completion action. Stale/concurrent approval is a security risk to test, not an established exploit: the inspected approval request does not accept an expected preview fingerprint, while caption updates clear the preview and approved posts are not editable through the normal update path.

**Smallest safe action / authorization.** In a future bounded fix task, expose the existing owner-authorized approval with explicit HUMAN review, not `schedulePost` or publish. Reproduce changed-input approval first; if the existing request cannot pin the reviewed state, minimally extend that authority rather than introducing another approval model. No live permission or production data is needed.

**Offline PASS / dependencies.** Four contexts must establish exact reviewed identity/version after approval/reload; stale review denial; existing duplicate/conflict semantics and first-create concurrency; validation/backend-failure recovery; owner/anonymous negatives; no publication, schedule or publishing job as a consequence of draft approval. Preserve inherited Video acceptance. Depends on shared fixture/snapshot work. Estimate 4–6 h, excluding a larger authority redesign (which would require a new scope decision).

**Contract references:** [image detail/UI](../../../apps/web/src/app/social/social-workspace.component.ts), lines 118–150; [Social router](../../../apps/api/vayujit_api/social/router.py), approval at line 296; [Social service](../../../apps/api/vayujit_api/social/service.py), `update_post` / `approve_post`.

### R-55e822d5 — marketplace overview/account state

**Original acceptance:** “Distinguish configured fake sandbox accounts from connected/live certification; missing/revoked authorization; reload snapshots and default deny.”

**Supported workflow and existing evidence.** `/marketplaces/overview` redirects to `/marketplaces`; Accounts and channel workspaces are linked. A6 checked sandbox account persistence and Amazon/Flipkart `provider_contract=UNVERIFIED`, `external_writes=false`. The Accounts UI already distinguishes validation, connection, permission and synthetic transport. Its source explicitly says provider permissions are unverified.

**Exact missing assertions:** `missing_credentials`, `fake_validated_label`, `invalid_expired_revoked`, `account_mismatch`, `reload_recovery`, `default_deny`.

**Classification and impact.** This is principally unexecuted local testing. Do not claim that overview wording alone proves an account is falsely classified as connected. The risk is seller confusion between configuration, local validation and real authorization. Real connected success is **not** needed to prove that the application truthfully declines to certify it.

**Smallest safe action / authorization.** Future targeted tests can reuse `/__qa/wp7a/control` for EXPIRED/INVALID/REVOKED with its exact `qa3-wp7a-` sandbox prefix and authenticated token/owner guard. A6's account prefixes do not match this fixture; adapt the fixture inputs, not the guard. Exercise overview-to-Accounts state transitions, mismatch/unknown IDs, recovery and reload. Meesho is not supported by the Amazon/Flipkart connectivity endpoint; test its truthful unsupported/manual state separately. No real credential or provider call is necessary.

**Offline PASS / dependencies.** All supported synthetic states must agree across API, owned persisted account and visible linked UI; configured/validated fake must never imply live-connected permissions. Default-deny and useful recovery actions must survive refresh in four contexts. Depends on shared account fixtures. Estimate 2–4 h. Actual OAuth/connected status remains externally pending, not a reason to skip local negatives.

**Contract references:** [routes](../../../apps/web/src/app/app.routes.ts), line 391; [Accounts UI](../../../apps/web/src/app/marketplaces/marketplace-accounts.component.ts); [connectivity projection](../../../apps/api/vayujit_api/commerce/connectivity_router.py), `_account`, `_capability`, `connectivity_status`; [guarded state fixture](../../../qa/wp7a_fixture.py), EXPIRED/INVALID/REVOKED branch.

### R-551d2f8c — Flipkart readiness and HUMAN authorization

**Original acceptance:** “Exact Flipkart draft, canonical readiness prerequisite correction, HUMAN review/authorization expiry/revocation/staleness and reload; no transport execution.”

**Supported workflow and existing evidence.** Channel-specific draft creation keeps remote ID absent. Local variant/media writes and the draft branch of local pricing already exist. Separate HUMAN review and expiring/revocable authorization are implemented. A6 proved missing readiness and an owned listing/product/account snapshot; A5 reported route/reload and anonymous rejection. Neither demonstrates the complete positive path.

**Exact missing assertions:** `legitimate_resolution`, `human_review`, `authorization_states`, `exact_fingerprint`, `stale_mismatch`, `repeat_concurrent`, `reload_failure_recovery`, `no_submission`, `owner_isolation`.

**Classification and impact.** Targeted test execution is missing, not an established external blocker. Issuance checks the stored review/fingerprint but does not visibly rerun `_readiness`; `_safe_authorization` returns stored status with expiry time. Whether prerequisite removal or an elapsed authorization is correctly represented/enforced remains a **test-first concern**. No new vulnerability is asserted without reproduction.

**Smallest safe action / authorization.** A future test task should use `POST /marketplaces/flipkart/listings` and the actual local `PUT .../variants`, `/media`, `/pricing`, not generic fake active listings. Exercise UI correction, HUMAN review, issue/revoke, exact account/content changes and replay. For expiry, use a tightly guarded QA-only clock/resource preparation or the supported minimum wait; never change the production clock/configuration. No submit/transport is needed for positive review/authorization proof.

**Offline PASS / dependencies.** Correct a genuine missing prerequisite through normal authorities, verify exact current review/authorization binding, reject wrong/stale/expired/revoked contexts, preserve history and idempotent/conflicting semantics under concurrent requests, and show useful recovery/reload in four contexts. Assert no consumption, remote listing or publishing work. Depends on true-draft fixtures, actual method/path allowlists and review/authorization snapshots. Estimate 4–6 h; only fix failures after reproducing them.

**Contract references:** [Flipkart router](../../../apps/api/vayujit_api/commerce/flipkart_router.py), draft creation ~451, review 801, authorization 894, local preparation 1208/1274/1314; [workspace](../../../apps/web/src/app/marketplaces/flipkart-workspace.component.ts).

### R-db243c36 — Meesho manual preparation/readiness

**Original acceptance:** “Exact Meesho draft, supported readiness/manual preparation/HUMAN review boundaries, unavailable integration and reload; do not invent OAuth or dispatch.”

**Supported workflow and existing evidence.** A channel-specific local draft, approved content, local variants/media, readiness and preview/manual review exist. There is no separate Meesho listing execution-authorization model in the inspected path. A6 checked missing readiness and owned context/reload; it did not complete a true unpublished-draft correction.

**Exact missing assertions:** `manual_resolution`, `review_boundaries`, `unsupported_live_truthful`, `stale_duplicate`, `reload_failure_recovery`, `no_dispatch`, `owner_isolation`.

**Classification and impact.** Static contract inspection establishes a price dependency cycle: a new channel draft has no remote ID; readiness requires a persisted base price; submit requires readiness; `save_price` rejects a missing remote ID before writing that price. Variant/media local writers do exist. This is an application-owned seller dead end, not missing Meesho credentials. **No fresh runtime reproduction was performed.**

**Smallest safe action / authorization.** First reproduce the true draft path. Then, under a future bounded fix instruction, reuse Meesho's pricing policy and owned MarketplacePrice model with a local-draft branch comparable to Flipkart's existing implementation. It must not call a connector, fabricate a remote ID or relax readiness. Do not add OAuth, an execution-authorization table or dispatch to satisfy “review”.

**Offline PASS / dependencies.** Legitimate local price and other missing inputs clear their actual blockers; invalid/unknown data remains blocked; manual preview/review respects exact content/product/account; duplicate/stale/error/recovery/reload and owner checks pass in four contexts; live unavailability remains truthful and no dispatch occurs. Share the local preparation correction with Amazon. Estimate 4–6 h. A new authority or migration is a stop-and-scope decision, not implied permission.

**Contract references:** [Meesho router](../../../apps/api/vayujit_api/commerce/meesho_router.py), create ~432, `_readiness` 509, submit ~647, `save_price` 878; [Flipkart local-price reference](../../../apps/api/vayujit_api/commerce/flipkart_router.py), remote-ID-absent branch ~1333; [Meesho UI](../../../apps/web/src/app/marketplaces/meesho-workspace.component.ts).

### R-d6a495d5 — Amazon local preparation and HUMAN authorization

**Original acceptance:** “Exact Amazon draft, canonical readiness prerequisite correction, HUMAN review/authorization expiry/revocation/staleness and reload; no SP-API calls.”

**Supported workflow and existing evidence.** Existing Amazon listing readiness, HUMAN review and execution-authorization models remain authoritative. A6's incomplete-review denial passed in four contexts. Its focused persisted tests passed for missing readiness, explicit HUMAN confirmation and price removal after review. This does not prove positive browser review/authorization, nor that a seller can populate the prerequisites normally.

**Exact missing assertions:** `legitimate_resolution`, `authorization_states`, `exact_fingerprint`, `stale_mismatch`, `repeat_concurrent`, `reload_failure_recovery`, `no_submission`, `owner_isolation`.

**Classification and impact.** The missing local preparation is application-owned. Readiness requires local variants, media and base price; the inspected Amazon POST variant/pricing writers require a remote ID and call the connector. The generic creator calls a fake connector and persists an active listing/remote ID, so it is not an unpublished-draft proof. Image handoff **already** provides a local media binding and must be reused, not duplicated. The backend positive fixture inserts mapping/variant/price rows directly; those valid backend fixtures cannot establish a seller-facing correction path.

**Smallest safe action / authorization.** Under a future explicit local fix/test instruction, reproduce a remote-ID-absent draft, audit the normal catalog-to-listing handoff, and add only the missing metadata preparation using existing Listing/Variant/Price models and channel policies. Preserve remote handlers and repaired readiness checks. Never use fake remote IDs or direct ORM seed rows as successful browser correction. No SP-API, production-data repair or recovered-database permission is inherited from earlier approvals.

**Offline PASS / dependencies.** Genuine local preparation reaches readiness, incomplete review/issuance remains denied before and after material change, and exact fingerprint, account/content, expiry/revoke/stale/replay/concurrency/reload/history checks pass in all four contexts without submission or consumption. Sequential frozen-source affected tests must resolve the saved test-outcome ambiguity described below. Share fixtures/local-pricing work with Meesho and the Flipkart positive control. Estimate 6–10 h; no new consequential authority is planned.

**Contract references:** [Amazon router](../../../apps/api/vayujit_api/commerce/amazon_router.py), readiness guards 664/747, readiness 1096, remote variant/pricing 1803/1881; [generic creator](../../../apps/api/vayujit_api/commerce/router.py), `create_listing`; [image handoff](../../../apps/api/vayujit_api/ai/image_service.py), `confirm_handoff`; [focused regression](../../../apps/api/tests/test_seller_wp7a6.py).

### L-16 — campaign artifact versions and dependency changes

**Original acceptance:** “Create campaign with exact approved artifact/product bindings; change input, expose stale prerequisite, recover via legitimate new review, verify dependency and reload.”

**Supported workflow and existing evidence.** Campaign and activity row versions, exact artifact binding, the dependency editor and canonical readiness/recovery exist. The artifact campaign-handoff API already previews and confirms replacement with expected artifact/current versions, updating the same activity and audit lineage. A5 tested exact binding and disabled-destination recovery. A6 only created/reloaded one checkpoint; it did not exercise a two-activity dependency or replacement.

**Exact missing assertions:** `artifact_versions`, `dependency_graph`, `changed_preview_stale`, `fingerprint_confirmation`, `concurrent_replay`, `interrupted_recovery`, `no_release`.

**Classification and impact.** This is unexecuted supported testing. An inspection concern remains: the reschedule fingerprint does not directly include dependency edges. That is not enough to declare a bypass; test what that specific preview authorizes and whether current dependency/readiness checks run before acceptance. Do not invent a CampaignVersion entity or impose a new fingerprint authority merely because an A6 label says `fingerprint_confirmation`.

**Smallest safe action / authorization.** Future tests should use two exact activities, real dependency editor operations, cycle/self/duplicate negatives, and old/new approved artifacts through the existing handoff preview/confirmation. Show that publishing a newer artifact does not silently replace the old binding. Test stale expected version and concurrent replacement, legitimate refreshed review and persisted recovery. Map any stronger fingerprint assertion to an existing canonical preview. The actual recovery UI posts `/campaigns/recovery/actions`; A6's per-action `/confirm` allowlist is not that route.

**Offline PASS / dependencies.** Exact version/edge identities persist; bad dependencies and stale reviewed changes are rejected under the actual contract; refreshed confirmation/recovery is safe and repeatable; no campaign release or real execution occurs. If a required recovery confirmation materializes an enabled schedule/job, verify its existing offline authorization scope before running it—do not silently replace it with a new dry-run authority. Metadata handoff/DAG checks do not require publication. Four contexts, failure/reload and owner proof remain mandatory. Estimate 4–8 h plus any separately reviewed, reproduced defect.

**Contract references:** [artifact handoff](../../../apps/api/vayujit_api/ai/studio_router.py), line 856; [activity/dependency authority](../../../apps/api/vayujit_api/campaigns/activity_service.py); [fingerprint](../../../apps/api/vayujit_api/campaigns/recovery_service.py), line 41; [confirmation](../../../apps/api/vayujit_api/campaigns/recovery_executors.py), `execute_reschedule_activity`; [dependency UI](../../../apps/web/src/app/campaigns/dependency-editor.component.ts); [actual recovery request](../../../apps/web/src/app/campaigns/campaign.service.ts).

### L-17 — Ads creative and authorization semantics

**Original acceptance:** “Local fake content/image creative preview, missing/expired/disabled authorization, stale references and HUMAN confirmation; never remote execution.”

**Supported workflow and existing evidence.** Ads has owned local accounts, configured/validated/enabled/status/credential-version fields, exact content/image creative readiness, campaign preview/fingerprint, explicit HUMAN confirmation and local job/failure/recovery history. A5/A6 only exercised an account/wizard and `/ads/create`; the required exact `/ads/campaigns/:id` with persisted creatives was not reached.

**Exact missing assertions:** `creative_content_image`, `exact_versions`, `missing_invalid_prerequisites`, `authorization_states`, `preview_fingerprint`, `human_confirm`, `stale_concurrent`, `failure_recovery_latest`, `reload_owned`, `no_spend`.

**Classification and owner decision.** “Expired authorization” needs an actual authority. The inspected AdAccount has no credential-expiry timestamp or Amazon-style one-use execution authorization. An AdJob lease expiry is not account authorization expiry. Missing/removable credentials, invalid validation, disabled status and credential-version changes are testable now. Do not invent an `expired` row value, reinterpret a validation timestamp, or use a synthetic credential as proof of provider expiry.

The owner must explicitly choose the acceptance mapping: identify an already supported invalidation/revocation contract and accept its **precise** scope, or retain the original expiry condition open and separately scope a real expiry capability. This report does not make that choice, remove the condition or certify an equivalent state silently. If genuine provider/OAuth expiry is intended, that part remains an external milestone outside offline authorization.

**Smallest safe action / authorization.** After that decision, run exact content and image creative selection/version/preview/HUMAN-confirmation, mismatches, failure/retry and detail reload with guarded synthetic fixtures. Confirm may queue an AdJob; this is not publication. Keep real workers/transports and spend blocked, assert canonical job/creative lineage, and never consume queued work with a real provider. Existing Ads failure controls are reusable only under their exact local fake binding and owned-resource guards.

**Offline PASS / dependencies.** The expiry requirement must have an explicit approved interpretation tied to a real application contract, or stay PARTIAL. All remaining local creative, account, fingerprint, HUMAN, stale/concurrent/failure/history/owner/no-spend evidence must reach the exact persisted detail in four contexts. Historical Ads 502 remains UNREPRODUCED / CAUSE UNCLASSIFIED unless actually reproduced and diagnosed. Decision estimate 0.5–1 h; subsequent existing-authority tests 4–8 h. A new expiry feature is **not estimated or authorized** here.

**Contract references:** [AdAccount model](../../../apps/api/vayujit_api/ads/models.py), line 48; [account/preview/creative services](../../../apps/api/vayujit_api/ads/service.py); [HUMAN confirmation and nested creative APIs](../../../apps/api/vayujit_api/ads/router.py), lines 340/363/454; [current scenario](../../../qa/wp7a6-scenarios.mjs), L-17; [guarded failure fixture](../../../qa/wp7a2_fixture.py).

## Shared causes and harness feasibility

1. **Incomplete scenario implementation, not seven independent mysterious failures.** `qa/wp7a6-scenarios.mjs` uses a helper that always returns PARTIAL and omits required sequences. Complete those sequences once, with assertion-to-authority mapping. Do not weaken `qa/wp7a6-contract.mjs` to make old partial attempts pass.
2. **Fixture authority mismatch.** The shared `listing()` calls generic fake-active creation. Use actual unpublished channel drafts and assert remote IDs absent before preparation; do not mistake synthetic remote success for a legitimate first-draft handoff. Backend row seeding remains suitable for unit/integration setup, not proof of the missing UI operation.
3. **One shared local preparation correction.** Amazon variant/base-price and Meesho base-price preparation should be addressed together using the already-local Flipkart pattern and existing image handoff, while preserving each channel's policy and remote gates.
4. **Exact test transport paths do not match actual contracts.** A6 omits some channel-specific draft/PUT preparation paths, nested Ads `/campaigns/:id/creatives` and `/creatives/readiness`, and the actual Campaign recovery action path. QA-only method/payload allowlists can be extended for these existing authorities without changing production configuration. Never add blanket `/submit`, `/execute`, `/release`, arbitrary credentials or worker permission.
5. **Missing state/snapshot coverage.** Reuse existing exact-prefix account expiration/revocation controls, add only tightly scoped synthetic authorization-clock support if needed, and include owned Ads creative/job/fingerprint, Flipkart review/authorization and Campaign dependency histories in read-only snapshots. UI failure/retry and owner negatives must be explicit, not inferred from API fixtures.
6. **Evidence order is ambiguous.** The current saved backend summary reports **72 unique cases, one latest failure**, not zero. Its generator sorts JUnit by file modification time. The full run `bed1d274ee1d45bb` started at 22:33:51 +05:30 on 3 November, before passing focused run `5740623d2b3c4fc8` at 22:45:29, but finished later. Completion order is not source-revision order. Without tested-source hashes, do not silently override either outcome or reclassify the old failure as an active production defect. A future sequential frozen-source affected-test run must settle it. The intermediate browser run that overlapped a build also remains diagnostic only.

The reusable foundation is sufficient: attested loopback QA instance design, signed marker/token/OID/role lifecycle, canonical deterministic fixtures, installed Chrome/Edge, four contexts, authentication, screenshots/traces, axe, three-layer egress controls and independent cleanup audit. The blockers above are mostly missing tests or bounded harness/application contract work—not a need to change the single-owner model, production `.env`, business database or real credentials.

No supported local test should require weakening HUMAN approval. Use a frozen application build and sequential test lifecycles. Any failed cleanup stops the batch; previous exact recovery approval is not reusable for another database.

## Recommended execution order and bounded scope

This is a recommendation, **not an instruction to execute during this review**:

1. Obtain the L-17 acceptance decision and a future bounded offline fix/test instruction. Do not start real provider onboarding to answer it.
2. Repair shared fixture/path/snapshot/evidence-ordering gaps. Freeze source/build hashes before browser execution.
3. Use Flipkart's real local draft path as the positive control. Then reproduce and repair the Amazon/Meesho local preparation family together.
4. Complete the image-only Social review affordance and its stale/replay/recovery tests without changing the inherited Video path.
5. Complete overview/account states and all three marketplace detail matrices from the shared fixtures; no provider submit.
6. Complete Campaign artifact handoff, dependency and changed-preview/recovery evidence; reproduce suspected failures before fixes.
7. Complete the exact Ads content/image creative matrix after the owner decision; keep fake queued work non-live.
8. Sequentially run affected backend regressions and seven complete Chrome/Edge desktop/mobile scenarios against stable source, relevant Angular/static/build/axe checks, then independently verify guarded cleanup. Preserve all earlier attempts and original 48 IDs.

**Minimum engineering budget, if Ads maps to an existing authority:** shared harness 3–5 h; seven incremental rows 28–48 h; final focused validation 3–5 h: **34–58 engineering hours**, plus the owner's 0.5–1 h decision. Estimates exclude waiting, new provider capability/expiry development and unexpected defects. Start with one marked backend lifecycle and one marked browser lifecycle; any debug retry needs a bounded reason and retained evidence. No automatic follow-up package or unrestricted redesign.

Planned application correction areas are limited to the image review affordance and the shared unpublished marketplace preparation family. No migration, new owner model or new approval system is planned. Stop for a scope decision if a reproduction requires a new consequential authority, destructive migration, real provider call, unexpected permanent data access, or an unapproved exact recovery.

## What offline authorization cannot certify

- Genuine seller connectivity/OAuth/permissions, official API/sandbox acceptance, live publication or account authorization expiry on Amazon, Flipkart, Meesho, social or Ads.
- An unimplemented Ads expiry authority, unless separately scoped and approved. Invalid/disabled or job-lease states are not an automatic substitute.
- Provider delivery, campaign spend/billing, complete WCAG/manual assistive-technology behavior, production financial reconciliation/immutable accounting, or independent PC-first backup.

None of these permits silently excluding a row. Where the original requirement is truthful **unavailability/default-deny**, test that local behavior; do not demand a live success it never required. Where it truly requires an absent authority, keep that condition open until the owner decides.

## Preservation and carried risks

The saved [recovery record](../../../tmp/qa-wp7a6/recovery-0e63cd34fede26e1.json) and [independent audit](../../../tmp/qa-wp7a6-final-audit.json) retain exact OID 13516456, guarded non-FORCE recovery and nine absent/signed-DROPPED databases. The original `CLEANUP_BLOCKED` session record and `before-approved-recovery-20261104T015051Z` archive remain unchanged. This review did not re-query or operate on them.

Carry forward without closure:

- PostgreSQL StartedAt/FinishedAt discrepancy: **UNRESOLVED / UNATTRIBUTED**; saved structural identity is unchanged. No restart/recreation to erase history.
- Historical Ads 502: **UNREPRODUCED / CAUSE UNCLASSIFIED**.
- Manual accessibility: open; A6's 28 scans/zero violations/14 incomplete rule occurrences do not establish WCAG compliance.
- Financial-history, reconciliation and immutable-accounting limitations: open and not retested.
- Historical repository-wide typing/lint debt: not recertified by focused checks; production-critical effects must not be inferred absent.
- PC-first backup certification: **PARKED**.

**Conclusion:** cleanup is not the blocker now. Finish the bounded local corrections and actual missing test execution, resolve the Ads acceptance meaning explicitly, and preserve the live-provider boundary. Until that work is demonstrated, all seven remain PARTIAL and WP7A stays INCOMPLETE. Stop after this decision review; no WP7B, WP7C or WP8.

## Review artifact validation

JSON parsing and cross-document checks passed: seven exact unique IDs, seven verbatim A5 acceptance/closure strings, seven unchanged A6 missing-assertion lists, seven decision-table rows and exactly one permitted disposition per entry. Trailing-whitespace checks passed. SHA-256 comparison confirmed 24 selected historical evidence and source files unchanged, including the recovery record, archive manifest and independent audit. These are document/preservation checks, **not application tests**. Certification/regression suites run during this review: **zero**.
