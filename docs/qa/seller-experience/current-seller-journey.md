# Current seller journey — source-grounded transition review

Audit/design only, 2026-10-27. The proposed chain below is **not** an existing
mandatory wizard. Sellers with stock/products should enter catalog/inventory
directly; sellers researching a new line need evidence-first decision paths.

The current Commerce Journey projects eight research/sourcing stages, not the
whole operational seller lifecycle (`apps/api/vayujit_api/intelligence/commerce_journey.py:35`).
Product, catalog, stock, channel preparation, orders and financials have separate
canonical authorities. All fresh persisted runtime consequences below remain
**UNVERIFIED** unless a named historical bounded record is cited. This document
does not create new fixtures, perform provider calls or claim application coverage.

Legend: S = current source verified; H = retained historical bounded QA evidence;
U = fresh runtime unverified. In each transition the numbered dimensions match
the ten questions in the seller-experience assignment.

## Entry: empty installation → owner workspace

1. **Seller objective:** establish the one legitimate owner and business context,
   without accidentally loading test accounts, inventory or financial events.
2. **Required information:** owner name/email/password; real brand information
   when creating products. Credentials are not QA-report evidence.
3. **Origin:** direct HUMAN entry; setup-status reports persisted owner presence.
4. **Current behavior (S):** `identity/router.py` setup-owner creates hashed owner
   and cookie session; duplicate owner fails via singleton constraint. Dashboard
   and launch-readiness provide separate guidance.
5. **Discoverable next step:** dashboard/Business Agent/product creation routes
   exist. Which entry best fits an already-operating seller is a UX design choice,
   not a requirement to research an opportunity first.
6. **Status comprehension:** “owner exists” is not business readiness or `.env`
   configuration; login and setup are distinct.
7. **Action state:** setup available only before owner; subsequent setup conflicts;
   protected APIs require current session. Real-data activation remains blocked by
   unresolved recovery/independence gates, not a UI authorization toggle.
8. **Explanation:** setup errors and launch-readiness exist; complete session
   expiry/password recovery instruction remains U.
9. **Context/lineage:** one owner per database (`ck_users_single_owner`), not SaaS
   multi-tenancy. Owner filtering still matters for foreign/stale IDs.
10. **Revise/recover:** login/logout supported; do not simulate recovery by adding
    another owner. H Phase 1 setup/protected route tests are not disk-loss recovery.

## 1. Goal → opportunity

1. **Seller objective:** find potentially suitable real products under explicit
   category/market/budget constraints, without unsupported best-seller/profit claims.
2. **Required information:** goal text, parsed constraints, approved research mode,
   budget/provider availability; real product identity evidence for eligibility.
3. **Origin:** HUMAN goal; parser proposes structured goal; Brave search returns
   URLs; approved fetcher obtains product pages; category hypotheses are derived,
   not product proof.
4. **Current behavior (S):** goal → plan → run authorities persist separately;
   `product_research.py:526–1110` checks explicit category against observed product
   evidence, records search/fetch outcomes and approval-required/no-useful results.
5. **Discoverability:** create/plan/start/review/retry controls exist; live mode,
   context confirmation and source approvals are distinct controls. H finding
   `QA-UX-PRE-RUN-MODE-001` preserves confusing pre-run guidance.
6. **Status:** run progress is execution steps, not number of useful products.
   No opportunity is a truthful outcome, not a mandate to fall back to cached
   unrelated products or generate a fixed count.
7. **Action state:** source approval/quota/identity failures can block discovery;
   plan/latest-run 404 before creation is not itself provider failure.
8. **Explanation:** outcome counters and failure messages exist; owner screenshots
   describe recurring discovery failure but fresh real-provider execution is U.
9. **Lineage:** run/candidate idempotency prefix links candidate to current goal;
   explicit goal category is retained in evidence metadata and journey filtering.
10. **Recovery:** revise plan/retry/cancel supported; each retry must retain bounds,
    source policy and HUMAN authority. Do not reset quota counters to pretend
    entitlement or fabricate a successful candidate.

## 2. Opportunity → research

1. **Seller objective:** understand product identity, sources, trust and gaps
   before interpreting attractiveness or commercial feasibility.
2. **Required information:** owner opportunity ID, constraints/assessment version,
   actual source/evidence and permissions.
3. **Origin:** fetched observed evidence, derived context, explicit assumptions and
   existing trend/review/competition/sourcing authorities, each with its own trust.
4. **Current behavior (S):** opportunity detail/market research and distinct
   assessment/intelligence/commercial/score/synthesis APIs exist. Unknown scores
   suppress ordinary ranking; underlying raw source is not automatically verified.
5. **Discoverability:** shared opportunity workspace exposes detail/research; many
   specialist research pages live in Advanced navigation. H long research-page
   finding documents 13–19k-pixel surfaces.
6. **Status:** lifecycle, research state, evidence state and assessment readiness
   are separate; “assessed” does not mean evidence verified or commercially viable.
7. **Action state:** research can be available, source-blocked, stale, incomplete
   or unavailable; loading an assessment is not authorization to buy/publish.
8. **Explanation:** sources/unknowns and gap reasons exist; end-user comprehension
   and each conditional state's useful next action require targeted U tasks.
9. **Lineage:** immutable constraints/input snapshots/assessments refer to owner
   opportunity; source/freshness/trust must remain visible through projections.
10. **Recovery:** re-assess/research/archive supported; retained prior evidence
    should not be overwritten or quietly promoted to current verified truth.

## 3. Research → explicit product selection/rejection

1. **Seller objective:** consciously choose a candidate for supplier work, or
   decline/defer it while preserving evidence and history.
2. **Required information:** canonical opportunity/assessment/score, rationale and
   request identity; no supplier price is invented to unlock selection.
3. **Origin:** existing assessment/score plus authenticated HUMAN intent.
4. **Current behavior (S):** `product_opportunity_scoring_router.py:452` persists
   decision tied to score/assessment. Schema supports watch, research_more,
   shortlist, reject, archive; UI mainly exposes shortlist. This is distinct from
   later commercial recommendation/HUMAN decision.
5. **Discoverability:** “Select this product for supplier research” is present;
   rejection/reselection and consequence explanation are less evident in inspected
   UI. A disabled action needs its prerequisite, not an instruction to weaken gates.
6. **Status:** selection is seller intent, not verified profitability or supplier
   approval. Current selection vs historical decision distinction is crucial.
7. **Action state:** score/assessment and authenticated scope gate request. U
   shortlist→reject behavior is particularly important before declaring closure.
8. **Explanation:** **S-SEL** in inventory records inconsistent query semantics:
   decision readiness uses latest action, journey/catalog/run queries find prior
   shortlist. These source facts do not prove a successful prohibited action.
9. **Lineage:** decision stores opportunity/assessment/score/idempotency key;
   freshness relative to a revised assessment and latest rejection needs testing.
10. **Recovery:** API supports new decision actions; identical/conflicting replay,
    rejection after selection and explicit reselection must be tested. Basic
    selection replay is not the stronger commercial HUMAN replay implementation.

## 4. Product selection → supplier discovery/evaluation

1. **Seller objective:** find relevant potential manufacturers/suppliers for the
   selected product, not retailers or arbitrary directory pages.
2. **Required information:** selected opportunity/product/goal, sourcing concept,
   geography/requirements and allowed mode/source policy.
3. **Origin:** canonical selected product and derived sourcing concept; fetched
   supplier evidence, or explicitly labeled manual/synthetic fixtures in QA.
4. **Current behavior (S):** `supplier_router.py:323` resolves explicit or projected
   opportunity and builds bounded research requirements, preserving retail and
   sourcing identities; searches/evidence/history/source-diversity APIs exist.
5. **Discoverability:** primary “Suppliers” points to sourcing decision workspace;
   canonical cross-marketplace discovery is under Advanced. This is a source-
   confirmed mislabeled handoff, not proof supplier APIs are absent.
6. **Status:** candidates/source claims ≠ verified suppliers; unknown terms and a
   single candidate are legitimate incomplete states, not artificial rankings.
7. **Action state:** discovery may be offline, permission-blocked or unavailable;
   direct exploratory query support is not equivalent to selected-product approval.
8. **Explanation:** clear “Find candidates for [product]” and source outcome guidance
   are needed; genuine live result and relevance behavior remain U here.
9. **Lineage:** selected opportunity/product in requirements; canonical supplier
   source/evidence and cross-marketplace correlation exist. Plain links can drop
   query context; two-product/two-supplier switching must be demonstrated.
10. **Recovery:** retries/history/manual entry supported under existing guards;
    never restore an old unrelated supplier merely because it has reusable evidence.

## 5. Supplier → sourcing / due diligence

1. **Seller objective:** understand legitimacy, capabilities, claims and missing
   commercial evidence; choose whether further investigation is justified.
2. **Required information:** supplier/opportunity scope, shortlist context/version,
   source evidence, gap plan; quotations/terms only where actually obtained.
3. **Origin:** canonical sources/claims/verification; reviewed inbound evidence and
   explicitly entered assumptions are separate from observed supplier facts.
4. **Current behavior (S):** comparison snapshots, HUMAN shortlist decisions and
   readiness/handoff exist; DD contexts/assess/gaps/plans/tasks/recovery exist;
   sourcing requirements/RFQ/quotes/samples/inspection authorities also exist.
5. **Discoverability:** separate detail/DD/shortlist/sourcing workspaces and plain
   subnavigation make the path hard to discover and preserve context. H Phase 2
   exercised a synthetic selected supplier/DD path, not live acquisition.
6. **Status:** NEEDS_EVIDENCE / NOT_COMPARABLE / blocked is not verified or failure
   to purchase. A supplier shortlist is not permission to contact/dispatch RFQ.
7. **Action state:** bounded DD can remain incomplete; engagement/send authorization
   remains separate and no contact is authorized by this audit.
8. **Explanation:** identify exact gap, who can satisfy it and where to enter
   evidence. Avoid presenting absent MOQ/lead time/price as zero or a score penalty.
9. **Lineage:** DD context refs supplier/product/opportunity; evidence version and
   shortlist remain durable. Context loss on links is U until persisted switching.
10. **Recovery:** new assessment/plan, gap actions and history supported; unsupported
    quote acquisition is a prerequisite, not reason to synthesize a quote.

## 6. Sourcing → economics / commercial decision

1. **Seller objective:** evaluate cost, capital fit, uncertainty and viable next
   decision; distinguish research interest from a decision to proceed.
2. **Required information:** explicit supplier/currency/price basis, MOQ/freight,
   logistics/duty/FX/fees/selling price/capital where required by actual formula.
3. **Origin:** reviewed commercial evidence, explicit HUMAN assumptions, approved
   fee rules; missing marketplace fee schedules are not invented.
4. **Current behavior (S):** readiness snapshots, immutable landed/unit calculations,
   scenario/capital/cash/sensitivity and decision synthesis/recommendation/HUMAN APIs.
   Material assumptions are compared semantically in `landed_cost_service.py:271`.
5. **Discoverability:** economics link exists, but `supplier_id` passed by supplier
   page is not consumed by economics initialization in inspected source. Long page
   hierarchy is a retained P2 issue, not grounds to remove provenance.
6. **Status:** unknown/stale/changed/NOT_COMPARABLE/READY describe different gates.
   READY for a calculation is not profitable, tax-compliant or approved launch.
7. **Action state:** changed/missing/stale acquisition lineage blocks old landed
   support; commercial PROCEED requires eligible recommendation/current synthesis.
8. **Explanation:** key missing/stale input and recalculation action should precede
   detailed lists; source/assumption/basis must remain inspectable.
9. **Lineage:** owner/opportunity/assessment/supplier/scenario/fingerprint; strong
   HUMAN decision replay compares scope/intent and current synthesis. H Phase 2
   remediation verifies modeled freshness/replay; real fees/taxes remain U.
10. **Recovery:** equivalent snapshots reusable; changed assumptions require new
    readiness/calculations/decision review. Preserve history and exact replay,
    reject conflicting same-key intent rather than duplicate business actions.

## 7. Economics/decision → catalog → opening inventory

1. **Seller objective:** establish a sellable product master and accurately record
   counted stock, without treating analysis as acquired physical goods.
2. **Required information:** owner/brand/product/SKU, optional real variant/images,
   physical stock quantity/location/unit and immutable opening intent.
3. **Origin:** manual real product entry or explicitly selected opportunity;
   stock count is HUMAN observation, not inferred MOQ/demand/financial assumptions.
4. **Current behavior (S):** `catalog/service.py:151` converts selected opportunity
   and persists lineage; `inventory_router.py:118` atomically creates item/movement/
   audit with owner lock, replay and physical/nonarchived product guards.
5. **Discoverability:** Catalog empty-state suggests conversion but no frontend
   conversion invocation was found. Manual creation and inventory “Add opening
   stock” exist; do not force existing sellers into research to create products.
6. **Status:** catalog draft/active is not quantity, stock synchronization or listing
   publication. Opening stock is local ledger count; unknown cost stays unknown.
7. **Action state:** catalog conversion requires shortlist; inventory requires valid
   product/variant and distinct SKU/location intent. No automatic procurement.
8. **Explanation:** explain master quantity vs unified stock and where acquisition
   cost belongs. H 4B verified bounded opening-stock copy/count/review flows.
9. **Lineage:** CatalogProductLineage retains opportunity/goal/assessment/selection;
   inventory movement retains HUMAN actor/opening_intent and before/after balances.
   Optional conversion goal and repeated conversion intent need S-CAT tests.
10. **Recovery:** local edit/archive/adjustment/ledger, replay after lost response and
    refresh supported; stock changes use movements, not rewriting old count intent.
    H 4B race/replay evidence does not certify disk-loss recovery.

## 8. Inventory → marketplace preparation

1. **Seller objective:** map SKU/product and prepare a listing/account safely;
   distinguish local completeness from legal eligibility and API entitlement.
2. **Required information:** real seller registration/identity/tax/category eligibility,
   separate API authorization, owned catalog product/images/claims/channel mapping.
3. **Origin:** HUMAN business records and official provider process; local fixtures
   are test-only. Owner has previously reported no registered channel accounts.
4. **Current behavior (S):** catalog local draft/review/readiness and channel-specific
   Amazon/Flipkart/Meesho local contracts/authorization safeguards exist. Connectivity
   imports reject non-SYNTHETIC mode; fake account validation remains UNVERIFIED.
5. **Discoverability:** overview, channel workspaces and generic listing/detail pages
   overlap. A “create listing” label must distinguish draft from fake transport or
   externally authorized submission.
6. **Status:** READY_FOR_FUTURE_SUBMISSION, SYNTHETIC, UNVERIFIED permission and
   external authorization required are not “connected/live/published.”
7. **Action state:** external writes default-deny; correct mandatory safety blocks
   must not be cleared by fake approvals or disabled controls.
8. **Explanation:** route to registration/API checklist and real missing field, not
   a synthetic account form as substitute for provider onboarding.
9. **Lineage:** product/variant/SKU/account/channel listing/version/fingerprint;
   CatalogListingDraft is distinct from MarketplaceListing fake active remote ID.
10. **Recovery:** edit/version/review/revoke/refresh supported locally; stale approval
    must require fresh review. Real OAuth/API read-only certification is U and
    separately authorized; do not call marketplaces in this audit.

## 9. Marketplace → orders

1. **Seller objective:** import and review actual orders, reconcile SKU/reservations
   and understand safe handling of cancellation/shipment/return.
2. **Required information:** authorized real account/transport, external event/order
   IDs, SKU mapping and sufficient stock; fixture events only in disposable QA.
3. **Origin:** canonical import adapter/event ingestion, not invented manual sales.
4. **Current behavior (S):** read-only unified order list/detail/timeline/insights;
   `/orders/fake/events` creates deterministic local events under owner/account
   lock. Reservation/release/consume transitions and reconciliation exist.
5. **Discoverability:** Orders links exist; unsupported manual fulfillment controls
   must not be promised. Surface rendering is not proof of genuine import.
6. **Status:** synthetic order status is local test evidence, not fulfilled sale.
   Returns are not automatically restocked or refunded without authoritative event.
7. **Action state:** live import unavailable under current connectivity contract;
   no safe way to “enable” it by entering fake credentials.
8. **Explanation:** account/auth/mapping/stock blockers need exact recovery links;
   authentic provider onboarding remains an external prerequisite.
9. **Lineage:** account/external order/event → item/mapping → inventory reservation/
   movement, with immutable replay identity and provenance. H Phase 3 covers local
   conservation, duplicate events and final-unit races, not real provider semantics.
10. **Recovery:** duplicate delivery/reload/retry supported within named cases;
    network loss, provider replay ordering, live fulfillment and OS restart remain U.

## 10. Orders → finance / reconciliation

1. **Seller objective:** know revenue, costs, fees, refund impact and settlement
   discrepancies without mistaking estimates for cash or accounting history.
2. **Required information:** canonical events, dated cost evidence, fee rule/source,
   refunds/shipping/payment/settlement and currency; explicit UNKNOWN where absent.
3. **Origin:** actual authorized source or labeled manually reported evidence;
   synthetic ancestry dominates contradictory “real” claims.
4. **Current behavior (S):** financial events/costs/rules/current calculations,
   summary/sales/profitability/fees/settlement reconciliation and alerts implemented.
   `_provenance` retains synthetic/unknown status through fallback projections.
5. **Discoverability:** multiple finance subviews exist. Sellers need an obvious
   “missing input → enter evidence → recalculate → review discrepancy” loop.
6. **Status:** current estimated/modelled projection, known zero, unknown cost,
   settlement mismatch and verified cash are not interchangeable labels.
7. **Action state:** missing costs inhibit complete profit; operational projections
   do not supply immutable historical accounting/financial transaction authority.
8. **Explanation:** sources/cost IDs and missing_inputs exist; historical
   `QA-P3-GAP-001` remains open despite narrower cost-lineage improvement.
9. **Lineage:** cost/event IDs, unknown cost IDs and provenance_sources retained;
   unique owner/scope/calculation_version current snapshot is overwritten by later
   recalculation (`financial_models.py:144`, router `:940`).
10. **Recovery:** new cost/reconciliation revision/recalculate/reload supported;
    recreating exact prior displayed projection remains unsupported. Do not use as
    sole accounting ledger without explicitly addressing that scope limitation.

## 11. Finance / operations → business improvement

1. **Seller objective:** understand what needs attention, why, and which supported
   next action resolves the source condition.
2. **Required information:** current source metrics/evidence, signal fingerprint,
   correct scope, severity/confidence/freshness and applicable HUMAN workflow.
3. **Origin:** canonical Action Center scan/briefing/financial Business Agent,
   rather than a second calculation or approval engine in dashboard.
4. **Current behavior (S):** operational signal list/filter/history/acknowledge/
   snooze/resolve/reopen and advisory request; Business Agent recommendations.
5. **Discoverability:** Action Center/dashboard/launch-readiness all surface work;
   they should link to exact artifact repair, not compete as approvals.
6. **Status:** acknowledging a signal does not resolve its underlying evidence or
   approve an RFQ/payment/publication. Resolved filters have H Phase 3B regression
   evidence; current status transitions still need representative fresh scenarios.
7. **Action state:** `request_action:939` rejects AI/SYSTEM impersonation and external
   mutations, then truthfully returns advisory-only; no durable generic approval or
   execution lifecycle is created. This is a supported boundary, not a disabled
   switch to bypass.
8. **Explanation:** H `QA-P3-GAP-002` requires owner scope decision for generic
   execution; use canonical commercial/engagement/channel workflows for supported
   action types, with clear “nothing was executed” feedback.
9. **Lineage:** signal/transition fingerprint, source and history; canonical HUMAN
   decision separately carries recommendation/synthesis/context/idempotency.
10. **Recovery:** retry scan/filter/reopen/snooze and current-state refresh supported;
    source repair should clear/transition warning through legitimate condition,
    not fake signoff. Backup/restore recovery remains a different unresolved gate.

## Highest-risk handoffs to exercise next

| Handoff | Source/historical concern | Required bounded test / prerequisite |
| --- | --- | --- |
| Rejected product → journey/run/catalog | S-SEL query inconsistency; runtime consequence U | Canonical shortlist → later reject → readiness/projection/run/local conversion; unchanged/conflicting replay, refresh and separate process. |
| Selected opportunity → catalog | Backend conversion exists; UI call not found | Authenticated explicit conversion from selected candidate; confirm same Product/lineage and UNKNOWN values, then stock entry without duplicate product. |
| Goal A/B → catalog conversion | S-CAT only owner-checks supplied goal in inspected body | Two genuine same-owner goals/opportunities; wrong-goal and changed-intent replay contract; no raw SQL fixture manufacture. |
| Suppliers → discovery → detail/DD/economics | Primary navigation lands in decision page; query context not consistently consumed | Two products + two suppliers, plain subnav/back/forward/deep link/reload; assert visible IDs, API request IDs and canonical persisted scope. |
| Missing supplier quote → economics | Correct UNKNOWN blockers can appear as dead end | Legitimate incomplete evidence fixture; identify exact entry source and safe return/recalculate path. Do not invent price/MOQ/lead time. |
| Changed economics → HUMAN decision | H freshness/replay fixes; long pages | Reuse actual semantic lineage guard; desktop/mobile seller identifies stale input and current eligible decision without losing provenance. |
| Catalog → stock → channel | Separate quantity/mapping/authorization authorities | Counted opening stock/ledger, no double counting; local draft vs fake active listing explicitly distinguished; external authorization denied. |
| Orders → finance → Action Center | Mutable projections and generic execution gaps | Persist/reload provenance/UNKNOWN/cost revisions/current-vs-history labels; source repair vs acknowledgement; default-deny external action. |

Fresh authenticated persisted exploratory execution requires a safely configured
disposable database/fixture harness and isolated browser. If unavailable, these
transitions remain U—not covered by route counts, self-tests or earlier screenshots.
Exact executed checks and blockers are in [audit validation](audit-validation.md).
