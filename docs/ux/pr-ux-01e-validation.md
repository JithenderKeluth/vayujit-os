# PR-UX-01E - Controlled Supplier Engagement, RFQs, Responses & Procurement Readiness

## A. Repository audit

The audit covered the Angular route table, seller navigation, Commerce Journey
projection, Business Agent/ProductOpportunity context, supplier discovery and
due-diligence workspaces, sourcing economics, PR-7A/7B/7C engagement and
response authorities, PR-8A/8B/8C commercial-readiness authorities, and PR-9A/
9B authorization boundaries. The implementation reuses those authorities; it
does not create a second supplier, RFQ, response, approval, or procurement
system.

## B. Canonical backend authority mapping

- `engagement_router.py` and `engagement_service.py` own draft creation,
  immutable draft versions, owner/goal/opportunity/supplier scope, HUMAN
  approval, cancellation, history, send eligibility, authorization, and
  idempotency.
- `email_delivery_router.py` and `email_delivery_service.py` own the separate
  PR-7B delivery boundary. The UX does not execute it during certification.
- `supplier_response_router.py` and `supplier_response_service.py` own inbound
  response correlation, extraction, HUMAN review, promotion, raw hashes, and
  provenance.
- `supplier_comparison_router.py`, `commercial_reassessment_router.py`, and
  `procurement_readiness_router.py` own comparison, economics reassessment, and
  readiness projections. The engagement page links to those authorities rather
  than calculating or ranking quotes in Angular.
- `commerce_journey_router.py` and the Business Agent/ProductOpportunity
  authorities supply the selected goal/product and next-action context.

## C. Changed files

Production UX changes:

- `apps/web/src/app/intelligence/supplier-engagement-workspace.component.ts`
- `apps/web/src/app/intelligence/supplier-engagement-workspace.component.spec.ts`
- `apps/web/src/app/app.routes.ts`
- `apps/web/src/app/shared/seller-navigation.component.ts`
- `apps/web/src/app/shared/breadcrumb.service.ts`

Documentation changes:

- `docs/ux/pr-ux-01e-validation.md`
- `docs/ux/seller-os-capability-matrix.md`
- `docs/ux/seller-os-implementation-roadmap.md`
- `docs/ux/seller-os-journey-map.md`

The responsive overflow repair is limited to the new workspace styles:
`min-width: 0` and break-anywhere handling for panels and long response
evidence values.

## D. Engagement workspace

`/intelligence/supplier-engagement` is an authenticated, context-preserving
workspace. It presents the goal, ProductOpportunity, marketplace/category,
supplier, contact, supplier readiness, engagement status, draft, approval,
authorization boundary, responses, history, and procurement-readiness handoff
in one seller-facing flow. Query IDs are inputs to owner-scoped canonical API
projections, not client-side authority.

## E. Supplier readiness

Readiness is rendered from the canonical brief. The persisted fixture showed
`NEEDS_REVIEW`, with deterministic supplier identity and an unverified contact.
The page explains that supplier identity, product relationship, due diligence,
fresh evidence, and verified contact remain prerequisites; no frontend score is
invented.

## F. RFQ preparation

The draft form captures requested quantity, destination, contact, and requested
fields (unit price, MOQ, lead time, incoterm, and payment terms). Submission
calls `POST /api/v1/intelligence/engagements` with a stable idempotency key and
creates an internal immutable draft only. The UI labels the result `DRAFT` and
states that no supplier contact occurs.

## G. RFQ review

The exact subject, structured request, message body, version, provenance,
warnings, unknowns, and limitations are exposed progressively. The review
surface identifies the intended supplier/contact scope and the consequences of
future sending. Draft approval and cancellation are deliberate HUMAN buttons;
there is no disguised navigation or automatic send control.

## H. HUMAN approvals

`POST /engagements/{id}/approve` is used only for the explicit HUMAN draft
approval path and keeps approval separate from execution authorization. The
workspace shows `NOT APPROVED`, `NEEDS_REVIEW`, or the canonical state returned
by the server and preserves decision provenance and history.

## I. Execution authorization boundaries

The authorization panel is a separate state machine. It displays provider
availability, exact-draft requirements, verified-contact requirements,
single-use authorization restrictions, and the deterministic-test/no-provider
blockers. No authorization or send was issued in browser certification. The
page explicitly states that approval is not authorization and authorization is
not proof of delivery.

## J. Engagement status lifecycle

The UI distinguishes draft preparation, `NEEDS_REVIEW`, approved/cancelled
states, `NOT_EXECUTED`, blocked eligibility, authorization, and command outcome
states. It renders canonical blocking reasons and a safe next action instead of
collapsing lifecycle states into a single success indicator.

## K. Supplier responses

The response section lists inbound records by channel, sender, received time,
correlation state, extraction version, review state, promotion state, and safe
next action. The deterministic fixture response is visibly `DETERMINISTIC_TEST`
and `QUOTE`; it is not presented as a live supplier confirmation.

## L. Response evidence and provenance

Raw response content is immutable and progressively disclosed. The page shows
the raw hash, extraction authority/version, correlation reason, trust/evidence
environment, warnings, and unknown fields. Unverified supplier claims remain
untrusted until a HUMAN reviews them. Unknown MOQ, price, lead time, incoterm,
freight, tax, packaging, and payment terms remain unknown rather than zero.

## M. Quote comparison

The workspace does not calculate landed cost, margins, or supplier rankings.
The canonical sourcing-economics route is linked with the same opportunity and
journey IDs for comparison and reassessment. `NOT_COMPARABLE` and missing-data
states remain owned by PR-8 authorities.

## N. Missing commercial information

Missing MOQ, wholesale price, lead time, shipping terms, payment terms,
validity, and packaging information are called out as evidence gaps. The UX
never fabricates a value and never converts `UNKNOWN` to zero.

## O. Procurement readiness

The page provides a clear handoff to canonical sourcing economics and readiness
assessment. It states that readiness is an evidence assessment, not a purchase
authorization. No purchase order, payment, procurement, or marketplace action
is available from this certification flow.

## P. HUMAN decision controls

Draft approval, cancellation, and response review are labelled HUMAN and use
canonical idempotency/provenance contracts. The UI does not impersonate a
seller, approve supplier engagement on behalf of a HUMAN, or infer a decision
from evidence.

## Q. Business Agent integration

The engagement context retains the Business Agent goal text and selected
ProductOpportunity. Business Agent copy can explain readiness and missing
evidence, but no agent action can approve, contact, send, negotiate, purchase,
or pay. The browser showed the exact goal: `I have INR 300000 and want to start
selling on Amazon India. Help me find a product in kids category.`

## R. Commerce Journey integration

The route preserves `opportunity_id`, `journey_id`, `supplier_id`, `contact_id`,
`human_decision_id`, and `engagement_id` through deep links and the canonical
decision brief. The procurement-readiness handoff returns to the same journey
scope; no separate frontend journey authority was introduced.

## S. Loading, blocked, and error states

Loading and API-error states use shared state components. Missing opportunity
context renders an actionable blocked state linking to Product Opportunities.
Missing supplier context links to due diligence and shortlisting. Provider
unavailability, unverified contact, stale/blocked decisions, no response,
unknown fields, and no-send policy are explained with a safe next action.

## T. Responsive validation

Authenticated Chrome CDP checks reported no horizontal overflow after the
response-evidence wrapping fix. The measured document widths were:

| CSS viewport | `scrollWidth` | Result |
| ---: | ---: | --- |
| 360 | 345 | PASS (15px scrollbar allowance) |
| 390 | 375 | PASS (15px scrollbar allowance) |
| 768 | 753 | PASS (15px scrollbar allowance) |
| 1024 | 1009 | PASS (15px scrollbar allowance) |
| 1440 | 1425 | PASS (15px scrollbar allowance) |

At every width the active context, draft review, response evidence,
authorization boundary, and procurement-readiness sections were present.
Captures are retained locally as `tmp/ux-browser/pruxe01e-360.png`,
`pruxe01e-390.png`, `pruxe01e-768.png`, `pruxe01e-1024.png`, and
`pruxe01e-1440.png`.

## U. Accessibility

The component uses one main landmark, semantic heading hierarchy, labelled
forms, `dl` facts, `details/summary` progressive disclosure, status/warning
roles, disabled states, keyboard-operable buttons/links, visible focus from the
shared shell, and non-color-only boundary copy. No irreversible action is
presented without explicit HUMAN wording.

## V. Authenticated browser certification

Normal login succeeded with the disposable owner account
`prux01d@example.com`. The deep link loaded the selected product `Kids
Reusable Lunch Box`, category `Kids`, supplier `PR UX 01E Deterministic
Supplier`, engagement draft version 1, `NEEDS_REVIEW` status, deterministic
response evidence, and blocked send eligibility.

Refresh retained the full query-scoped context. Explicit Chrome history-entry
navigation proved Dashboard -> Supplier Engagement and back/forward restoration.
Logout returned to `/login`; navigating directly to the protected engagement
route while logged out also returned to `/login`.

## W. Owner isolation and security

The route is guarded by the existing `authGuard`; every API request uses the
existing credential interceptor and owner-scoped authorities. PR-7A/7B/7C,
PR-8C, PR-9A, and PR-9B regressions cover foreign-owner access, stale draft or
decision context, HUMAN-only authorization, idempotent replay, single-use
authorization, provider-unavailable behavior, and default-deny network safety.
No external request was made by this certification.

## X. Automated tests and static checks

- Focused engagement workspace: **1 file, 3 tests passed**.
- Full Angular suite: **61 files, 220 tests passed**.
- PR-7A/7B/7C and PR-8C focused regressions: **23 passed** (48 existing
  FastAPI deprecation warnings).
- PR-9A/PR-9B certification regressions: **55 passed** (28 existing FastAPI
  deprecation warnings).
- Angular production build: **PASS**, 507.99 kB initial bundle; existing
  7.99 kB warning above the 500 kB budget.
- Angular ESLint: **0 errors, 2 pre-existing lifecycle warnings**.
- Focused Ruff: **PASS**.
- Focused Black `--check`: **6 files unchanged**.
- Focused strict mypy: **PASS, 6 source files**.
- Python `compileall`: **PASS**.
- Clean disposable migration lifecycle: **1/1 run passed**.
- `git diff --check`: run for the final handoff.

## Y. Golden database, external effects, and remaining limitations

The persisted fixture used only the marked disposable `vayujit_test` database;
`vayujit_golden_test` was not modified. The local fixture and response are
synthetic deterministic evidence, not live supplier evidence. No RFQ, email,
supplier contact, procurement, purchase, payment, or marketplace write was
performed. Real provider delivery and live supplier responses remain outside
this milestone and are still controlled by PR-9A/9B. The unrelated Angular
bundle-budget warning and two lifecycle-interface warnings remain existing
quality debt, not PR-UX-01E failures.

## Z. Final classification

**PR-UX-01E - FULLY VALIDATED (LOCAL / NO EXTERNAL EXECUTION)**

The supported engagement UX, draft review, HUMAN boundaries, deterministic
response evidence, procurement handoff, responsive layout, authentication,
security regressions, and quality gates passed. This classification does not
claim real RFQ delivery or real supplier interaction.
