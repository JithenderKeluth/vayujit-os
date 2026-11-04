# Proposed connected Seller OS experience

Design proposal only, 2026-10-27. This is not an implementation, new authorization,
approved backlog, or certification. Current runtime gaps remain **UNVERIFIED**
unless the enclosing audit records an actual test. The one-owner installation
and `ck_users_single_owner` remain unchanged.

## Experience principles grounded in the current implementation

Reuse `CommerceJourney`, `ProductOpportunity`, HUMAN selection, canonical Supplier,
source/evidence and assessment records, commercial input/snapshot authorities,
Product/Catalog lineage, listing drafts, stock movements, orders/financial events,
and operational signals. Do not create a second “seller workflow” database.

The current eight-stage Commerce Journey guides research/sourcing/commercial
review; it is not evidence that inventory, orders and finance form a single
transaction. Offer connected tasks, not a mandatory linear wizard. An existing
seller may start with an owned Product and counted stock without conducting new
product discovery. A researching seller must not be allowed to skip HUMAN selection
by opening a supplier URL.

For every screen, show: **what this is**, **current product/supplier context**,
**what is known/unknown/stale**, **why blocked**, **one useful next action**, and
**how to return without losing persisted work**. A recommendation is not approval;
an approval is not execution; local preparation is not marketplace publication.

## Navigation proposal: regroup existing routes, preserve deep links

| Task area | Existing routes and recommended presentation |
| --- | --- |
| Home | Dashboard, Action Center, Launch readiness. Business Agent remains a prominent task entry rather than replacing operational records. |
| Find and evaluate products | Business goals/runs → Product Opportunities. My Research remains a clearly marked detailed evidence/history workspace. |
| Suppliers and commercial review | Existing `/intelligence/cross-marketplace` as primary Suppliers; contextual Compare, Shortlist, Verify, Economics and Engagement. Existing `/intelligence/sourcing` becomes requirement/quote/scenario work, not the destination called Suppliers. |
| Products | One clearly explained product workspace connecting existing Product facts, Catalog images/variants, drafts, readiness, economics and stock links; preserve both route families and identifiers. |
| Marketplaces and operations | Visible Marketplace setup/overview; Listings, Inventory, Orders and Financials. Account registration/API entitlement remain separate, external prerequisites. |
| Create and grow | Existing content, images/video, campaigns/social/advertising/calendar. Show local/provider-unavailable capabilities accurately; do not make them prerequisites for catalog/stock work. |
| System and advanced research | Existing settings, provider/source tools, approvals, execution history, workflows, health/recovery. Label publishing connectors separately from marketplace accounts. |

Use the existing `SellerNavigationComponent`, shared page headers, state/evidence
primitives and `SupplierJourneyNavComponent`; do not replace route guards with
sidebar checks. Detail-level contextual tabs should retain scoped IDs and a
**Back to results** path with filter state. Do not place 155 destinations directly
in the primary sidebar.

## Module contracts

These specify the proposed seller experience using supported artifacts. “Current
authority” is a reuse direction, not a claim that every stated UI link already
exists. Workflow gaps must be approved separately before implementation.

### 1. Owner onboarding and business context

- **Purpose / entry:** setup/login → Dashboard; existing AuthService/guards and
  owned Brand configuration. One seller, one installation, no second owner.
- **Inputs / prerequisites:** genuine owner and business/brand information;
  authenticated session after setup. Do not seed synthetic production records.
- **Outputs / states:** canonical owner/brand and active brand; needs setup →
  authenticated → brand selected; expired/maintenance/error remain distinct.
- **Next / back:** choose a task, start/resume a goal or create an existing Product;
  back to Dashboard; logout protects all resources. Do not force discovery first.
- **Empty / errors:** explain absent brand versus failed lookup; retry must leave
  the spinner and preserve entered non-secret data. Do not hide auth denial as empty.
- **Provenance / HUMAN:** owner supplies genuine facts; UNKNOWN remains unknown.
  Account creation is not consent to research acquisition, publishing or payment.

### 2. Dashboard and next action

- **Purpose / entry:** `/dashboard`; answer what needs attention, why, what is
  blocked, and how to resume an unfinished scoped task.
- **Inputs / prerequisites:** current authenticated Dashboard and Commerce Journey
  projections, operational signals, genuine readiness/configuration status where
  those authorities already supply it; do not infer readiness from record counts.
- **Outputs / states:** links to owning workspaces, not new business actions;
  loading → empty/ready/partial/error; distinguish journey unavailable from no journey.
- **Next / back:** primary action from canonical `next_action`; additional
  alternative entry for existing-product owners; return from any task to Dashboard.
- **Error / empty:** actionable retry and known scope; never show “nothing needs
  attention” while a required source has failed.
- **Provenance / HUMAN:** display source/freshness/trust; fixture and local-only
  labels persist. Publishing destinations are not connected marketplace accounts.
  Advisory cards never authorize external actions.

### 3. Business goals, plans and research runs

- **Purpose / entry:** existing `/intelligence/business-agent`; seller describes
  market, budget, category and constraints; resume the actual persisted run.
- **Inputs / prerequisites:** owner-entered goal, supported parser constraints,
  canonical context confirmation and existing plan/run policies.
- **Outputs / states:** goal → plan → running/awaiting source review/blocked/
  partial/completed/cancelled; fetched evidence and discovery outcomes, not promised
  products or fabricated “top sellers.”
- **Next / back:** one current CTA: review context, create plan, start, approve an
  eligible source, continue/retry a supported failed step, or review candidates.
  Keep run details and safe cancel/retry history, with return to goal list.
- **Error / empty:** separate no useful candidates, source approval, unavailable
  provider, quota/rate limit and failed approved fetch; explain the owning action.
  Search requests, fetched pages and canonical products are separate counters.
- **Provenance / HUMAN:** current source-review component already records audit
  purpose and optional note; retain explicit policy/terms/access attestations.
  Approval is not product verification. No silent policy approvals or provider calls.

### 4. Product opportunities, comparison and selection

- **Purpose / entry:** `/intelligence/product-opportunities` and exact owned detail;
  assess actual evidence for the current seller goal before supplier discovery.
- **Inputs / prerequisites:** goal/category/market scope, canonical candidate,
  source identity and current assessment where required by selection authority.
- **Outputs / states:** researched candidate with gaps/current/stale/rejected/
  archived status; explicit HUMAN selection, never implicit selection from viewing.
- **Next / back:** research missing evidence, compare eligible candidates, select
  one for suppliers, or use the existing catalog conversion authority when eligible.
  Detail → filtered results; preserve original goal rather than substituting active goal.
- **Error / empty:** no candidates is a legitimate outcome; show latest bounded
  research outcomes and safe retry, not unrelated historical fallback. Disabled
  selection explains the missing assessment beside the action.
- **Provenance / HUMAN:** citations, fetched time, confidence, claims/contradictions
  and missing commercial values retained; synthetic/cached evidence cannot override
  category eligibility. HUMAN selection/replay/stale-context rules remain backend-owned.

### 5. Supplier discovery, evidence and comparison

- **Purpose / entry:** existing `/intelligence/cross-marketplace` from selected
  Opportunity; selected product context is visible before search/results.
- **Inputs / prerequisites:** canonical HUMAN-selected Opportunity, category/market,
  bounded approved read policy; existing supplier correlation/relevance authorities.
- **Outputs / states:** canonical supplier candidates/sources/evidence, zero/one/
  many candidates, partial/no useful evidence/provider blocked; comparison is a
  trade-off projection, not automatic ranking or supplier selection.
- **Next / back:** inspect exact supplier → explicit shortlist → DD/commercial
  evidence; back to original Opportunity or filtered suppliers. Preserve opportunity
  and supplier in links, refresh, new tab and browser history.
- **Error / empty:** describe zero-result versus failed research, clarify approved
  read does not guarantee a relevant supplier; do not fabricate another supplier.
- **Provenance / HUMAN:** original URL/hash, trust/freshness, identity confidence,
  verification, contradictory claims and UNKNOWN MOQ/price/lead time remain visible.
  Source approval and single-use live-execution authorization stay separate.

### 6. Shortlist and due diligence

- **Purpose / entry:** existing shortlist and `/intelligence/due-diligence`, scoped
  from a supplier; explain evidence review, not supplier certification by appearance.
- **Inputs / prerequisites:** exact canonical supplier/opportunity, comparison or
  shortlist context and supported assessment/finding versions.
- **Outputs / states:** explicit HUMAN shortlist, findings and reviews; not started →
  needs evidence/review/current/stale/blocked; do not invent a blanket verified status.
- **Next / back:** inspect contradictory/absent evidence; supported review/waiver
  only; continue to commercial evidence; return to exact supplier and comparison.
- **Error / empty:** no DD context links to canonical context creation, not a UUID
  prompt as the sole path; explain stale review rejection and refresh safely.
- **Provenance / HUMAN:** source claims never become independent verification;
  preserve confidence, observed freshness, reviewer and rationale. Waivers do not
  manufacture commercial facts or authorize procurement.

### 7. Commercial evidence, economics and business decisions

- **Purpose / entry:** existing `/intelligence/sourcing-economics` from exact
  Opportunity/supplier assessment; `/intelligence/sourcing` retains supported
  requirements/quotes/scenarios. Clearly explain the distinction.
- **Inputs / prerequisites:** canonical acquisition assumptions, observed/claimed
  costs, quote evidence and supplier context; explicit existing immutable FX/freight/
  tax references where applicable. No new fee schedule or GST formula is designed here.
- **Outputs / states:** readiness → immutable input snapshot → landed/unit economics →
  evidence-backed assessment/decision; READY, UNKNOWN, NEEDS_EVIDENCE, STALE,
  NOT_COMPARABLE and blocked are not conflated. Material input change requires recalculation.
- **Next / back:** a compact top summary: input freshness, known cost, excluded
  unknowns, budget/capital fit, main risk, next legitimate action. Accessible jump
  links to evidence, assumptions, calculations and HUMAN decision; details retained.
  Back to exact supplier/opportunity/assessment; preserve historical snapshot identity.
- **Error / empty:** explain missing group and owning input form, rejection of
  stale/replayed-conflicting actions and safe same-intent retry. No zero substitution.
- **Provenance / HUMAN:** show calculation/input versions and known/claim/assumption
  distinctions; explicit HUMAN hold/reject/approve via existing decision authority.
  Decision readiness is not purchasing permission or proven future profitability.

### 8. Controlled engagement and responses

- **Purpose / entry:** existing supplier engagement from the reviewed commercial
  context; prepare local drafts and record legitimate response evidence.
- **Inputs / prerequisites:** exact supplier, approved context/version and supported
  contact/consent evidence where required by existing authorities.
- **Outputs / states:** local draft → review → separately authorized dispatch only
  when legitimately enabled; response/quote evidence → reassessment. In this audit,
  actual sends, supplier contact and external writes remain prohibited.
- **Next / back:** inspect exact draft/recipient and readiness; input supported
  response provenance → return to economics; safe cancel/revoke; return to supplier.
- **Error / empty:** absent contacts/quotes remain UNKNOWN; local-no-send is not
  “email sent”; show expired/revoked/stale/disabled controls truthfully.
- **Provenance / HUMAN:** immutable response/source/quote lineage, attachments and
  reviewer identity; no invented prices/MOQ/lead times and no auto-approval.

### 9. Product master, catalog, images and listing preparation

- **Purpose / entry:** existing owned Product/Catalog routes; create genuine manual
  product or convert an eligible HUMAN-selected Opportunity using the supported API.
- **Inputs / prerequisites:** owned brand, factual name/category/SKU/variants,
  explicitly confirmed currency and prices/costs where known; private ready media.
- **Outputs / states:** Product plus preserved origin, variants/images and local
  channel-specific drafts; incomplete → validated/review needed/approved/stale;
  Product active does not mean published or commercially ready.
- **Next / back:** edit Product facts, attach private media, resolve readiness
  blockers, review draft, go to exact supported marketplace workspace. Show stock
  and economics as linked authorities, not product-form substitutes. Back to
  filtered products or originating Opportunity; cancellation must not lose origin.
- **Error / empty:** required fields identified with labels and focusable errors;
  failed/stale save is recoverable. Do not label all non-BLOCKED states “ready to
  submit” unless canonical contract makes that meaning true.
- **Provenance / HUMAN:** preserve opportunity lineage and authored-versus-source
  claims. Draft approval is explicit and versioned; changing material content
  invalidates prior review as required. No synthetic-to-production promotion.

### 10. Inventory and opening stock

- **Purpose / entry:** existing Inventory → Add opening stock; independent from
  Product metadata Quantity. Count physical units the seller actually owns.
- **Inputs / prerequisites:** canonical product/variant/SKU, location/unit, counted
  quantity, supported cost-evidence status; owner count confirmation and version.
- **Outputs / states:** immutable opening intent/movement/audit → current stock,
  reservations/damaged/available quantities; empty, initialized, stale/conflict.
- **Next / back:** inspect ledger, adjust legitimate receipts/corrections, map SKU
  to actual configured channel; return to Product or inventory filters.
- **Error / empty:** unknown acquisition cost is not zero; duplicate opening stock,
  invalid quantity and stale adjustment must explain recovery without double count.
- **Provenance / HUMAN:** manual count versus imported/reserved evidence visible;
  explicit counted-stock review. No stock publication, fabricated orders or forced
  listing prerequisite for counting owned inventory.

### 11. Marketplace setup, listings and orders

- **Purpose / entry:** existing Marketplace overview/accounts/channel workspaces,
  linked from products and operations; separate setup from ongoing orders.
- **Inputs / prerequisites:** actual seller registration, identity/tax/category
  eligibility, distinct API entitlement/credentials, verified official contract,
  separately approved read certification. Missing external prerequisites block live use.
- **Outputs / states:** local catalog mapping/draft/readiness/review/authorization;
  read-only orders and their canonical event/timeline. UNCONFIGURED, LOCAL/FAKE,
  EXTERNALLY_PENDING and genuine authorized states must be visibly distinct.
- **Next / back:** actual missing setup checklist or exact channel draft; orders →
  mapped Product, stock movement and financial evidence. Back to originating draft,
  account or filtered order list with seller/listing identity retained.
- **Error / empty:** distinguish no orders from unavailable import. Unsupported
  cancellation/fulfillment is explicitly unsupported, not a fake success. Existing
  generic listing-create fake active connector is not the local draft mechanism.
- **Provenance / HUMAN:** provider, account scope, import freshness and synthetic
  ancestry remain visible. All applicable exact version/fingerprint, expiry,
  revocation/replay, emergency-stop and worker gates remain canonical; no external
  execution is authorized by this design.

### 12. Financial operations and business improvement

- **Purpose / entry:** existing Financials, settlements and Business Agent advice;
  reconcile evidence, not promise profit from partial data.
- **Inputs / prerequisites:** canonical observed order/fee/refund/settlement and
  cost evidence, SKU mapping, currency and known provenance; preserve Decimal rules.
- **Outputs / states:** current qualified/partial projections, UNKNOWN profitability,
  discrepancies and evidence-linked recommendations. Exact immutable operational
  historical reconstruction is an existing gap, not a feature promised by these views.
- **Next / back:** add legitimate missing evidence through its authority, inspect
  source event/cost/settlement and refresh current projection; return to order or
  filtered finance view. Proposed accounting-history work requires separate approval.
- **Error / empty:** unknown fees/GST/refunds are not zero; no fake “import real
  finance” shortcut; failed projection distinct from no evidence.
- **Provenance / HUMAN:** synthetic/mixed/unknown retained across fallback and
  reload; source IDs/freshness and calculation basis visible. Advice remains advisory;
  no payouts, refunds, financial transactions or autonomous business decisions.

### 13. Action Center, approvals and system recovery

- **Purpose / entry:** actionable signals/briefing; owning source links; existing
  artifact/commercial/channel authorities remain the actual approval workspaces.
- **Inputs / prerequisites:** canonical signals with owner/scope/current evidence,
  supported filter/status/history; protected system settings and maintenance status.
- **Outputs / states:** acknowledge/snooze/resolve/reopen/stale is local signal
  lifecycle, not source correction or approval/execution. Generic durable execution
  remains unsupported; never manufacture it inside a generic button.
- **Next / back:** inspect why/source/freshness → correct in owning module → refresh;
  preserve filter/page on return. Explicitly warn that Resolve does not fix source.
- **Error / empty:** operation-specific failure and retry, finite loading, last
  successful scan time; empty results not shown during source failure. System
  recovery is not a generic browser retry or a synthetic backup certificate.
- **Provenance / HUMAN:** actor/audit and source retained; maintenance/default-deny
  controls never hidden. PC-first backup/independent restore remains separately
  parked and unresolved; this design does not run or change it.

### 14. Content, campaigns, social and advertising

- **Purpose / entry:** existing Create/Grow routes when a seller needs product
  content or marketing; optional for initial catalog/counting work.
- **Inputs / prerequisites:** exact product/brand/campaign/activity and provider
  capability; supported local artifact review and destination settings.
- **Outputs / states:** drafts/generated artifacts/reviews/plans; unavailable
  provider, unknown outcome and local preview separate from published delivery.
- **Next / back:** safe edit/review/compare/export/local planning; link to owning
  Product or campaign. Preserve exact artifact/activity IDs across deep links.
- **Error / empty:** provider/capability-specific recovery, no fake generated
  success; fix bounded overflow/accessibility issues before claiming responsive PASS.
- **Provenance / HUMAN:** authored/generated/source claims distinguished; existing
  approval/version/execution gates retained. No live social/ad/provider action here.

## Minimum coherent seller experience before an application-complete claim

1. Choose either research-led or existing-product entry; know its prerequisites.
2. Research results obey the actual goal/category and never force a product result.
3. Exact HUMAN selection → canonical supplier → scoped DD/commercial review has no
   context substitution, hidden technical-ID requirement or misleading success.
4. Eligible selected product → existing conversion → Catalog retains lineage;
   manual creation remains a legitimate independent path.
5. Genuine private images, variants, INR/currency confirmation and local drafts
   have useful errors, review, stale rejection and browser-history recovery.
6. Counted opening stock and Product Quantity cannot be mistaken for each other.
7. Financial projections explain known/unknown/synthetic/stale and current-only
   history limits; owner approves intended initial financial scope separately.
8. Marketplace registration and API authorization are truthful external blockers;
   local readiness is never called actual connectivity/publication.
9. Keyboard/assistive/mobile review covers the required task states, not only
   headings or route visits; original unresolved findings retain history.
10. Separate operational security/backup/restore and explicit HUMAN activation
    gates must pass before real operation, regardless of UI improvement.

## Required evidence before implementing this design

Approve a bounded backlog, then use existing disposable fixtures to test two
goals/products/suppliers, same-route switching, interruption/replay, missing and
stale inputs, no-useful-result states, owner/auth denial, keyboard/axe and all
five existing viewport widths. Preserve original assertions and immutable evidence.
Do not calculate “completion percentage” from route count, hide failed APIs as
empty data, or silently accept owner risk. No implementation is authorized by
this document; stop for review as requested by the enclosing audit specification.
