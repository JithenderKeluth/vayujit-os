# Seller workflow gap analysis

Audit and design only. No production correction, acceptance, waiver, permanent
data activation, provider call or new workflow authority is authorized by this
document. Findings retain their previous status. Source review is distinguished
from runtime evidence; current audit execution is recorded separately in
[audit-validation.md](audit-validation.md).

## Evidence and interpretation

Fresh persisted browser/API task execution for this audit is BLOCKED because the
runner lacks approved `QA_DATABASE_ADMIN_URL`. This subreview performs source and
retained-evidence analysis only. It does not configure credentials or reuse a
normal database. The root audit records its actual non-database checks separately.

The baseline is [Phase 4C validation](../phase-4c-validation.md), its
[journeys](../phase-4c-journeys.md), [route/control reconciliation](../phase-4c-route-control-coverage.md),
[findings](../phase-4c-findings.md), and the unchanged
[canonical backlog](../defect-backlog.json). At review the backlog has 129 records:
117 PASS, nine NOT_RETESTED and three BLOCKED. These are occurrence-level records,
not 129 independent bugs. The twelve open records include recommendations,
suspected defects and coverage limitations; they are not twelve confirmed
functional failures.

Phase 4C documents 155 route declarations, not 155 complete user workflows. Of 26
artifact-dependent declarations, six had bounded context evidence and twenty
were unexecuted. Seven other prior artifact visits explicitly did not certify a
workflow. Redirects are not missing pages. A screenshot, DOM control count or API
registration cannot prove successful use. Historical tests are retained evidence,
not tests newly executed for this document.

Classification used below:

- **SOURCE-CONFIRMED PRODUCT GAP:** a supported backend capability lacks the
  required frontend handoff in inspected source; task execution may be unverified.
- **HISTORICAL CONFIRMED LIMITATION:** actual retained execution plus current
  source establish the stated contract; this is not necessarily a regression.
- **USABILITY:** evidence supports friction, not an arithmetic/security defect.
- **UNVERIFIED:** a proposed test has not demonstrated the journey or failure.
- **INTENTIONAL BOUNDARY:** correct denial or external prerequisite, not a bug to
  remove. Permission to research is not permission to contact or publish.

## Transition-by-transition assessment

| Transition / seller question | Actual support and information authority | Gap and discoverability | Required safe recovery / next step |
| --- | --- | --- | --- |
| Start work: "I already have stock, or should I research a product?" | Dashboard, Business Agent, Catalog and Inventory are independent entry points. Research is not a prerequisite to manually creating an owned Product or counted opening stock. | USABILITY / task understanding UNVERIFIED. Navigation exposes research, preparation, content and growth at the same time; do not force a new seller into a single linear wizard. | Offer task choices: research an idea, manage an existing product, record counted stock, review operations. Preserve unfinished owned context; explain why a task is blocked. |
| Goal → plan → research | Goal/plan/run and canonical journey authorities are distinct. A configured provider, a confirmed goal context, source approval and a permitted run are not interchangeable. | Historical QA-UX-PRE-RUN-MODE-001. Real permitted Brave/source-approval success is UNVERIFIED in QA fixtures; earlier screenshots of failures are not proof of a current parser defect. | Display actual failure boundary: credential/quota, source approval, page-fetch failure, incompatible category, or no useful candidates. Retry only the eligible failed step; never manufacture a candidate. |
| Research → opportunity | ProductOpportunity represents supported identity with evidence, category and provenance; source snippets or an approved domain alone are not a product. Current workspace filters current versus historical opportunities. | Genuine candidate quality and cached-evidence category eligibility remain UNVERIFIED by offline seller QA. Historical page lengths complicate source review. | Preserve immutable sources, observed date/confidence/unknowns; distinguish 0 candidates from missing approval and from API failure. Explain the smallest permissible next action. |
| Opportunity → HUMAN product selection | Canonical assessment and explicit selection exist; Phase 2 synthetic fixtures demonstrated persisted scope, staleness and replay subsets. | All state combinations and first-time comprehension UNVERIFIED. Disabled selection is not permission to bypass assessment, context or evidence gates. | State exactly which prerequisite is missing and link to that owned artifact. Keep research, comparison and selection distinct; stale evidence needs re-review. |
| Selected opportunity → seller Catalog | `catalog/router.py:123` exposes conversion. `catalog/service.py:151–281` requires a HUMAN shortlist and records CatalogProductLineage, selection and opportunity context, replay/concurrency handling. | **SOURCE-CONFIRMED PRODUCT GAP SE-HANDOFF-001.** `CatalogService` has no conversion method; no conversion call exists in `apps/web/src`. `catalog-workspace.component.ts:234` instructs conversion but only links to opportunity review. Product Opportunity has no catalog conversion CTA. Browser task not yet demonstrated. | Add a bounded review-and-convert handoff to the existing endpoint, with owned brand/SKU inputs and explicit confirmation. Reuse existing product identity if linked; preserve selection lineage and UNKNOWN price. Do not replace conversion with a disconnected manual duplicate. |
| Selection → supplier discovery | Existing opportunity-scoped sourcing, supplier classification, source/evidence and HUMAN shortlist authorities; Phase 2 LOCAL_FIXTURE path exists. | SE-HANDOFF-002 source-confirmed primary Suppliers entry points to Make a sourcing decision, not Find suppliers. SE-HANDOFF-003/SE-CONTEXT-005 omit or do not consume some handoff IDs; effect UNVERIFIED. Live relevance/approval evidence also UNVERIFIED. | Use existing discovery as task entry and show selected product/goal/supplier through each supported scoped link. Test two distinct contexts before correction. No MOQ/quote/lead-time inference; contact remains separate. |
| Supplier → DD → shortlist | DD assessment/finding/claim/provenance and supplier comparison exist. Unknown evidence must remain unknown; shortlist does not certify a company or approve procurement. | Populated paths exist but many conditional states, stale approvals and owner-scoped deep links are not covered by broad route visits. Long dense evidence is a USABILITY concern. | Show evidence coverage, claims vs verification, contradictions, gaps and freshness before decision. Make normal supplier switch/back/retry reconstruct the exact owned context. |
| Supplier quotation → cost assumptions | Commercial evidence and response workflows exist; absence of a quotation does not justify inventing one. Human-entered assumptions are not a verified quote. | Actual missing-quote seller task and quote amendment propagation are not comprehensively certified. External engagement is intentionally restricted. | Offer review of existing evidence or deliberate assumption entry only where the canonical contract supports it; label estimates, source and validity. Do not offer generic "approve" as a substitute for a supplier quote. |
| Assumptions → landed cost → economics → HUMAN decision | Phase 2 material-input freshness fixes and independent Decimal oracles, subsequent persisted regressions; canonical HUMAN replay/conflict/concurrency tests. | Long economics pages (desktop 16k, mobile 43k historical pixels), hidden blockers and repeated reasons are USABILITY findings. All real GST/category fees/FX/rules UNVERIFIED. | Compact current-context summary, freshness and UNKNOWN blockers, then cost breakdown and evidence drill-down. Keep full provenance available. Recalculation and explicit review must follow material changes. |
| Commercially reviewed product → catalog preparation | Manual product creation, variants/private images/local listing drafts/readiness are supported. Catalog economics derives canonical opportunity context. | SE-HANDOFF-004: `catalog/service.py:517–541` requires opportunity lineage for sourcing projection even for a manual existing-business Product; separate operational cost authority exists. Product/Catalog naming, USD default and context-free missing-economics link add friction. | Clarify master facts vs preparation vs operational cost. Decide a legitimate manual-product evaluation path without fabricated research lineage. Preserve actual IDs through supported links; explicit currency preference/confirmation. |
| Catalog → inventory initialization | Opening-stock route is implemented; existing `POST /inventory/items` creates item + immutable movement + audit. Phase 4B covers UI, replay, races and lost replies. | **Not a missing workflow.** QA-P3-GAP-003 was resolved in 4B. Product-master quantity and canonical inventory remain different authorities that require explanation. | Record only physically counted units, explicit zero where intentional; adjustments use reason/versioned ledger, not repeated opening stock. No supplier/account/cost prerequisite invented. |
| Local SKU → marketplace draft/mapping | Catalog channel drafts, Amazon/Flipkart controlled local authorities, mapping and readiness exist. | Live registration/API entitlement/authorization not configured; generic marketplace listing creation is a deterministic fake-adapter active-listing operation, not equivalent to a local draft. Complete channel artifact routes remain unverified in 4C. | Direct seller to the channel-specific draft authority and missing-field blocker. Distinguish local readiness from provider eligibility, HUMAN review from single-use execution authorization, and all of these from publication. |
| Stock/mapping → orders | Inventory reservations/consume/release and local order projections exist; Phase 3 tests synthetic event conservation and races. | Genuine import, fulfillment and channel acknowledgement not certified. No manual-order workflow should be invented merely to populate an empty page. | Explain read-only projections and external prerequisites; retain source and synthetic labels. Order cancellation is not automatically restock or refund. |
| Orders → finance | Canonical immutable events/cost evidence feed current projections. Source fallback carries synthetic/unknown provenance after Phase 3B fixes. | **Historical confirmed limitation QA-P3-GAP-001:** current calculation upsert is not immutable historical accounting. `financial_router.py:940–984` now includes cost IDs, but overwrites the same scope/version row. | Label current/estimated projections and retain a separate accounting record if accepted. Exact historical reconstruction needs approved design/retention requirements; do not relabel mutable rows as snapshot history. |
| Finance/stock → Business Agent → Action Center | Operational signals, filtering/acknowledge/snooze/resolve/reopen, source links and advisory recommendations exist. | **Historical confirmed limitation QA-P3-GAP-002:** action request is advisory; `action_center_router.py:939–970` explicitly says no approval/execution recorded. SE-METRIC-001: publishing destination count is called sales channels connected; source-confirmed semantic mismatch, runtime fixture BLOCKED. | Route to each existing canonical HUMAN workflow. Use real metric authority/scope, not content counts as marketplace authorization. Acknowledge is not approve; resolve is not execute. |
| Interruption → safe continuation | Owned fixture process restart, committed-response retry, refresh and reconstruction evidence exist in earlier suites. | Host restart, power loss, worker recovery and encrypted independent restore are different gates. PC-first certification is **parked/unresolved**, not reopened by this audit. | Retain exact request identity after unknown outcome, read canonical state before retry. No permanent activation while required recovery proof and independent destination remain missing. |

## Three historical missing workflows: disposition

| Historical ID | Present conclusion | Criticality and scope |
| --- | --- | --- |
| QA-P3-GAP-001 | OPEN/BLOCKED; current cost lineage improved but immutable operational projection reconstruction absent. | Launch-critical **if** this application is the sole accounting/audit ledger. Otherwise important but deferrable only with explicit owner scope and separate retained records. No acceptance recorded. |
| QA-P3-GAP-002 | OPEN/BLOCKED; default-deny/advisory-only behavior is intentional and truthful; durable generic action lifecycle unsupported. | Launch-critical only if generic execution is a launch requirement. Prefer existing canonical action workflows; do not implement a second approval authority. |
| QA-P3-GAP-003 | Historical closure in Phase 4B, not reopened. | Opening stock is now supported and bounded-tested. Continue regression coverage; do not reimplement or treat Product quantity as its replacement. |

## Important source-led hypotheses, not confirmed runtime bugs

1. **SE-CONTEXT-001:** `/intelligence/trends/:contextId` is declared but the component
   does not consume ActivatedRoute; constructor loads active journey and selected
   contexts. Test two different legitimate contexts via deep links, reload and
   back/forward before deciding whether routing is broken or intentionally aliased.
2. **SE-CONTEXT-002:** CampaignVideo reads `id` but not declared `activityId`
   (`campaign-video.component.ts:76–104`); it renders campaign activities. Test two
   activities; a campaign overview heading cannot certify activity identity.
3. **SE-CONTEXT-003:** Ads route selector maps `/ads/accounts/:id` to `accounts`
   (`ads-workspace.component.ts:1457–1487`) and loads the list. Test two actual owned
   account IDs plus invalid IDs; classify intended list alias versus detail contract.
4. **SE-CONTEXT-004:** Missing-economics and Business Agent links from Catalog
   (`catalog-workspace.component.ts:138,148`) do not themselves carry the inspected
   product/opportunity ID. This is not proof of cross-product leakage: test with a
   different active journey and require explicit context choice or matched scope.

Two selection/lineage questions require specific follow-up, not a downstream UI
patch. **SE-AUTHORITY-001:** Catalog latest_shortlist, Journey and Business Agent
filter historical shortlist actions before choosing/counting them, whereas
`decision_readiness_service.py:140–152,391` reads the latest action then requires
shortlist. Later reject/archive/research_more may have different effects across
consumers; runtime behavior remains UNVERIFIED. **SE-AUTHORITY-002:** supplied
conversion goal is checked for ownership, but the inspected block does not prove
its association to the converted opportunity. Test two same-owner goals through
normal authorities, without inventing a second owner or direct row edits.

Current approval-note friction must not be copied from old screenshots:
`product-discovery-review.component.ts:188–209,363–399` already records an automatic
audit purpose and makes the additional note optional. The three policy/access
confirmations remain genuine HUMAN safeguards. Fresh browser validation is
BLOCKED, not a reason to remove them.

## Minimum coherent seller experience

Completion means a seller can finish a supported task and understand the safe
boundary, not that every menu has a green result. Required local minimum:

1. Choose research versus an existing-product operation without a forced wizard.
2. See owner/product/goal/supplier context, provenance, freshness and status on
   each handoff; unknown commercial facts remain UNKNOWN.
3. In permitted synthetic QA, reach selected opportunity → supplier review → DD →
   current economics → explicit canonical HUMAN decision, with missing/stale paths.
4. Expose existing selected-opportunity conversion, or explicitly document a
   supported manual entry path that does not pretend to carry lost lineage.
5. Create/edit a real seller-authored local Product, private image, SKU, counted
   opening stock and controlled listing draft without requiring live credentials.
6. Explain unavailable real import/publication and distinguish local estimates
   from operational financial records. No synthetic-to-permanent promotion.
7. Return/revise/retry/reload safely, keep idempotency and reject stale approvals;
   exercise keyboard/mobile and exact conditional accessibility nodes.
8. Resolve, explicitly scope or accept each open finding through a recorded owner
   decision and independent retest. Do not silently close recommendations.

Real business activation additionally needs the separate parked recovery proof,
host/key/destination review and genuine channel prerequisites. Those are not
features to fake or controls to disable to make this local audit pass.

## Coverage limits and next audit tests

Retain the original Phase 1–4C findings and archived reports. Current broad QA
uses marked per-run PostgreSQL and process/browser egress guards; ORM metadata
fixtures are not fresh migration certification. Artifact-dependent routes need
their own legitimate draft/version/HUMAN context, not guessed IDs. No real seller
accounts, marketplace rates, supplier facts, native mobile device or complete
screen-reader journey is established by these fixtures. See the
[completion backlog](prioritized-completion-backlog.md) for exact acceptance and
test requirements; this document itself runs no suite or database operation.
