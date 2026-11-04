# WP5 — Daily seller operations remediation

Date: 2026-10-30. **WP5 IMPLEMENTED / BOUNDED LOCAL DAILY-OPERATIONS VALIDATED**.
Application certification remains **INCOMPLETE**. Financial-history and order-price
precision limitations remain; no live marketplace capability is certified. Stop
after WP5, before WP6. PC-first backup certification remains parked.

See [browser/test evidence and commands](wp5-browser-retest.md) and
[structured resolution](wp5-resolution.json). Prior WP1–WP4 reports, original
exploration evidence and unsuccessful retests are preserved.

## Scope and original finding disposition

The four remaining original findings were 009 (mobile Video overflow), 012 (mobile
menu remains open after navigation), 017 (creative-tool active-product prerequisites)
and 020 (login loses protected return route). **012 belongs to this operational
navigation package and is resolved locally. 009/017/020 remain open.** Suspected
global Advanced-link contrast and historical QA findings are not silently closed.

Before-change run `69d80dd4ed546298` used actual production Angular, authenticated
Chrome desktop/mobile and installed Edge on an approved disposable installation.
It captured empty/new seller, research without inventory, configured mock destination,
synthetic orders, missing costs, multiple signals, failed scan and failed Finance
filter states. First attempt `f02d10a22e99fe10` stopped at an investigator's overly
strict filter locator; its partial evidence is not a completed baseline.

## Confirmed roots and bounded corrections

| ID | Root cause | Correction / demonstrated result |
| --- | --- | --- |
| SE-WP5-DASH-001 | Dashboard called active `PublishingDestination` count “sales channels connected”, although no marketplace account existed. It primarily summarized publishing/journey activity, not daily seller records. | Correct configuration wording; reuse canonical account, inventory, order, financial-summary and operational-briefing reads for an explicitly installation-wide daily-status panel. Record counts, synthetic orders and unavailable reads are distinguished; no account configuration is promoted to verified connectivity. |
| SE-WP5-READ-001 | Brand initialization could reject outside Dashboard/App handling; asynchronous reads could display older filter responses. | Catch brand restoration failures, clear prior usable data during new reads, and retain only latest request results. Partial daily reads become UNKNOWN/unavailable, not zero or healthy. Existing API authorization remains authoritative. |
| SE-WP5-ACTION-001 | Scan, inspect, transitions and policy handlers awaited rejected promises without usable feedback; repeated pending actions were not blocked; inspect used the stale tile instead of returned detail. | Safe visible failure, no false saved notice, busy guards, authoritative detail refresh and late-read protection. Acknowledge/resolve remain local notice actions, not repair or generic execution. Explain observed/fresh-until evidence and advisory boundaries. |
| SE-WP5-STALE-001 | A full scan upserted present conditions but did not retire absent financial/order/listing conditions. An old negative-contribution warning could survive a legitimate revised working snapshot. | At successful scan completion, only known derived rules owned by this scanner and not re-observed become STALE. Old evidence/history is retained. Automatic recurrence and retirement use the existing SYSTEM derived-transition writer, not fabricated HUMAN approval. Stock-specific source revalidation remains intact. |
| SE-WP5-ORDER-001 | Order details exposed a line count but no lines or owned product handoff; selection was not URL-restorable. | Extend the existing owner-scoped order read with safe line projections, product IDs and nullable recorded currency; add Catalog/inventory links and exact `order_id` deep link/reload, with stale-response/invalid-ID protection. Read failure is not an empty history. No lifecycle execution UI added. |
| SE-WP5-PROVENANCE-001 | Unified order response unconditionally set `fake_provider=True`; missing/declared source ancestry was not represented. | Reuse the existing financial source classifier for orders. Positive synthetic ancestry dominates contradictory declarations; absent ancestry is UNKNOWN; reported is not independently verified real. Shared classifier now checks source declarations across persisted metadata, not only the first dictionary. Five persisted classifications/reload tested. |
| SE-WP5-FINANCE-001 | A failed new filter left old figures displayed beneath the new filter; older responses could overwrite newer scope. “Fully qualified estimate” overstated contribution, and history semantics were unclear. | Clear all financial read models on scope change/error, latest-request guard, persistent marketplace/date URL scope, invalid-period rejection, exact-string INR presentation and source navigation. Missing sales render UNKNOWN, not a meaningful zero. Label current projections, UTC reporting basis, retrieval versus source freshness, contribution versus net profit and mutable working snapshots. |
| SE-WP5-AGENT-001 | Business Agent unconditionally probed latest plan/run as failing resources even when an owned goal legitimately had none. Final clean-console gate caught its 404 after navigation. | Existing endpoints gain explicit `allow_missing=true` nullable reads after owned-goal validation. Default 404 behavior and unknown/unauthorized-goal rejection remain. Hydration uses this empty-state contract, not invented runs or suppressed console failures. Add daily-work links to existing Action Center, Orders and Finance, with no claim of execution. |
| SE-BROWSER-012 | Mobile details menu only closed on Escape, not successful destination navigation. | Close on `NavigationEnd`, focus existing main content, unsubscribe with component lifetime. Actual Chrome mobile keyboard navigation/reload verified. |

Scoped Action Center source URLs are parsed as Angular URL trees so `?product_id=`
and `?order_id=` are preserved, not encoded into a path. External/protocol-relative,
backslash and control-character routes are not accepted as source links.

No financial formula, marketplace fee schedule, GST treatment, approval threshold,
database ownership architecture or external execution authority was introduced.
Single-owner `ck_users_single_owner` remains. No migration or dependency installation.

## Financial-history and price-precision disposition

The existing FinancialCalculationSnapshot is **mutable for the same scope and
calculation version**. Recalculation overwrites its metrics/lineage; it is not an
immutable accounting journal. Persisted regression proves same ID, revised amounts
and one working row. The UI now explicitly states this limit. Historical accounting
gap QA-P3-GAP-001 remains open; no new ledger architecture or fabricated accounting
history was created. Financial source freshness is not established by retrieval time.

Browser/API checks independently used synthetic sale INR 200.25, fees INR 20.05,
unknown costs → UNKNOWN contribution. Explicit synthetic cost INR 300 produced
contribution **-119.80**, an additional fee INR 1 produced **-120.80**, and an
additional legitimate synthetic sale INR 500 produced **379.20**. These are existing
server model outputs, not verified net profit, real fees, GST or real revenue.

**SE-WP5-PRICE-001 — MEDIUM/P2, underlying precision policy OPEN; display mitigated.**
The fake-order endpoint accepts a source unit price 100.125 and computes a two-unit
line from it, while `MarketplaceOrderItem.unit_price` stores Numeric(12,2). Browser
evidence showed stored unit **100.13** and recorded line total **200.25**. The UI now
explicitly calls the unit amount a rounded stored projection and warns not to
reconstruct totals from it. Recorded amounts and canonical arithmetic are unchanged.
This is not certification of sub-paise order accounting. A separate reviewed precision/
source-correlation contract is needed before changing input precision, storage or
historical amounts. Original event evidence must not be silently rewritten.

Catalog estimates are not automatically imported as recorded financial costs. Full
seller-facing financial cost correction/immutable accounting workflows were not
invented. Agent guidance on Finance is labelled installation-wide, separate from the
selected reporting filter; its links do not execute corrections or payouts.

## Changed files and architecture

Production backend:

- `apps/api/vayujit_api/commerce/orders_router.py` — owner-scoped detail/provenance.
- `apps/api/vayujit_api/commerce/schemas.py` — additive line/currency/provenance DTO fields.
- `apps/api/vayujit_api/commerce/financial_router.py` — existing provenance metadata lookup.
- `apps/api/vayujit_api/operations/action_center_router.py` — exact source routes and completed-scan negative reconciliation/SYSTEM audit.
- `apps/api/vayujit_api/intelligence/business_agent_router.py` — optional owned empty reads.

Production Angular under `apps/web/src/app/`:

- `operations/dashboard.component.ts`, `operations/operations.service.ts`.
- `operations/action-center.component.ts`.
- `marketplaces/unified-orders.component.ts`, `marketplaces/marketplace.service.ts`.
- `marketplaces/financial-workspace.component.ts`.
- `intelligence/business-agent-workspace.component.ts`, `intelligence/business-agent.service.ts`.
- `app.component.ts` — navigation completion and safe context restoration.

Regressions/harness:

- New `apps/api/tests/test_seller_wp5.py` — 11 persisted cases.
- New `apps/web/src/app/operations/seller-wp5.spec.ts`; updated Dashboard and Business Agent workspace specs.
- New `qa/wp5-fixtures.mjs`, `qa/wp5-before.mjs`, `qa/wp5-browser-retest.mjs`, `qa/wp5_final_audit.py`, `qa/unit/wp5-safety.test.mjs`, `scripts/test-seller-wp5.ps1`.
- `qa/fixture_server.py`, `qa/server.mjs`, `qa/safety.mjs`, `qa/seller-browser-session.mjs`.
- `qa/wp4_final_audit.py` now accepts only wp4/wp5 scope, preserving wp4 default behavior; read-only reuse, not a second deletion authority.
- Three WP5 reports, original finding ledger, backlog and journey-coverage addenda.

Prettier expanded preexisting inline templates, so line count is not business-logic
scope. Existing unrelated dirty-worktree/backup changes are preserved. No branch,
commit or push. No production `.env` changes.

## Final results and remaining work

**56 backend cases, 352 Angular cases, 59 Node QA self-tests, 54 Python QA self-tests,
21 authenticated browser checks passed.** Build/changed-file lint, TypeScript,
Ruff/Black, compileall, PowerShell parser and whitespace checks passed.
Eleven real axe scans: zero violations/incomplete checks in those tested states.
Bounded keyboard/focus and visual contrast spot review are not full WCAG certification.

Strict mypy across five changed backend contracts reports one **existing** schema
`Field(ne=0)` overload error at InventoryAdjustmentRequest.delta; untouched HEAD
shadow reports the same diagnostic. Other four changed routers pass in that run.
The unsupported validation keyword warrants separate runtime nonzero-adjustment
verification; it must not be dismissed as proof of complete input validation.
No assertion or check was disabled. Historical broader typing debt remains outside
this focused result. Bundle budget warning: **519.17 kB / 500 kB**, versus WP4 518.31 kB.

Final audit verifies **14/14 signed databases DROPPED/absent**, original 10 Docker
containers/networks/volumes preserved and 20 retained trace archives with valid CRC.
Seven earlier interrupted drops required exact-token guarded recovery; an attempted
90-second DROP also timed out during concurrent work, then succeeded after execution
settled. Original failures remain. Final accepted backend/browser runs cleaned
normally, exit 0. No FORCE, unrelated session termination or guessed-prefix deletion.

Remaining original findings: **009/017/020**. Global suspected contrast, WP4's seven
incomplete textarea checks, older QA gaps and backup/activation gates remain open.
Long page density, technical Product IDs and direct cost-evidence entry remain UX/
workflow limitations, not newly invented workflows. Live synchronization, actual
Amazon/Flipkart authorization, marketplace writes, real financial events and complete
cross-owner/assistive-technology coverage are unverified. Stop after WP5 for review.
