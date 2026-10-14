# Seller OS information architecture — PR-UX-01A

The information architecture is organized around seller outcomes rather than
backend service names. Existing Angular routes remain the source of truth for
deep links; this document records how they are presented in the shell.

## Primary navigation

| Group | Destination | Purpose |
| --- | --- | --- |
| Home | Dashboard | Operating overview, journey, attention, and quick actions |
| Home | Business Agent | Goal, plan, evidence review, and governed next action |
| Research | Product Opportunities | Product evidence, comparison, and HUMAN selection |
| Research | My Research | Research contexts, historical work, and intelligence |
| Source | Suppliers | Supplier discovery, detail, and source-backed comparison |
| Source | Sourcing decisions | Shortlists, scenarios, economics, and decisions |
| Sell | Products, Listings, Inventory, Orders | Product and marketplace operating surfaces |
| Create | Content, SEO, Images, Videos | Content preparation and media workflows |
| Grow | Campaigns, Social, Advertising | Growth workspaces and channel workflows |
| Manage | Calendar | Planned work and upcoming activity |

## Advanced navigation

Advanced workspaces are progressively disclosed so the primary journey stays
scannable. They include trend intelligence, competitors, reviews, website and
external research, autonomous research, cross-marketplace supplier views,
shortlists, due diligence, economics, operations, workflows, approvals,
execution history, jobs, schedules, recovery, health, integrations, providers,
and settings.

## Context and deep-link rules

1. `AppComponent` owns the authenticated shell, skip link, active brand
   presentation, maintenance notice, mobile menu, and breadcrumbs.
2. `SellerNavigationComponent` presents links only. Guards and route resolvers
   decide access; navigation never duplicates authorization.
3. Lazy-loaded route boundaries keep domain workspaces isolated. A refresh or a
   deep link must reconstruct context from the canonical API/state service;
   the shell does not persist business truth in local storage.
4. Goal, product, supplier, shortlist, and scenario identifiers stay visible
   in the owning workspace. A missing context produces an actionable empty or
   blocked state rather than a misleading default.
5. Active links expose `aria-current="page"`; keyboard focus is visible; the
   Advanced group is a native disclosure element.
6. Supplier discovery accepts optional owner-scoped `opportunity_id` and
   `supplier_id` query context. The page resolves both through the canonical
   API projection; a URL ID is never treated as proof of ownership or product
   membership.
7. Due diligence accepts the same context and renders an explicit selected
   product panel. Review and waiver requests use the authenticated canonical
   authority and remain HUMAN-controlled.

## PR-UX-01C context boundary

Supplier discovery accepts optional owner-scoped `opportunity_id` and
`supplier_id` query context. Due diligence accepts the same context and shows
an explicit selected-product panel. Both routes resolve IDs through canonical
API projections; a URL ID is never proof of ownership or product membership.
Review and waiver remain HUMAN-controlled. Supplier contact, RFQs, purchasing,
payments, and marketplace mutations are not navigation outcomes of this slice.

## Context hierarchy

```text
Owner
└── Active brand
    ├── Dashboard / journey
    ├── Business goal
    │   └── Research plan and product opportunities
    │       └── HUMAN-selected product
    │           └── Suppliers and evidence
    │               └── Shortlist → economics → decision
    └── Sell / Create / Grow / Manage workspaces
```

PR-UX-01B–F may refine terminology and task-level information architecture,
but must preserve these owner, brand, and evidence boundaries.
