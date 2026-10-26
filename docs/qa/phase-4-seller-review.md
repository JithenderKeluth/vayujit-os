# Phase 4 — first-seller task and completeness review

Expert usability review grounded in source, actual captured DOM and explicit
synthetic task assertions; **not a human participant study**. A route visit alone
does not demonstrate a completed seller journey. All figures/evidence are synthetic
or explicitly unknown; no verified live acquisition is established.

| Journey | Start, next step and required inputs | Trust, preservation and correction | Completion/support verdict |
| --- | --- | --- | --- |
| 1. Initial setup/onboarding | Fresh Phase 1 installation offers owner setup; required identity/password validation is exercised. Existing owner follows login to Dashboard. | Setup persists one owner; duplicate owner denied. Tab/Shift+Tab and validation exercised; Phase 4 logout/protected-route/history assertions pass. | **Supported bounded local owner flow verified**; not complete expiry/lockout/recovery certification. |
| 2. Product discovery/selection | Business Agent and Product Opportunities are discoverable. Goal/plan and selected fixture contexts exist; no live research run is executed. Pre-run mode/confirmation wording remains an open clarity concern. | Category/seller constraints remain canonical; only normal fixture-selected ProductOpportunity is reused. Query/source acquisition and all real-provider claims are untested. | **Partial**. Goal-to-plan persistence and existing selection authorities are regression evidence; do not infer live discovery or new UI selection success. |
| 3. Supplier evaluation/DD | Supplier and DD routes exist; exact opportunity/supplier query context opens persisted findings. Required missing evidence and unknown commercial values are visible, not filled in. | Existing synthetic supplier evidence, scope and canonical DD are reused. No supplier changes/contact or new shortlist execution. Captions clip on mobile. | **Partial**; source/evidence inspection supported, full live supplier journey untested. |
| 4. Economics/profitability | Economics exposes modeled components, assumptions and decision state. Long pages make the next decision difficult to find; summary/jump-link proposal remains open. | Phase 2 deterministic oracles, stale assumptions, HUMAN decision/replay/reload pass. Estimates/UNKNOWN are not verified margins; no live GST/fee schedule is invented. | **Partial accounting scope**; supported synthetic commercial subflow verified, not a real business profitability certification. |
| 5. Catalog | Catalog/Products and create/edit actions are discoverable. Existing brand prerequisite is explicit; Phase 1 enters INR rather than accepting the USD default. | Phase 4 cancel leaves Product unchanged, one save persists/reloads; Phase 1 create/edit passes. Price/cost remain separate; no publication. Asset/variant conditional editors are not fully exercised. | **Supported basic create/edit subflow**, incomplete full catalog state/asset/dialog coverage. |
| 6. Initial inventory entry | **Phase 4B:** Inventory → Add opening stock → owned physical Product/variant → explicit count → review → HUMAN confirmation. Product master quantity remains a different authority. | Existing canonical API persists one item, HUMAN opening movement and audit; replay/concurrency, UNKNOWN cost, zero count, lost response, reload and scope denial have dedicated tests. | Implemented bounded local workflow; current evidence and closure are in [Phase 4B validation](phase-4b-validation.md). No marketplace synchronization or complete inventory-management certification implied. |
| 7. Inventory updates | Existing item provides Adjust stock, ledger and SKU mapping. Delta/reason/version are canonical inputs; mapping requires an existing account/SKU, not a live provider call. | Phase 4B preserves adjustment authorities and corrects filtered-empty wording. Existing Phase 4 tests still exercise mapping cancel and API error/retry. | **Partial**: canonical opening and existing update subflows tested; no remote sync or full edit-dialog matrix. |
| 8. Order handling | Orders page exposes persisted read-only order/timeline information; fake-provider ingestion is not a seller-facing manual order-entry authority. | Existing API lifecycle/reservations/concurrency pass. No refund dispatch, real fulfillment, order acquisition or supplier action performed. | **Partial/intentionally read-only UI**. Do not call absent external execution a successful seller operation. |
| 9. Financial reconciliation | Financials and settlement tables expose sales, missing costs and reported reconciliation. Four exact historical headers are keyboard-exposed and readable after scrolling. | Independent synthetic decimal/reconciliation assertions pass. UNKNOWN stays UNKNOWN; explicit synthetic provenance survives fallback. Filters/reload and modeled-versus-real distinction remain bounded to tested states. | **Partial**. Real bank/marketplace settlement and complete net-profit accounting unsupported by this evidence; other captions still need review. |
| 10. Business Agent recommendations | Dashboard/Business Agent are discoverable. Distinct goal confirmation, plan and run states need clearer guidance; existing pre-run proposal is retained. | Canonical financial-agent API says advisory/read-only and preserves loss/unknown evidence. No Start run/live-provider or automatic business action executed. | **Partial**. Recommendations are not authorizations or evidence of completed external actions. |
| 11. Action Center HUMAN decisions | Filters/cards/inspect links and canonical acknowledge/snooze/resolve/reopen exist. Banner explains controlled advisory scope. | Existing API transitions/replay/HUMAN impersonation denial pass. Generic approval/reject/execution is not a durable supported authority here; do not duplicate commercial HUMAN workflow. | **Local signal lifecycle supported; broader business-action workflow missing/conditionally deferrable**. |
| 12. Settings/status/recovery | Settings/Operations routes, forms and status controls are inventoried. Missing credentials/providers remain unavailable; no owner secrets are entered. | Normal login/logout and safely injected HTTP retry are exercised. Read-only status visits do not certify provider health, backups, worker restart, restore or production readiness. | **Partial/read-only assessment**. PC-first backup workstream remains untouched; those operational actions are blocked/out of scope. |

## Cross-cutting observations

- The known currency default and economics hierarchy recommendations are not
  silently closed. Current evidence supports retaining both.
- Page-current navigation fixed by Phase 3B remains intact; a broader source visit
  does not undo its prior resolution.
- Additional long research screens and desktop overflow are **recommendations**,
  not automatically data-loss or calculation bugs. Practical complexity is in the
  backlog. No broad redesign is performed.
- Initial setup, Product create/edit and cancel/reload have clear persisted success
  in executed bounded subflows. Many other features have only discovery evidence.
- Unknown commercial data, synthetic context and governed actions must remain
  distinct. No test converts synthetic fixture state into production business data.
- The UI double-click save race, variant/media dialogs, screen readers and the 26
  missing canonical artifact contexts remain explicit coverage gaps.

Use [actual journey coverage](phase-4-journeys.json), [surface captures](phase-4-surface-inventory.json)
and [validation](phase-4-validation.md) to distinguish assertions from review.
