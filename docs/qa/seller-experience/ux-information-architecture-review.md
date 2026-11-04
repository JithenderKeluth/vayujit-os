# Seller experience: information architecture and UX review

Audit and design only, 2026-10-27. No application source, approval authority,
database, marketplace, or backup implementation was changed by this review.

## Evidence standard and limits

`SOURCE VERIFIED` below means the statement is visible in current code, not that
the complete interaction passed a browser test. `HISTORICAL EXECUTION` cites the
preserved Phase 4C/earlier evidence; it is not a new run. `UNVERIFIED` identifies
an interaction or consequence requiring a disposable authenticated test.
Recommendations are not silently promoted to confirmed functional defects.

Read: the attached audit specification; Phase 4C validation, findings, journeys,
route/control coverage; the current finding ledger; and the existing Seller OS
information architecture, journey map, and component architecture. Existing open
findings remain open. Phase 4C explicitly says application certification
INCOMPLETE and first real operation NO-GO. PC-first backup certification is
separate, unresolved, and parked for this assignment.

## What exists and should be retained

Current `apps/web/src/app/app.routes.ts` has **155 path declarations**, consistent
with the Phase 4C reconciliation: six redirects are not business screens. Route
count is not workflow coverage. Seller navigation has **7 primary groups / 23
links** and **3 advanced groups / 28 links**: 51 link definitions to 50 unique
paths. Supplier engagement is linked in both groups. Desktop and mobile reuse
the same component, rather than separate navigation authorities.

The shell already supplies authenticated owner identity, active-brand context,
skip navigation, one main landmark, a mobile disclosure menu and breadcrumbs
(`app.component.html:1`, `:21`, `:30`, `:40`). Preserve these. Domain routes are
guarded with `authGuard`; the navigation explicitly presents links without
deciding access (`shared/seller-navigation.component.ts:9`). Route declarations,
discoverability and authorization are different concerns.

The code already has reusable page headers, loading/empty/error/blocked states,
evidence labels, backend-driven Commerce Journey stages and next actions,
explicit HUMAN product selection, supplier comparison, immutable commercial
snapshots, listing drafts, stock ledger, read-only orders and financial evidence.
Do not rebuild these as a new wizard, a second approval inbox, a browser-side
calculator, or another business-state store.

## Navigation and terminology findings

Paths below are relative to `apps/web/src/app/` unless otherwise stated.

| Stable audit ID / priority | Source-verified observation | Seller impact and bounded recommendation | Verification required |
| --- | --- | --- | --- |
| SE-HANDOFF-002 / P1 | Primary **Suppliers** goes to `/intelligence/sourcing` (`shared/seller-navigation.component.ts:133`), whose title is **Make a sourcing decision** (`intelligence/sourcing-workspace.component.ts:40`). Actual **Find suppliers** is `/intelligence/cross-marketplace` (`intelligence/supplier-journey-nav.component.ts:132`), labeled **Cross-marketplace Suppliers** in Advanced (`shared/seller-navigation.component.ts:179`). | A first-time seller looking for candidates enters a requirement/quote/scenario workspace instead. Make the primary Suppliers entry lead to the existing discovery surface; retain sourcing under Commercial evaluation. No discovery engine change is implied. | Authenticated first-time task from Dashboard to selected-product discovery, with no candidates, one candidate, and blocked context. |
| SE-HANDOFF-001 / P1 | Catalog empty copy offers conversion of a HUMAN-selected opportunity (`catalog/catalog-workspace.component.ts:234`), but the inspected CatalogService and Product Opportunity workspace expose no conversion request. Existing backend test names `/api/v1/catalog/opportunities/{id}/convert` (`apps/api/tests/test_pr_sos_01_catalog.py:53`). | Selected research can become a dead end, or force manual recreation that loses lineage. Expose the existing conversion authority on an eligible selected opportunity with an explicit review and a link to the created Product record. Do not invent conversion semantics. | Execute existing conversion, owner/HUMAN/selection prerequisites, replay and lineage tests, then browser selected opportunity → Catalog → refresh. Backend availability is source evidence; this handoff is not newly runtime-certified. |
| SE-IA-001 / P2 | Both **Catalog** and **Products** are adjacent primary links (`shared/seller-navigation.component.ts:141`), and Catalog links back to Product record/edit (`catalog/catalog-workspace.component.ts:80`). They share product IDs but have distinct detail experiences. | The seller must guess whether catalog and product are separate records. Present one Products entry with Product facts, Images/variants, Channel drafts and Readiness sections; retain existing deep links as compatible views. This is presentation consolidation, not merging authorities. | Back/forward/deep links, creation/edit/cancel and Catalog detail with one persisted product. |
| SE-IA-002 / P2 | Shortlists, Supplier Verification and Sourcing Economics are Advanced links (`shared/seller-navigation.component.ts:185`); supplier engagement appears twice (`:135`, `:188`). Marketplace overview/accounts are not primary navigation entries, although Listings/Inventory/Orders are. | Core evidence and account prerequisites are less prominent than later operations. Add contextual links on the selected supplier/product and a visible Marketplace setup destination; reserve Advanced for technical/source tools. Avoid multiplying the entire sidebar. | Empty account/setup state, selected supplier task, mobile menu scanning and keyboard ordering. |
| SE-IA-003 / P2 | **Integrations** redirects to publishing connectors (`shared/seller-navigation.component.ts:207`, `app.routes.ts:676`) while **Provider Integrations** and AI Providers are separate. | “Integrations” can be mistaken for Amazon/Flipkart onboarding. Use specific labels: Publishing connectors, Research/AI providers, Marketplace accounts. Indicate unconfigured, local-only and externally pending distinctly. | Inspect labels/targets without credentials; never imply registration grants API access. |

None of these observations proves that a route is unreachable. Advanced and
contextual links are reachable alternatives; the finding is the mismatch between
seller task and entry-point label.

## Handoff and recovery findings

| Stable audit ID / priority | Source and current boundary | Minimal proposed correction and acceptance evidence |
| --- | --- | --- |
| SE-HANDOFF-003 / P1 candidate, runtime UNVERIFIED | Shared SupplierJourneyNav links contain only `step.url`, no query parameters (`intelligence/supplier-journey-nav.component.ts:30`, `:132`). Some downstream pages recover the active journey instead of the originating selected opportunity. Opportunity detail DD/scenario links similarly omit item context, while its Economics link passes `opportunity_id` (`intelligence/product-opportunity-workspace.component.ts:1195`). | Carry an owner-validated context reference to the existing target authority. Test two legitimately persisted goals/opportunities, active B while reviewing A, supplier switching, back/forward, reload and new tab. Prove no A/B context substitution; do not infer a current vulnerability or weaken API owner checks. |
| SE-CONTEXT-004 / P1 candidate, runtime UNVERIFIED | Catalog economics unavailable state links to all Product Opportunities (`catalog/catalog-workspace.component.ts:137`–`:138`); Business Agent guidance links to the unscoped workspace (`:148`), even when the Product detail contains canonical lineage (`:96`). | If the existing lineage supports an owning opportunity or goal, provide a scoped return to that exact context. Manual products must receive an honest no-linked-opportunity explanation, not an invented research identity. Test products A/B with active journey B while catalog A is open. |
| SE-CONTEXT-005 / P1 candidate, runtime UNVERIFIED | Supplier discovery emits `supplier_id` in `economicsParams()` (`intelligence/cross-marketplace-supplier.component.ts:979`); Economics initialization reads only `opportunity_id` and `journey_id` (`intelligence/sourcing-economics-workspace.component.ts:3008`). | Decide whether supplier is a supported contract parameter. If supported, resolve it against the opportunity's canonical supplier membership; otherwise label the link **Review product economics** rather than imply a selected-supplier view. Two-supplier browser assertions must verify the exact assessment/supplier, not just a page heading. |
| SE-CONTEXT-006 / P2 candidate, runtime UNVERIFIED | Catalog detail holds a snapshot `selectedId` (`catalog/catalog-workspace.component.ts:266`); DD reads snapshot opportunity/supplier query parameters (`intelligence/supplier-due-diligence.component.ts:303`); Economics also initializes snapshot context. Supplier discovery does subscribe for supplier query changes (`intelligence/cross-marketplace-supplier.component.ts:898`) but only initializes opportunity context once (`:911`). | Audit same-component URL transitions before changing code. Browser A→B in one tab, Back, Forward and refresh must display persisted B/A correctly or explicitly reload. Do not declare every snapshot use broken: route recreation may make it safe; same-component reuse is the test prerequisite. |
| SE-STATE-001 / P2 candidate, runtime UNVERIFIED | CommerceJourneyContext catches active-journey errors and sets null (`commerce-journey-context.component.ts:114`); Dashboard's optional journey loader also returns null (`operations/dashboard.component.ts:387`). | Distinguish **no journey** from **journey unavailable** without making optional guidance block all work. Show a retry and retain explicit scoped links. Test timeout/401/500 versus genuine empty response; a missing projection must not imply the seller has no work. |
| SE-ERROR-001 / P1 candidate, runtime UNVERIFIED | Dashboard `init()` awaits brand list and active brand outside `load()`'s try/finally (`operations/dashboard.component.ts:238`); `ngOnInit` starts it with `void`. The spinner is cleared only inside `load()` (`:258`). | A rejected prerequisite can prevent reaching the useful retry state. Inject brand-list/active-brand failures and verify finite loading, useful error and retry. If reproduced, wrap initialization at its existing boundary; do not hide a failed owner/brand lookup as an empty workspace. |
| SE-ERROR-002 / P2 candidate, runtime UNVERIFIED | Action Center load errors have a visible retry (`operations/action-center.component.ts:23`), but inspect/transition/policy methods await their APIs without local catch/busy feedback (`:114` onward). | Test failed inspect, resolve, scan and emergency-stop changes with no source mutation. Each must show failure, prevent misleading success and recover without duplicate effects. Do not implement another execution lifecycle inside Action Center. |

Other retained context-contract concerns from Phase 4C remain UNVERIFIED
(`SE-CONTEXT-001` Trends, `SE-CONTEXT-002` Campaign Video, `SE-CONTEXT-003` Ads):
`/intelligence/trends/:contextId` loads active journey (`trend-intelligence-workspace.component.ts:412`);
Ads account-detail URL maps to accounts list (`ads/ads-workspace.component.ts:1457`);
Campaign Video consumes campaign ID but not declared activity ID
(`campaigns/campaign-video.component.ts:76`). Existing route declarations do not
establish exact artifact identity. Two distinct legitimate contexts are necessary
to prove or disprove each concern.

## Home, evidence, economics and forms

### Home must distinguish operating signals from content-system counters

Dashboard already renders active journey, attention items, quick actions and
advanced technical health (`operations/dashboard.component.ts:35`, `:81`, `:165`).
Keep this foundation. Its `opportunities()` labels `active_destinations` as
**sales channels connected** and routes to Marketplaces (`:427`), whereas the
metric's own card is **Active destinations**, linking to publishing destinations
(`:447`). The backend counts active `PublishingDestination` rows
(`apps/api/vayujit_api/operations/router.py:195`). **SE-METRIC-001 / P1 semantic
risk:** a configured publishing destination must not be presented as authorized
Amazon/Flipkart connectivity. Use the metric's actual name and scope. A synthetic/local
account must never create a “real connected marketplace” assurance.

The same function labels `total_products` “ready to review” (`:404`). A count of
product records is not canonical readiness. Prefer “Products in your workspace”
and separately display existing CatalogReadiness/marketplace eligibility when
the API provides it. Do not derive commercial viability from product count.

### Preserve evidence, reduce competing controls

Product Opportunity has a real HUMAN shortlist boundary (`product-opportunity-workspace.component.ts:2368`)
and passes scope to supplier discovery (`:2173`). Do not enable supplier research
just because a card exists, silently create an assessment, or remove eligibility
checks to increase the success rate. Explain the missing current assessment
beside its disabled selection action (`:712`) and link to the supported assessment
operation. Source approval is permission to fetch, not verification of a product.

Current source-review UI already makes the note **optional**, automatically records
an audit purpose and retains three explicit policy/access confirmations
(`intelligence/product-discovery-review.component.ts:185`, `:199`, `:226`, `:363`).
The owner's historical screenshot requiring a reason is not proof that the current
note remains required. Do not propose deleting existing safeguards. Explain scope,
future reuse and the next **Continue product discovery** action; do not guarantee
that approval produces a product.

Economics is a 4,085-line component; Opportunity 2,997; Business Agent 1,408
(current line counts, not bug counts). Economics combines live supplier-source
certification (`sourcing-economics-workspace.component.ts:670`), commercial decisions,
comparison, due-diligence readiness, input entry and calculations. It even exposes
explicit immutable snapshot UUID inputs (`:2312`–`:2340`). This concentration
explains why “Review economics” can introduce unrelated source/authorization work.
**SE-UX-001 / P2:** progressive disclosure and in-page navigation should separate
seller questions from advanced authority inspection. Retain immutable snapshots,
evidence, unknowns, contradictions and HUMAN decisions; do not collapse distinct
source approval and one-use live execution authorization into one button.

This complements, rather than closes, `QA-P2-UX-ECONOMICS-DESKTOP/MOBILE` (historical
16,236px/43,325px documents) and `QA-P4-UX-RESEARCH-LENGTH`. A long page alone is a
usability observation; measure seller task completion and error rate before a
larger component redesign.

### Product facts are not counted stock or commercial evidence

The Product form contains Price, Currency, Cost and Inventory Quantity
(`products/product-form.component.ts:90`, `:115`). Currency defaults to USD (`:193`),
preserving the existing `QA-UX-CURRENCY-DESKTOP/MOBILE` findings. Canonical inventory
has a distinct opening-stock and movement ledger (`marketplaces/unified-inventory.component.ts:41`,
`:98`, `:170`). **SE-UX-002 / P1 clarity risk:** label Product Quantity's scope and
link to counted Opening stock; do not make editing master metadata create a stock
movement. Similarly Product Cost must not be described as a verified supplier
quote or complete landed cost. Require provenance through the existing authority.

Catalog draft editing asks for Image reference and Compliance JSON
(`catalog/catalog-workspace.component.ts:179`, `:183`). **SE-UX-003 / P2:** offer the
existing private media picker and provider-defined compliance controls where the
contract supports them; retain JSON as advanced inspection. No invented compliance
rules, tax treatment or marketplace requirements.

## Accessibility and responsive disposition

Historical Phase 4C: 34 scans, no recorded violations, eight incomplete occurrences;
this is not a WCAG conformance certificate. Preserve `QA-P4A-A11Y-MANUAL-001`,
stock-cell review, offscreen/conditional nodes, keyboard reading order, modal focus,
zoom and high-contrast checks. The two desktop overflow findings and long mobile
economics finding remain open; no new screenshot was taken by this source review.

Existing focus styles, native disclosures, labels, table captions and state
components are assets to reuse. Proposed sticky summaries/jump links need tests
for focus not hidden by sticky content, 200/400% zoom, keyboard activation,
screen-reader names and 360/390/768/1024/1440 CSS-pixel layouts. Never remove
evidence nodes or axe rules to obtain a green report.

## Prioritized design order and evidence needed

1. Repair task labels/entry points and expose the existing conversion handoff.
2. Test and then correct exact scoped navigation; keep owner/selection/stale gates.
3. Make initialization/action failures recoverable and status copy truthful.
4. Introduce a selected product/supplier commercial summary with accessible jump
   links, preserving all detailed provenance below.
5. Clarify catalog/product/stock/cost boundaries and explicitly confirmed INR.
6. Complete retained manual/accessibility and unsupported-workflow decisions.

No new runtime test was executed by this document's author. Read-only checks used
`rg --files`, `rg -n`, `Get-Content`, source regex counts, and file line counts.
The enclosing audit's actual execution evidence belongs in `audit-validation.md`;
do not sum source observations with passed tests or close inherited findings.

