# Comprehensive seller-experience audit: validation and executive summary

2026-10-27. **AUDIT AND DESIGN DELIVERED / FRESH PERSISTED EXPLORATION BLOCKED.**
**Application certification remains INCOMPLETE. First real operation remains NO-GO.**

This assignment did not authorize implementation. No production fixes, finding
closures, owner waivers, new business authority or permanent activation occurred.
The PC-first encrypted backup/restore workstream remains parked and unresolved;
its prior tests are not counted as seller-experience tests in this report.

## Deliverables and evidence vocabulary

| Deliverable | Contents |
| --- | --- |
| [Application inventory](application-inventory.md) | Navigation, routes, backend domains/operations, artifacts, transitions, dependencies, source counts and unsupported/discoverability distinctions. |
| [Current seller journey](current-seller-journey.md) | Onboarding and each proposed transition assessed against all ten requested dimensions; source, historical and unverified behavior separated. |
| [Workflow gaps](workflow-gap-analysis.md) | Actual gaps versus intentional boundaries, historical workflow disposition and the minimum coherent supported experience. |
| [Information architecture/UX review](ux-information-architecture-review.md) | Task navigation, terminology, context handoffs, dashboard semantics, forms, density, accessibility and concrete bounded proposals. |
| [Target experience](proposed-target-experience.md) | Fourteen module contracts: entry/input/output/prerequisites/states/next/back/errors/provenance/HUMAN controls; no mandatory linear wizard. |
| [Completion backlog](prioritized-completion-backlog.md) | Twenty-five indexed new audit items, not twenty-five confirmed bugs; P0–P3, evidence, reproduction, dependencies, acceptance and automated/manual tests. All twelve existing open findings retained. |
| This report | Executive summary, actual current commands/results, blocked exploratory matrix and limits. |

Extra durable data: [full source inventory](application-inventory.json) and
[actual execution record](audit-execution.json). Existing Phase 4C and earlier
reports/backlog were read, not regenerated or silently reconciled into PASS.

- **SOURCE CONFIRMED:** exact current declarations, code paths or absent calls.
  This is not a claim that a complete seller task passed in a browser.
- **HISTORICAL:** original Phase 1–4C evidence remains at its original scope/date.
  No historical counts are added to this audit's execution totals.
- **UNVERIFIED/BLOCKED:** current persisted consequence or task was not executed.
  An API reference, matching heading or screenshot is not identity/approval proof.
- **PROPOSAL:** needs product review and separate implementation authorization.
  A confusing boundary is not permission to remove it.

## Executive summary: top ten seller-experience problems

These are a mix of source-confirmed gaps, semantic inconsistencies, historical
usability observations and unverified risks—not ten freshly demonstrated bugs.

| Priority order / item | Evidence and seller impact | Minimum proposed action |
| --- | --- | --- |
| 1. Selected opportunity stops short of Catalog (`SE-HANDOFF-001`) | The canonical HUMAN-shortlist-backed conversion endpoint and lineage exist, but no frontend conversion caller is present. Catalog promises conversion and sends the seller back to opportunity review. Source-confirmed missing handoff; fresh browser task BLOCKED. | Expose a bounded review-and-convert action using the existing API; preserve selection/assessment/goal/Product lineage and replay/conflict controls. |
| 2. “Suppliers” opens the wrong task (`SE-HANDOFF-002`) | Primary navigation opens Make a sourcing decision, while Find suppliers is Advanced cross-marketplace discovery. Source-confirmed task/label mismatch. | Repoint the task entry to existing discovery; label requirements/quotes/scenarios as commercial evaluation. Preserve supported deep links. |
| 3. Context is not consistently carried between supplier tasks (`SE-HANDOFF-003`, `SE-CONTEXT-005`) | Shared subnavigation omits query context; discovery supplies supplier_id that economics initialization does not consume. The code difference is confirmed; actual wrong-context behavior is UNVERIFIED. | First run two-goal/two-opportunity/two-supplier identity tests. Use existing owned context authorities, not global guesses or a second state store. |
| 4. Effective product selection is inconsistently queried (`SE-AUTHORITY-001/002`) | Some consumers filter historical shortlist before ordering, while readiness considers the latest decision across actions. Conversion's optional goal check is narrower than an explicit opportunity-goal consistency proof. Consequences remain UNVERIFIED, not a claimed approval bypass. | Validate shortlist→reject/archive and mismatched same-owner goal under canonical APIs before changing any consumer. This is an early safety investigation, not a downstream UI patch. |
| 5. Dashboard can overstate marketplace connection (`SE-METRIC-001`) | Backend active_destinations counts PublishingDestination, but the dashboard calls them sales channels connected and links to Marketplaces. Source-confirmed semantic mismatch. | Use the metric's true publishing scope. Display marketplace authorization only from its actual authority; local/fake records must never imply real connection. |
| 6. Existing-product entry is disconnected from research economics (`SE-HANDOFF-004`, `SE-UX-002`) | Manual products and opening stock are supported, but Catalog sourcing economics requires opportunity lineage. Product metadata quantity/cost are distinct from inventory movements/commercial evidence. Source-confirmed boundary; seller comprehension UNVERIFIED. | Explain the authorities and available next action. Let an existing seller start with genuine products/counts; do not force fake research or invent a second calculator. Approve any new manual-product economics adaptation separately. |
| 7. Research failures remain difficult to interpret (`SE-JOURNEY-001`, `QA-UX-PRE-RUN-MODE-001`) | Configured provider, recorded run mode, confirmed context, source approval, fetched product evidence and HUMAN selection are separate states. Current live discovery/relevance success was not exercised. Category token guards are not authoritative marketplace taxonomy proof. | One state-specific explanation and safe next action: unavailable/quota, policy approval, failed fetch, incompatible identity, or genuinely zero useful candidates. Do not promise success from a rewritten goal. |
| 8. Commercial review is dense and India currency needs explicit confirmation (existing economics/currency findings) | Historical economics pages are very long; current components combine multiple authority workflows. Product form still defaults currency to USD. Two historical screenshots reopened in this audit show that currency field, consistent with current source. | Summary of known/unknown/stale blockers and next action, in-page navigation and progressive detail. Explicit INR confirmation/preference design; retain all evidence and numeric rules. |
| 9. Action Center is advisory, not a generic execution system (`QA-P3-GAP-002`) | Existing action request truthfully records no approval/execution and does not implement a durable generic lifecycle. This is a supported-scope limitation, not permission to enable actions. | Name acknowledgement/request/approval/execution separately and route supported tasks to their existing canonical HUMAN workflows. Owner decides whether advisory-only scope suffices. |
| 10. Financial current projections are not immutable accounting history (`QA-P3-GAP-001`) | Current scope/version calculation upserts one row. Cost IDs now exist; that improvement does not reconstruct the exact earlier displayed result. | Label current/estimated outputs and obtain owner scope decision. Exact historical reconstruction needs separately approved design; no new GST/fee formula or synthetic history is proposed. |

Accessibility is an additional required verification gate, not omitted because it
is outside this top-ten task grouping. `QA-P4A-A11Y-MANUAL-001`, historical node
incompletes and the stock numeric-cell review stay open. A prior zero-violation
axe subset is not whole-app WCAG conformance.

## Critical handoffs and difficult-to-discover existing functionality

Source-confirmed missing or misleading handoffs: selected Opportunity→Catalog;
primary Suppliers→discovery; publishing destination metric→marketplace readiness.
Source-confirmed context differences requiring runtime proof: supplier subnav,
supplier→economics, later product rejection, optional conversion goal, and the
three Phase 4C artifact route identities. See the backlog for exact source lines,
repro steps, expected outcomes and tests; do not treat all of them as confirmed
broken runtime transitions.

Existing capabilities that should be connected, not rebuilt:

- Product conversion with CatalogProductLineage and HUMAN selection authority.
- Canonical supplier discovery, comparison, shortlist, evidence and due diligence;
  sourcing economics and separate source-approval/live-execution authorization.
- Channel-specific local listing drafts/mapping/readiness. Generic fake-adapter
  listing creation is not interchangeable with these draft authorities.
- Opening-stock entry, stock movements, reservations, stale/replay controls and
  operational cost evidence. Opening stock was implemented/validated in Phase 4B;
  it is not a newly missing workflow.
- Commerce Journey's existing eight-stage guidance, shared navigation/headers/
  state components and owned contexts; it is not a single transaction spanning
  inventory, channels, orders and finance.

Missing/unsupported capability decisions: generic durable Action Center execution,
immutable operational financial reconstruction, manual-product linkage to the
same sourcing-economics projection, and genuine registered/authorized marketplace
operation. Some are deliberate scope boundaries or external prerequisites, not
automatically features to build. UNKNOWN costs/fees/taxes/quotations remain UNKNOWN.

## Recommended implementation order — proposal, not execution

1. Agree the supported first-seller tasks: research/planning, existing-product
   local preparation, or real channel operation. Keep permanent activation blocked
   by the separate unresolved recovery and external prerequisites.
2. In fresh marked PostgreSQL fixtures, verify effective-selection/goal consistency
   and two-context handoffs. Fix only demonstrated authority defects under new
   authorization; never weaken HUMAN or owner boundaries to simplify a task.
3. Connect the existing conversion API, correct Suppliers entry and metric labels,
   and preserve exact product/supplier context. These precede cosmetic redesign.
4. Make research, assessment, stale/unknown and external-approval states actionable;
   clarify INR, product metadata, counted stock and real versus assumed costs.
5. Improve economics/research hierarchy and complete targeted manual/assistive
   accessibility review. Do not remove provenance or hide required controls.
6. Exercise channel-specific draft and operational scenarios with migration-backed
   fixtures. Resolve the historical account-list 502 uncertainty. Separately obtain
   real-provider authorization only if/when requested; none is granted here.
7. Decide the larger accounting/history and advisory-execution product scope;
   then review the backlog before any further workflow implementation.

Do not rebuild backend selection, approvals, arithmetic, stock ledger, fake/live
provider boundaries, source safety or the entire Angular application. No SaaS,
marketplace of VAYUJIT's own, autonomous QA fixer, linear mandatory wizard or second
owner is proposed.

## Actual current execution

Exact argv, working directories, exit codes, timings and log paths are retained
in [audit-execution.json](audit-execution.json). All commands used installed local
dependencies; no package installation, registry audit or provider request was run.

| Check | Current result | What it does NOT establish |
| --- | --- | --- |
| Existing `audit({write:false})` | 155 route declarations: 149 PAGE, six REDIRECT; 1,610 API declarations; 421 model declarations; 71 frontend spec files | Mounted runtime OpenAPI count, every operation's UI access or completed workflows. |
| Node QA unit/self-tests | **49 passed, 0 failed/skipped**, exit 0 | Application browser/DB behavior. A negative reporter fixture intentionally logs failure text; its assertion passes. |
| Python QA unit/self-tests | **28 passed, 0 failed/skipped**, exit 0 | Persisted supplier/economics/order correctness against PostgreSQL. |
| Angular suite | **267 passed, 71 files**, exit 0 | Authenticated Chrome, server permissions or all screen states. |
| Production build | **PASS**, exit 0 | Release readiness. Existing 517.89 kB initial bundle exceeds advisory 500 kB by 17.89 kB. |
| Existing Playwright discovery | Phase 1: 8; Phase 2: 8; Phase 3: 18; Phase 4: 44; Phase 4B: 16; Phase 4C: 8 listed | **Zero tests executed** by `--list`; phases/viewports overlap and must not be summed as unique requirements. |
| Existing disposable-runtime preflight | **BLOCKED**, exit 1, `QA_ADMIN_REQUIRED` at `qa/probe-owned-runtime.mjs:8` | No application defect, fixture startup, PostgreSQL connection, database creation or cleanup success. It exits before provisioning. |
| Fresh persisted API/browser/axe | **0 executed; BLOCKED** | No new confirmation or closure of the original findings. |
| Preservation | **1,276 checked files unchanged; zero added in protected source/history sets** | Database content hashing or certification; no database was contacted. |
| Git whitespace | PASS | Whole-repository lint, typing, migrations, dependency security or manual accessibility certification. |

Documentation validation also passed: all seven required Markdown artifacts,
36 local link targets, matching machine-inventory counts and a final independent
recheck of the same 1,276 protected file hashes; no changes or broken links found.
The local check record is `tmp/seller-experience-audit/document-check.json`.

The 344 passing current tests are 49 QA Node + 28 QA Python + 267 Angular tests,
not 344 unique seller requirements. No historical backend/browser counts were
added. New screenshots/traces/network recordings were not fabricated.

Preservation covered `apps/web/src`, `apps/api/vayujit_api`, `apps/api/alembic`,
`scripts`, `qa`, and existing `docs/qa`, excluding generated caches and this new
audit directory. Baseline hashes are at
`tmp/seller-experience-audit/preservation-before.json`; execution records contain
the final zero-delta comparison. Existing dirty changes were preserved, not reset.
Only the new audit reports/data and temporary audit execution helpers/evidence
were created; Angular generated its normal build/cache output.

## Phase C exploratory scenario disposition

All eighteen requested scenario groups need the missing disposable PostgreSQL
prerequisite for a fresh authenticated task. Source/historical references are
supporting evidence, not current passes.

| Requested scenario | Current disposition / prerequisite and retained coverage |
| --- | --- |
| First-time empty application | BLOCKED: fresh owner/brand fixture; historical smoke covers bounded setup. |
| Goal but no opportunities | BLOCKED: owned goal/plan/run fixture; no provider call or forced candidate allowed. |
| Opportunity without sufficient research | BLOCKED: real supported synthetic assessment/evidence states. |
| Missing/conflicting research evidence | BLOCKED: canonical source/evidence fixtures with explicit UNKNOWN/contradictions. |
| Product selection and rejection | BLOCKED: current assessment, HUMAN shortlist/reject and fresh reconstruction; SE-AUTHORITY-001 needs explicit consistency test. |
| Supplier comparison | BLOCKED: selected product plus legitimate synthetic candidates/assessments, including one-supplier/NOT_COMPARABLE. |
| Missing supplier quotations | BLOCKED: preserve absence versus assumption, no fabricated MOQ/price/lead time. |
| Changed landed-cost assumptions | BLOCKED: original independent freshness/oracle tests are historical only. |
| Unknown marketplace fees | BLOCKED: explicit UNKNOWN inputs, no zero or invented fee schedules. |
| Inventory initialization | BLOCKED: supported Phase 4B opening-stock authority and reviewed count fixture, not product metadata edit. |
| Marketplace onboarding unavailable | BLOCKED: authenticated credential-free/default-deny account state; no real account/API authorization implied. |
| Existing operational records | BLOCKED: canonical synthetic inventory/order/financial events in fresh persisted scope. |
| Interrupted journeys | BLOCKED: exact owned runtime/reply interruption and replay identity; not backup/restore. |
| Duplicate actions | BLOCKED: real committed API replay/conflict/concurrency scenarios, not unit mocks alone. |
| Stale data | BLOCKED: old assessment/version and changed material inputs, latest effective selection. |
| Error recovery | BLOCKED: scoped brand/API/action failures with retry; failed response must not look empty/successful. |
| Desktop/mobile navigation | BLOCKED: authenticated disposable contexts, Back/Forward/reload/new tab and precise artifact identity. |
| Keyboard/accessibility behavior | BLOCKED: actual affected states with axe and manual focus/reading order; no new scans claimed. |

Read-only visual review reopened the existing historical Phase 4C desktop and
mobile `QA-P4C-04/5-final-screen.png` screenshots under installations
`8644b989a75faaef` and `c84e3310c5656b03`. The mobile capture shows a visible focused
USD field and stacked pricing inputs; desktop shows adjacent Catalog/Products
navigation and the same currency field. Source confirms USD default at
`products/product-form.component.ts:193`. The visible 19.99 is the form's source
placeholder, not proof of persisted fabricated pricing. These are two reviewed
historical images, **not two newly executed browser scenarios**, accessibility
passes or pixel measurements of today's built app.

## Safe reproduction and missing HUMAN input

From repository root, available non-database checks:

```powershell
npm.cmd run qa:unit
& .\apps\api\.venv\Scripts\python.exe -m pytest qa/unit -q -o addopts= -p no:cacheprovider
npm.cmd run test --workspace @vayujit/web -- --watch=false
npm.cmd run build --workspace @vayujit/web
# Discovery only, not a test run:
node node_modules/@playwright/test/cli.js test --config qa/playwright.config.mjs --list --reporter=list
git diff --check
```

Use the exact Node/Python paths in the execution JSON if those commands are not
in the current shell's PATH. Process-approved access made the installed local Node
available; initial sandbox path denial was not classified as software absence.

To unblock persisted exploration, the owner must supply an **approved loopback QA
PostgreSQL admin connection targeting database `postgres`**, capable of creating
only the harness's fresh token-marked test installations, in the current process
as `QA_DATABASE_ADMIN_URL`. Do not paste credentials into this report/chat, change
production `.env`, reuse a business/golden database, or guess credentials. The
harness rejects non-loopback/non-postgres admin targets and reused test names.
Existing fixture cleanup is exact-token/marker guarded; do not manually delete
unrelated databases or Docker resources.

Once provided, the existing safe prerequisite/runtime check is:

```powershell
node qa/probe-owned-runtime.mjs
```

Then resume the named existing Playwright/API scenarios using the normal guarded
fixture, default-deny network policy and genuine synthetic canonical API artifacts.
Preserve old reports first: `qa/run.mjs`/report generators update existing Phase
reports, and `archive-reports.mjs` does not automatically cover every Phase 4C
artifact. A separately reviewed audit-output configuration or explicitly preserved
run is needed; do not overwrite history just to obtain browser output. Current
fixtures use `Base.metadata.create_all`; successful fixture tests alone do not
certify Alembic migration-head behavior.

## Remaining unknowns and stop decision

No real provider discovery quality, seller registration, API entitlement, official
provider contract, live read-only import, publishing, procurement, payment,
supplier contact, GST/fees or real profitability is certified. No marketplace or
supplier network operation occurred. No permanent database was initialized or
modified. No branch, commit or push was made. Backup scripts/resources were not
executed or changed by this audit.

Unverified consequences include effective rejection across consumers, owned goal
lineage, two-context/deep-link behavior, dashboard initialization failure recovery,
unexercised artifact-dependent routes, full owner/auth attack matrix, historical
accounts 502, current migration safety, all conditional accessibility nodes and
seller comprehension. Unit passes and route counts do not waive any of these.

The existing twelve open finding IDs and historical priorities remain intact;
resolved opening-stock, financial freshness, HUMAN replay, provenance and resolved
signal work are not reimplemented or silently reopened. Owner decisions and the
minimum coherent completion criteria are in the backlog and gap analysis.

**STOP: review this audit, target experience and completion backlog before any
production implementation.** The audit makes no application-complete, WCAG,
first-seller operational or encrypted-backup certification claim.
