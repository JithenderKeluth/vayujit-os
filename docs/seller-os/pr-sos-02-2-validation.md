# PR-SOS-02.2 — Amazon Local Certification Closure

**Final classification:** **PR-SOS-02 — FULLY VALIDATED (LOCAL / FAKE AMAZON
TRANSPORT / NO LIVE MARKETPLACE MUTATIONS)**

This closure executes the only two browser scenarios left open by PR-SOS-02.1:
the genuine incomplete-listing blocker and stable browser history/deep-link
navigation. It does not expand Amazon scope and does not certify Amazon OAuth,
SP-API connectivity, sandbox acceptance, or production publication.

## A–Z evidence report

**A — Authority audit.** The scenario uses the existing
`MarketplaceListing`, catalog Product/Variant/MediaAsset, GeneratedArtifact,
readiness, review, execution-authorization, audit, and fake transport
authorities. No second approval or readiness system was introduced.

**B — Browser environment.** Authenticated Chrome was run with the isolated CDP
endpoint on port 9225 and the Angular app on port 4200. The CUA helper could
not initialize because its ACL helper returned `helper_unknown_error:
apply deny-read ACLs`; direct CDP was used as the documented local fallback.

**C — Disposable state.** PostgreSQL database `vayujit_sos022b_test` was
migrated/reset for the run. The protected `vayujit_golden_test` database was
not modified.

**D — Incomplete listing.** Canonical authenticated listing creation produced
listing `4d5e9698-4289-48e9-82ad-a5716354dc60` for product
`88772f5a-02bf-4672-9085-56e045bc7c6c`. It intentionally had no approved
artifact, variant, mapped image, or selling price, so the server—not the UI—
reported the blocker.

**E — Exact missing information.** The listing page reported:

- “The exact mapped Artifact version must be approved.”
- “At least one valid variant is required.”
- “At least one mapped main image is required.”
- “A selling price is required.”

**F — Disabled HUMAN boundary.** Review/approval, one-time execution
authorization, and submission controls were disabled while readiness was
Blocked. No UI action bypassed the authoritative prerequisite.

**G — Guidance.** The page now presents: “Next action: complete the blocking
items above, then select Preview readiness. HUMAN review and execution
authorization remain unavailable until the server reports Ready.”

**H — Correction/reassessment.** Adding the existing canonical media asset
`11faf44b-f486-4ea2-a39a-268c348bfca7` through the media editor removed the
image blocker after a fresh readiness read. The remaining artifact, variant,
price, and drift blockers stayed visible, proving re-evaluation rather than a
client-side unlock.

**I — Complete listing.** The complete fixture listing was
`f42e855a-251c-4319-8ef3-bd832537d4c2` (Kids Thermal Lunch Carrier). After
review and the existing Keep remote drift resolution it reported
`Server-driven readiness Ready` and `Blocking None`.

**J — Defect found and fixed.** `keep_remote` resolved drift records but did
not persist `MarketplaceListing.drift_state`; the next drift read therefore
re-detected the same records and kept readiness blocked. The bounded fix
persists `remote_kept`, preserves resolved fields on replay, and avoids
re-creating unchanged detected records. A focused regression covers this
behavior.

**K — HUMAN review.** The complete listing was reviewed through the browser;
the persisted projection reported `Listing review: approved`.

**L — One-time authorization.** The existing authorization action issued one
authorization once the listing was Ready and approved. The page reported
`Execution authorization: issued`; the submit control became enabled. No live
transport was called.

**M — Back/forward.** The authenticated CDP run navigated
`/marketplaces` → `/marketplaces/amazon` →
`/marketplaces/listings/f42e855a-251c-4319-8ef3-bd832537d4c2/amazon`, then
restored the recorded `/marketplaces/amazon` history entry and the listing
entry using Chrome navigation history. The listing ID and Ready state were
preserved on forward restoration.

**N — Refresh.** Refresh on the listing deep link retained the route, listing
ID, Ready state, `Listing review: approved`, and issued authorization.

**O — New-tab deep link.** A second isolated Chrome tab opened the same deep
link. It remained authenticated, owner-scoped to `pr-sos021@example.com`, and
reported the same listing ID, Ready state, approved review, and issued
authorization.

**P — Runtime errors.** CDP `Runtime.exceptionThrown` and `console.error`
listeners captured zero errors during reload in both tabs.

**Q — Accessibility.** axe-core 4.11.0 reported zero violations and zero
incomplete findings on the complete listing/review state (1,026 passes) and
the blocked/correction listing state (960 passes). Evidence images:
[`complete`](../../tmp/ux-browser/prsos022-complete-axe.png),
[`deep-link`](../../tmp/ux-browser/prsos022-deeplink-axe.png), and
[`corrected blocker`](../../tmp/ux-browser/prsos022-incomplete-corrected.png).

**R — Focused controls regression.** `test_pr_sos_02_amazon_controls.py`:
**5 passed**, 12 framework deprecation warnings. The new keep-remote test was
also rerun alone: **1 passed**, 4 deselected.

**S — Adjacent backend regression.** `test_amazon.py`,
`test_amazon_e2e.py`, and `test_amazon_workers.py`: **11 passed**, 2 framework
deprecation warnings.

**T — Angular regression.** `62` test files / `223` tests passed.

**U — Frontend quality.** ESLint passed with 0 errors and 2 pre-existing
`ngOnInit` lifecycle warnings in unrelated campaign dialogs. Production build
passed; the pre-existing initial bundle budget warning remains (509.18 kB vs
500 kB).

**V — Python quality.** Focused Ruff, Black, strict mypy for
`amazon_router.py`, and API `compileall` all passed.

**W — Migration/integrity.** The disposable PostgreSQL migration chain and
fixture reset passed. No production or golden database mutation occurred.

**X — Network/safety.** The run used the deterministic local fake Amazon
transport only. No Amazon credentials, SP-API request, publication, supplier
contact, RFQ, procurement, payment, or marketplace write occurred.

**Y — Git hygiene.** `git diff --check` passed. The repository had broad
pre-existing worktree changes; no unrelated changes were reverted, and no
commit or push was performed.

**Z — Release decision.** Both PR-SOS-02.2 browser rows are **PASS** and the
focused/adjacent regressions are green. PR-SOS-02 is therefore fully validated
for the local fake transport boundary. Real Amazon OAuth, SP-API, sandbox
acceptance, and production listing publication remain explicitly uncertified.

## Scenario ledger

| Scenario | Result | Evidence |
|---|---|---|
| Incomplete-listing blocker | **PASS** | Server readiness Blocked; four exact missing fields; review/authorization/submission disabled; correction removed only the corrected image blocker; next action shown |
| Stable browser history/navigation | **PASS** | Back/forward history-entry restoration, refresh, second authenticated deep-link tab; listing ID/owner/review/authorization/Ready state retained; zero runtime errors |

## Changed files in this closure

- `apps/api/vayujit_api/commerce/amazon_router.py` — durable drift-state and
  resolved-record replay fix.
- `apps/api/tests/test_pr_sos_02_amazon_controls.py` — keep-remote/readiness
  regression.
- `apps/web/src/app/marketplaces/amazon-workspace.component.ts` — blocked
  state next-action guidance.
- `docs/seller-os/pr-sos-02-2-validation.md` and the linked roadmap/report
  status updates.

No PR-SOS-03 work was started.
