# Seller OS component architecture — PR-UX-01A

The frontend is layered so the shell stays small and domain workspaces do not
become one monolithic Angular component.

## Layers

### Shell

- `AppComponent`: authenticated frame, skip link, mobile menu, active brand,
  maintenance banner, breadcrumbs, and router outlet.
- `SellerNavigationComponent`: the single reusable seller navigation contract
  for desktop and mobile, with primary groups and progressive Advanced links.
- `BreadcrumbsComponent`: route context and accessible navigation landmark.

### Shared UX primitives

- `PageHeaderComponent` for consistent eyebrow, title, description, and actions.
- `LoadingStateComponent`, `EmptyStateComponent`, `ErrorStateComponent`, and
  `BlockedStateComponent` for explicit API lifecycle states.
- `StatusBadgeComponent` and `EvidenceCardComponent` for trust vocabulary.
- `BusinessSelectorComponent`, `CommerceJourneyContextComponent`,
  `CommerceJourneySummaryComponent`, `CommerceJourneyNextActionComponent`,
  and `CommerceJourneyStepperComponent` for shared context and progression.

### Domain workspaces

Dashboard, Business Agent, product opportunities, supplier discovery,
shortlisting, due diligence, sourcing economics, decisions, content,
marketplaces, operations, and intelligence remain feature-owned route
components. They consume shared primitives rather than styling or reimplementing
the shell. In PR-UX-01C, `CrossMarketplaceSupplierComponent` owns only route
orchestration and projection of canonical supplier rows/detail, while
`SupplierDueDiligenceComponent` owns only review presentation and calls the
existing due-diligence authority. Neither component infers verification,
calculates risk, or creates a supplier.

### Services and authority boundary

Typed Angular services call the versioned API and expose signals/observables for
loading, success, empty, blocked, and error states. The backend remains the
authority for owner isolation, HUMAN approval, evidence provenance, provider
readiness, idempotency, and consequential action controls. Components render
those decisions; they do not calculate or bypass them.

## Rules for new work

- Prefer a standalone, OnPush component with a focused template and test.
- Keep route components as orchestration shells; move repeated visual patterns
  to `shared/`.
- Never create a second store for goals, products, suppliers, or approvals.
- Never infer evidence or provider readiness in the browser.
- Every async operation must render pending, success, empty, error, and blocked
  states where those states are possible.
- Preserve keyboard order, semantic headings, labels, focus visibility, and
  reduced-motion behavior.
- Keep route-level lazy loading and avoid importing an entire domain into the
  shell.
- Preserve explicit route context (`opportunity_id`, `supplier_id`) and restore
  focus to the selected detail region for keyboard users. Async plain-object
  projections must publish completion to change detection in the zoneless
  runtime.

## PR-UX-01A implementation

This slice centralizes seller navigation and uses the existing shared state,
journey, evidence, and dashboard primitives. It intentionally does not add a
new business store, approval service, API endpoint, or persistence mechanism.
