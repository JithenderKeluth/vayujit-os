# Seller OS journey map — PR-UX-01A

This map describes the seller outcome, the authoritative workspace, and the
current UX boundary. It deliberately distinguishes an implemented experience
from a route that exists only as a future shell. No status below implies that
an external write, supplier contact, purchase, payment, or marketplace write
is enabled.

| Stage | Seller outcome | Current authority / workspace | Status | Next useful action |
| --- | --- | --- | --- | --- |
| 1. Sign in and choose brand | Enter an owner-scoped workspace | `AuthService`, `authGuard`, active brand selector | IMPLEMENTED | Choose the active brand, then open Dashboard |
| 2. Orient on Dashboard | See what needs attention and the current journey | `GET /dashboard`, `GET /journey` | IMPLEMENTED | Follow the highlighted next action |
| 3. State a business goal | Describe budget, market, category, and constraints | Business Agent goal/plan authorities | IMPLEMENTED | Create or resume a research plan |
| 4. Discover product opportunities | Receive evidence-backed candidates | Product research and `ProductOpportunity` authority | IMPLEMENTED / LIVE-DEPENDENT | Review evidence and gaps |
| 5. Select a product | Explicitly choose one product before sourcing | HUMAN selection boundary | IMPLEMENTED | Select the product, then continue to suppliers |
| 6. Discover suppliers | Compare source-backed supplier projections for the selected product | Supplier discovery authority + `CrossMarketplaceSupplierComponent` | IMPLEMENTED / LOCAL-VALIDATED / PROVIDER-DEPENDENT | Inspect a supplier and its sources |
| 7. Verify supplier | Review contradictions, freshness, capabilities, and risk in the selected product context | Supplier verification / due diligence + `SupplierDueDiligenceComponent` | IMPLEMENTED / REVIEW-GATED | Review gaps; do not treat unknowns as verified |
| 8. Shortlist suppliers | Record a deliberate shortlist | Shortlist authority | IMPLEMENTED | Evaluate the shortlist |
| 9. Model sourcing scenarios | Explore assumptions without contacting suppliers | Sourcing economics authority + `/intelligence/sourcing-economics` | IMPLEMENTED / EVIDENCE-DEPENDENT | Review known costs, assumptions, and unknowns |
| 10. Compare commercial evidence | See trade-offs with provenance | Commercial/economics projections + decision brief | IMPLEMENTED / REVIEW-GATED | Review budget fit, capital fit, and comparability |
| 11. Record a decision | Capture a HUMAN hold/approve/reject decision | Decision authority + journey-scoped brief | IMPLEMENTED / HUMAN-GATED | Record a review decision only after resolving blockers |
| 12. Prepare controlled engagement | Create an approved, bounded engagement intent | PR-7A/7B authorities + `/intelligence/supplier-engagement` | IMPLEMENTED / LOCAL-NO-SEND / APPROVAL-GATED | Review the exact draft; no supplier contact occurs automatically |
| 13. Review supplier responses | Append supplier response and quote evidence | PR-7C quote evidence authority + Supplier Engagement workspace | IMPLEMENTED / LOCAL-FIXTURE / INPUT-DEPENDENT | Review immutable response evidence and unknowns |
| 14. Reassess and certify readiness | Preserve the decision trail and certification history | PR-8A–8C and PR-9A authorities | IMPLEMENTED / CERTIFICATION-GATED | Review procurement readiness; do not treat it as purchase authorization |
| 15. Author listing/content | Prepare content for a selected product | Product/content workspace | PARTIAL | Move approved content through review |
| 16. Manage marketplace operations | Operate listings, inventory, orders, and publishing | Marketplace routes and workflow authorities | PARTIAL / CONNECTOR-DEPENDENT | Configure a connector and use HUMAN approval |
| 17. Grow the business | Use campaigns, social, ads, analytics, and calendar | Grow/Manage workspaces | PARTIAL | Complete provider and channel setup |

## Journey rules

- Product and supplier transitions are explicit. A route link never silently
  selects a product or supplier.
- Evidence is shown with an authority, freshness, confidence, and an
  `OBSERVED`, `DERIVED`, or `UNKNOWN` label where the underlying workspace
  provides those fields.
- The next action is a recommendation, not an automatic consequential action.
- Blocked and approval-required stages explain the missing prerequisite and
  link to the owning workspace.
- Live provider unavailability is shown as a provider state; the UI does not
  turn a local fixture into live evidence.

PR-UX-01C adds context-safe supplier discovery and verification presentation.
It is locally validated with an authenticated disposable PostgreSQL fixture at
360, 390, 768, 1024, and 1440 CSS pixels. Commercial decisions, controlled
engagement, and the remaining responsive certification slices remain in the
next UX slices.

PR-UX-01D adds the authenticated sourcing-economics workspace as the canonical
commercial review surface. It preserves goal/product context, shows unknowns
as unknown, and keeps launch preparation disabled until the backend brief is
recommendation-ready. Local fixture evidence is not live market evidence.

PR-UX-01E adds the authenticated supplier-engagement workspace as the
canonical seller-facing handoff for draft preparation, HUMAN review, supplier
response evidence, and procurement-readiness navigation. It reuses the
existing backend authorities and is certified with deterministic local/no-send
fixtures; it does not claim real RFQ delivery or supplier contact.

PR-UX-01A establishes the shell and journey vocabulary for the application.

PR-UX-01F closes the platform stabilization pass for the supported Seller OS
journey. Protected routes share one semantic main landmark, keep the goal /
opportunity / supplier context visible through economics and engagement, and
retain explicit HUMAN and no-send boundaries. Responsive and browser-history
evidence is recorded in [`pr-ux-01f-validation.md`](pr-ux-01f-validation.md);
live-provider certification and full assistive-technology lab coverage remain
outside this local/no-external milestone.
The remaining task-specific flows stay in the next UX backlog.
