# Actual application inventory — seller-experience audit

Audit/design only, 2026-10-27. No application code, database, migrations, provider
configuration or prior finding disposition was changed by this inventory.

## Evidence vocabulary and scope

- **SOURCE VERIFIED** means the named declaration, query or control exists in the
  current source. It is not a fresh execution, a complete security review, or proof
  that the UI invokes it correctly.
- **HISTORICAL BOUNDED** means a named previous QA record supplies execution
  evidence. It is retained as history, not rerun or silently upgraded here.
- **UNVERIFIED** means the current scenario has not been executed with legitimate
  persisted context. Missing credentials, authorization or fixtures are not
  permission to fabricate success.

Starting evidence: [4C validation](../phase-4c-validation.md), [journeys](../phase-4c-journeys.md),
[12 open findings](../phase-4c-findings.md), [route/control reconciliation](../phase-4c-route-control-coverage.md)
and the existing defect backlog. Those records explicitly classify application
certification INCOMPLETE and first real operation NO-GO. The PC-first recovery
workstream remains parked; its later diagnostic improvements do not establish a
successful encrypted restore or independent physical backup destination.

Read-only census of the current source:

| Surface | Count | Meaning / limit |
| --- | ---: | --- |
| Angular route declarations | 155 | Fresh TypeScript AST inventory: 149 PAGE + six REDIRECT; guest and artifact-dependent routes included; not 149 complete seller workflows. |
| Primary navigation | 7 groups / 23 link definitions | Current `shared/seller-navigation.component.ts`; mobile rendering is a separate runtime question. |
| Advanced navigation | 3 groups / 28 link definitions | Combined navigation has 51 definitions / 50 unique paths because engagement repeats. |
| API Python files | 464 | `rg --files apps/api/vayujit_api -g '*.py'`; no app import or database access. |
| API router-bearing files | 85 | Files containing `APIRouter(`, not distinct URL prefixes. |
| Python AST API declarations | 1,610 | Fresh existing audit's declaration inventory, including multiline syntax; not deduplicated mounted runtime OpenAPI operations. |
| Static HTTP decorator occurrences | 1,605 | Line-start `@name.(get|post|patch|put|delete|options|head)(` across API source; aliases, hidden fixture and operational routes included. Not deduplicated runtime OpenAPI operations. |
| AST model declarations / frontend spec files | 421 / 71 | Source inventory, not unique SQL tables, complete invariants or executed test coverage. |
| Migration Python files | 164 | File enumeration, not proof that a particular database applied them or that upgrades/downgrades pass. |

The durable [machine-readable inventory](application-inventory.json) contains all
155 current routes/components, 1,610 API declarations and 421 model declarations
from the existing offline AST auditor; current raw capture is
`tmp/seller-experience-audit/source-inventory.json`. The regex census deliberately
remains labeled as a separate lower-level measurement, not a contradictory API
coverage total. Neither census imports the API or resolves runtime OpenAPI.

Route-by-route declarations/components and prior coverage dispositions are retained in the existing
[155-row route matrix](../phase-4c-route-control-coverage.md#all-current-route-declarations).
The current source still has the same declaration count; that does not close the
20 artifact-dependent declarations not exercised in 4C. Navigation/IA specifics
are assessed separately in [UX review](ux-information-architecture-review.md).

## Canonical seller capabilities and authorities

Paths below are relative to `apps/api/vayujit_api/`. `main.py:203–293` explicitly
mounts the reviewed router families. A route family may expose administrative or
diagnostic operations without a dedicated seller screen.

| Seller task / principal UI | Actual canonical backend operation family | Persisted artifacts and dependencies | Implemented boundary / missing or unverified segment |
| --- | --- | --- | --- |
| Owner setup/login (`/setup`, `/login`) | `identity/router.py:49–130`: setup-status, setup-owner, login/logout, me | `User`, `AuthSession`, hashed token/password; current-user dependency | SOURCE VERIFIED cookie authentication and one-owner setup conflict. Account recovery/lockout/expired-session journey not comprehensively certified. `ownerExists` is API state, not an `.env` switch. |
| Brand/product master (`/brands`, `/products`, Catalog) | `brands/router.py`, `products/router.py` | Owner-scoped `Brand`, `Product`; SKU/barcode/slug uniqueness; `ProductStatus` draft/active/archived | CRUD exists. Product master quantity is not the unified inventory reservation ledger. New-product USD default remains an open historical UX finding. |
| Goal → plan → run (`/intelligence/business-agent`) | `intelligence/business_agent_router.py:611–854`: goals CRUD, plan/revise, run create/start/pause/resume/cancel/retry, approvals approve/reject | `BusinessAgentGoal/Plan/Step/Run/Attempt/Approval/Artifact/Finding/ToolInvocation/Checkpoint` | Separate authorities, not one button. Deleting goal and expected first-plan/latest-run 404 states have explicit APIs. Real research is not guaranteed; retry cannot manufacture eligible evidence. |
| Current research/journey guidance | `/api/v1/commerce-journeys/active`, `/{id}`, next-action, context-confirmation, decision-brief, decision | `commerce_journey.py` projects existing goal/run/opportunity/shortlist/DD/scenario/decision records; confirmations/legacy decisions are goal provenance | SOURCE VERIFIED **projection**, not a second persisted workflow engine or a complete inventory/order/finance lifecycle. Eight stages GOAL/RESEARCH/COMPARE/SOURCE/VERIFY/ECONOMICS/DECIDE/LAUNCH. |
| Opportunities/research (`/intelligence/product-opportunities`) | `product_opportunity_router.py`: create/list/detail/update/archive, constraints/assessments/history/current, market-research; separate intelligence/commercial/score/synthesis routers | `ProductOpportunity`, immutable constraint versions/input snapshots/assessments, outputs/scores/decisions; optional Product link | A research candidate is not catalog conversion, HUMAN selection, profitable business, verified supplier or inventory. SOURCE VERIFIED explicit category eligibility uses fetched product evidence (`product_research.py:526–1110`). Historical cached/mismatched candidate concerns require current scenario execution, not a promise that every goal will return three products. |
| Explicit product decision | `product_opportunity_scoring_router.py:452–490`, scoring service `add_decision:603`; decision endpoint is opportunity + assessment scoped | `ProductOpportunityDecision` refers to assessment + score, owner/idempotency key | Backend supports watch/research_more/shortlist/reject/archive. UI prominently exposes shortlist; supported rejection/revision discoverability needs review. **Source inconsistency S-SEL below** must not be mistaken for a confirmed live authorization bypass. |
| Live source permission and evidence | `external_router.py`, `website_router.py`; `live_supplier_certification_router.py:84–228` source approvals, separate single-use execution authorization/eligibility/revoke/execute/evidence review | Source registry, fetch/evidence records, certification runs/authorizations/executions, freshness/trust/review metadata | Existing HUMAN source approval is not supplier verification, commercial approval or permission to contact. Source approval and live execution authorization remain separate. Genuine live acquisition UNVERIFIED in this audit and expressly not executed. |
| Supplier candidates/detail | `supplier_router.py:315–640`: searches, research, manual supplier, compare, freshness/diversity/history/risk, contacts/documents/claims/terms, decision/verification | `Supplier`, `SupplierSearch`, `SupplierSource`, `SupplierProduct`, `SupplierEvidence`, verification/commercial terms/claims/history/opportunity match; cross-marketplace canonical supplier/link models | Supplier discovery derives selected-product sourcing concept (`supplier_router.py:323`); directory search results ≠ proven manufacturers. Direct research also supports query input, so not every research call is evidence of product selection. Primary “Suppliers” currently lands in sourcing decisions; actual discovery is less discoverable. |
| Compare and HUMAN shortlist | `supplier_comparison_router.py`, `shortlisting_router.py`: context/version/shortlist/compare/readiness/decision/handoff | `SupplierComparisonSnapshot`, `SupplierShortlistContext/Version/ScoreVersion/Decision/Handoff/Event` | Canonical contexts/versions already exist. One supplier cannot be honestly ranked against absent alternatives. Claims and unknown MOQ/price/lead time are not filled automatically. |
| Due diligence (`/intelligence/supplier-due-diligence`) | `due_diligence_router.py:80–308`: contexts/assess/gaps/plans/run/tasks/gap actions/recovery/readiness/history/report | `SupplierDueDiligenceContext/Assessment/EvidenceGap/ResearchPlan/ResearchTask`; supplier/opportunity/product scope | Evidence gaps, contradictions and bounded research plan are implemented. DD sufficiency is not procurement approval. Plain supplier journey links and supplier switching need two-context browser tests. |
| Sourcing/quotes/inspection | `sourcing_router.py`: requirements/version, RFQ/version/approve/dispatch, quotes/compare, samples/status/evaluate, inspections/findings, negotiation/scenario/decision | Requirement, RFQ, SupplierQuote/Line/Version, sample, inspection, scenario, decision, worker/history records | These capabilities exist; do not rebuild a generic supplier system. Different workspaces and legacy/canonical scenarios complicate terminology. Dispatch/contact is a separate controlled external boundary and was not exercised. |
| Supplier engagement/response | `engagement_router.py`: create/draft/approve/cancel/history/send-readiness/eligibility/authorization/send/retry; `supplier_response_router.py`: create/list/detail/review/promote | `SupplierEngagement/Draft/Approval/Event`, inbound response/extraction/review/promotion | HUMAN approval, draft and send authorization are distinct. Manually entered response is not automatically verified supplier evidence. No email/RFQ/contact execution authorized by this audit. |
| Economics (`/intelligence/sourcing-economics`) | Commercial readiness → landed cost → unit economics; economic assumptions/scenarios; `landed_cost_service.py:271–347` freshness issue; scenario/sensitivity/capital/cash timeline | `CommercialReadinessSnapshot`, `EconomicCalculation` and component/input lineage; unit-economics, sourcing scenario versions | SOURCE VERIFIED material value/basis/currency/provenance/freshness/reference/supplier/scope changes invalidate landed lineage; equivalent snapshots do not automatically stale. UNKNOWN never supplies a default zero. Historical independent Decimal/freshness tests do not certify actual GST/fees. Long pages remain a P2 usability concern. |
| Commercial/launch HUMAN decision | `decision_readiness_router.py`, `decision_synthesis_router.py`, `decision_recommendation_router.py`; service `create_human_decision:371` | Decision evidence/synthesis/recommendation/HumanDecision, owner/opportunity/goal/supplier scope and fingerprints | PostgreSQL advisory lock + unique key; exact replay vs conflict, latest synthesis and PROCEED eligibility checked. Reuse these authorities; Action Center acknowledgement is not their equivalent. |
| Catalog conversion, variants, media | `catalog/router.py:122–212`, `catalog/service.py:151–291`, variants/images/economics/associate-supplier | `CatalogProductLineage` → Product + opportunity/goal/assessment/selection; variants/private image associations/supplier associations | Conversion exists and retains unknown commercial values, selection provenance and claims-unverified marker. **No frontend conversion call found** in inspected CatalogService/opportunity component despite empty-state guidance. S-CAT below requires distinct-goal test. |
| Local listing draft/review/readiness | `/api/v1/catalog/listing-drafts`, patch/review; product/readiness | `CatalogListingDraft`, version/review/missing fields | `catalog/service.py:760`: BLOCKED or READY_FOR_FUTURE_SUBMISSION; still local, no remote listing ID. Does not imply API authorization, eligibility or publication. |
| Initial stock (`/marketplaces/inventory/opening`) | `inventory_router.py:118–251` creates inventory item/opening movement/audit atomically; adjustment/ledger/mappings/reservations/release/consume | `InventoryItem`, immutable `InventoryMovement` opening intent, reservation, `ChannelSkuMapping` | SOURCE VERIFIED physical/nonarchived product/variant, owner/key replay and scope checks; no duplicate SKU/location. Quantity is a deliberate HUMAN count, not hypothetical research demand or inferred procurement. 4B has historical bounded race/replay/rollback evidence. |
| Marketplace setup and mapping | Generic `commerce/router.py`; channel-specific Amazon/Flipkart/Meesho routers; `connectivity_router.py` | MarketplaceAccount/category/listing/snapshot/import job, channel mapping/draft/review/execution authorization | Account response explicitly SYNTHETIC / UNVERIFIED permissions. Connectivity `start_import:310` rejects non-SYNTHETIC mode before replay. Seller registration and genuine API access are external prerequisites, not missing local fake records. |
| Controlled channel listing operation | Amazon/Flipkart/Meesho channel routers: draft/preview/readiness/review/authorization/revoke/execute/status/reconcile variants | Version/fingerprint-bound approval/authorization/execution records, account/catalog mapping | Local transport path exists; no real SP-API/Flipkart certification claimed. Generic `POST /marketplaces/listings` invokes deterministic fake connector and returns active/fake remote ID—**not local draft creation**. Keep these operations distinct in fixtures and UX. |
| Orders (`/marketplaces/orders`) | `orders_router.py`: list/detail/reconciliation/insights, explicit `/fake/events`; channel import adapters | MarketplaceOrder/item/event/refund/return/shipment and reservation lineage | SOURCE VERIFIED account lock before replay, owner/account/event identity, stock reservation lifecycle. Read-only seller order review exists; no generic manual fulfillment/refund authority invented. Actual authorized live ingestion/fulfillment UNVERIFIED. |
| Finance (`/marketplaces/financials` and subviews) | `financial_router.py`: events/costs/fee rules/summary/recalculate/calculations/sales/profitability/missing costs/refunds/trends/fees/settlements/reconciliation/alerts/Business Agent | FinancialEvent/CostEvidence/FeeRule/CalculationSnapshot/SettlementReconciliation + order/payment/shipment sources | Explicit Decimal inputs/provenance; `_provenance:450` synthetic ancestry dominates claims, missing/unrecognized provenance UNKNOWN. Current snapshot unique per owner/scope/calculation version and overwritten: **not immutable historical accounting**. Current source includes cost evidence IDs. |
| Improvement/Action Center | `operations/action_center_router.py`: scan/list/briefing/signal/history/acknowledge/snooze/resolve/reopen/action/policy/notifications | OperationalSignal/Transition/AutomationPolicy/Notification/BriefingSnapshot | SOURCE VERIFIED status filtering and persisted lifecycle. `request_action:939–968` rejects AI/SYSTEM and consequential external action types; returns advisory-only with no approval/execution row. Retain default-deny; generic durable execution remains unsupported. |
| Launch readiness / settings / operations | Hardening/control-center/settings/staging routers; existing deployment/runbooks | Readiness projection, health/maintenance/security/backup evidence, existing workflow/approval authorities | Local warnings are evidence of prerequisites, not instruction to disable controls. Recovery certification is pending and untouched; public deployment/real seller activation not authorized. |
| Content/growth/automation | AI studio/text/SEO/image/bulk; campaign/video/social/ads/publishing/workflow routes | Generated artifacts/versions/approval records, media, campaigns/activities, publishing jobs/schedules/executions | Extensive implemented API surface, partly Advanced navigation and artifact-dependent. Not core commerce proof. Real providers, publishing workers and external writes remain unauthorized. Detailed conditional state correctness remains UNVERIFIED unless named prior evidence exists. |

## Lineage and state boundaries that must not be collapsed

1. **Goal, plan, run and projection:** `BusinessAgentGoal` contains raw/structured
   goal and provenance; plan and run are separate durable records. The journey
   projection selects goal-scoped candidates by run idempotency prefix or explicit
   opportunity reference, then filters category (`commerce_journey.py:145–178`).
2. **Opportunity identity vs seller commitment:** `ProductOpportunity.product_id`
   may already identify a Product created by research. Catalog conversion still
   requires shortlist and adds lineage. The presence of Product alone must not be
   presented as a HUMAN catalog conversion.
3. **Selection vs evidence vs commercial permission:** shortlist decision,
   assessment score, source approval, DD assessment and commercial HUMAN decision
   are different records. A usable page, claim or source is not verified profit or
   permission to order/contact/publish.
4. **Research vs stock:** catalog Product quantity, InventoryItem balances,
   InventoryMovement ledger and marketplace inventory/sync are distinct. Opening
   stock records real count intent; it is not procurement receipt or remote stock
   publication.
5. **Scenario vs operational financial truth:** immutable scenario calculations
   preserve modeling assumptions; operational FinancialCalculationSnapshot is a
   current projection. Missing price, fees or settlement must stay UNKNOWN and
   synthetic provider ancestry must remain visible after fallback/reload.
6. **Local channel preparation vs external marketplace:** CatalogListingDraft,
   MarketplaceListing fake remote IDs and channel-specific approval/authorization
   are separate. Connectivity is explicitly SYNTHETIC-only in the reviewed code;
   do not promote these accounts/orders/events into production.

The current category eligibility guard is an observed-text token-overlap policy,
not an authoritative marketplace taxonomy integration: `product_research.py:93–114`
accepts any non-stopword requested-category token matched in observed name,
category, subcategory, description or canonical URL. Journey matching at `:78`
compares category/subcategory tokens. These facts establish a guard exists, not
that every multiword category/synonym/incidental URL match is correct. Such cases,
cached reuse under another goal and candidate exclusion need focused persisted
relevance tests before claiming category integrity or a current wrong-result bug.

## New source-level concerns requiring bounded persisted reproduction

These do not close or rewrite previous findings. Runtime/security consequences
are **UNVERIFIED**. Preserve their source evidence when triaging the completion backlog.

### S-SEL / SE-AUTHORITY-001 — inconsistent “current selection” projections

- Supported API: `product_opportunity_scoring_schemas.py:92–97` permits `reject`
  and `shortlist`; `scoring_router.py:452–490` uses the same opportunity/assessment
  decision endpoint. `scoring_service.py:603–630` appends one row for each new key;
  the default key includes score and action, so reject and shortlist do not share a
  key. The decision method does not remove prior shortlist rows.
- `catalog/service.py:101–115` filters `action == shortlist` **before** descending
  timestamp/limit; `commerce_journey.py:181–207` similarly counts/selects shortlist
  rows; `business_agent_service.py:155–166` checks any shortlist exists.
- In contrast, `decision_readiness_service.py:140` obtains the most recent decision
  across actions and at `:391` requires shortlist for downstream decisions. That
  is a confirmed query-shape inconsistency, not proof every downstream operation
  succeeds after rejection. Later guards/real UI behavior have not been exercised.
- Required test: use canonical score/assessment, shortlist, then reject with a
  distinct key; compare current readiness, journey, run continuation and local
  catalog conversion. Repeat fresh process, latest assessment, watch/research_more,
  ties and explicit reselection. Preserve historical decisions; no external action.
- Additional replay concern: basic `add_decision` returns an existing same-owner key
  without comparing changed intent. The stronger commercial HUMAN authority does
  compare intent. Test changed action/opportunity/assessment/rationale replay
  before assigning a defect consequence or designing a shared contract.

### S-CAT / SE-AUTHORITY-002 — optional goal context and repeated conversion

`catalog/service.py:162–171` verifies that supplied `goal_id` belongs to the owner,
but the inspected conversion body does not check that this goal produced/selected
the opportunity. Existing lineage replay returns the Product without reconciling
new goal/SKU/brand intent. This may be an intentional product-level conversion
contract; a two-goal/changed-intent persisted test and documented contract decision
are required before claiming wrong-goal mutation or proposing new authority.

### S-SUP / SE-HANDOFF-003 — query context and discovery handoff

`supplier_router.py:323–421` accepts explicit opportunity or projected current
selection and preserves a derived sourcing concept. It also supports direct
query-based research. UI plain links can drop selection/supplier context; direct
research support must not be mislabeled an authorization bypass. Test two selected
products and two suppliers against all plain links, browser refresh/history and
actual API bodies. Keep “exploratory search” separate from HUMAN selected-product
continuation.

### Manual product → sourcing economics limitation

`catalog/service.py:517–541` returns `available=False` when a manually created
product has no opportunity lineage, explaining that canonical sourcing economics
require a Product Opportunity. Operational financial cost entry still exists, so
this is not “no product-cost functionality.” The product-first seller journey
needs an explicit scope decision: explain the separate actual-cost workflow and
evaluate a supported link into existing scenario authorities rather than creating
fictional research evidence to unlock the screen. Supplier association at `:546`
also deliberately rejects `status=accepted`; review-required association is not
HUMAN approval. Neither boundary should be silently weakened.

## Schema/migration evidence

Inspected actual models and migration bodies, not just roadmap claims:

- `identity/models.py:23`: singleton-key check `ck_users_single_owner` plus unique
  singleton key; `alembic/versions/20260727_0002_local_owner_auth.py:37` creates it.
  Two-owner shared-database fixtures violate the architecture; owner isolation
  tests must use foreign/absent IDs or separate installations.
- `20261016_0156_seller_catalog_listing_preparation.py` creates catalog lineage,
  variants, supplier associations/drafts with owner/product uniqueness and FKs.
- `20261201_0143_pr_sos_05_financial_intelligence.py` defines financial tables and
  `20261202_0145_pr_sos_06_operational_intelligence.py` signal categories/status,
  owner/fingerprint and transition-idempotency constraints.
- `20261203_0146_pr_sos_08_connectivity.py` records owner/account/operation import
  jobs; allowed operations catalog/orders/inventory/financial and indexed scope.

Filename dates/revision identifiers are source identifiers, not audit execution
dates. No migration chain, fresh installation, downgrade or database schema was
executed by this inventory; actual deployment applicability is UNVERIFIED.

## Complete router-file census

Source root: `apps/api/vayujit_api/`. Numbers are static HTTP decorator
occurrences, not unique endpoints or proof of UI coverage. All 85 router-bearing
files are enumerated; detailed core behavior is traced above. Auxiliary growth
routers were inventoried, not exhaustively audited for every domain contract.

| Module | Files and decorator occurrences |
| --- | --- |
| Identity / configuration | `identity/router.py` 5; `brands/router.py` 8; `products/router.py` 8; `catalog/router.py` 17; `providers/router.py` 3; `settings/router.py` 8; `media/router.py` 6 |
| Commerce | `commerce/router.py` 24; `amazon_router.py` 41; `flipkart_router.py` 46; `meesho_router.py` 41; `connectivity_router.py` 7; `inventory_router.py` 10; `orders_router.py` 5; `financial_router.py` 22; `marketplace_video.py` 20 |
| Operations | `operations/router.py` 5; `control_center.py` 43; `action_center_router.py` 13; `hardening.py` 10; `staging_router.py` 3 |
| AI | `ai/router.py` 25; `studio_router.py` 40; `seo_router.py` 19; `image_router.py` 41; `bulk_router.py` 10 |
| Marketing / content | `ads/router.py` 50; `ads/optimization_router.py` 44; `ads/marketplace.py` 20; `ads/marketing.py` 39; `ads/marketing_execution.py` 6; `campaigns/router.py` 41; `campaigns/campaign_video.py` 12; `social/router.py` 28; `video/router.py` 50; `video/channels.py` 7; `video/bulk.py` 11 |
| Publishing / workflow | `publishing/router.py` 39; `publishing/scheduler_router.py` 18; `workflows/router.py` 8 |
| Intelligence orchestration | `intelligence/router.py` 58; `business_agent_router.py` 23; `commerce_journey_router.py` 6; `autonomous_router.py` 33; `operations.py` 2; `simulation_router.py` 3 |
| Product opportunity | `product_opportunity_router.py` 13; `product_opportunity_intelligence_router.py` 16; `product_opportunity_commercial_router.py` 16; `product_opportunity_feasibility_router.py` 5; `product_opportunity_synthesis_router.py` 4; `product_opportunity_scoring_router.py` 9 |
| Supplier / external research | `supplier_router.py` 33; `website_router.py` 32; `external_router.py` 27; `live_supplier_certification_router.py` 16; `indiamart_router.py` 12; `alibaba_router.py` 12; `tradeindia_router.py` 12; `global_sources_router.py` 12; `cross_marketplace_router.py` 17; `supplier_comparison_router.py` 4; `shortlisting_router.py` 18; `due_diligence_router.py` 19; `engagement_router.py` 13; `supplier_response_router.py` 5 |
| Commercial / decision | `sourcing_router.py` 65; `scenario_router.py` 20; `economic_router.py` 43; `economic_integration_router.py` 2; `economic_scenario_router.py` 8; `commercial_reassessment_router.py` 5; `decision_readiness_router.py` 4; `decision_synthesis_router.py` 3; `decision_recommendation_router.py` 6; `procurement_readiness_router.py` 4; `portfolio_router.py` 12; `portfolio_integration_router.py` 8; `resilience_router.py` 5 |
| Demand / competition | `trend_router.py` 44; `review_router.py` 44; `competitor_router.py` 16; `competitor_discovery_router.py` 14; `competitor_commercial_router.py` 17; `competitor_change_router.py` 12 |

## What this inventory does not establish

No fresh persisted seller journey, browser screenshot, API response, migration
upgrade, real provider entitlement, full attack surface or complete accessibility
result follows from file enumeration. See [audit validation](audit-validation.md)
for the actual newly executed checks, blockers and retained historical evidence.
Backend capabilities absent from primary navigation are discoverability candidates,
not automatic permission to expose administrative/external execution controls.
