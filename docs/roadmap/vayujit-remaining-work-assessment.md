# VAYUJIT remaining-work assessment

2026-11-06. Read-only repository/evidence review plus documentation. **Application
certification: INCOMPLETE. Production readiness: NOT ESTABLISHED.** No meaningful
single completion percentage follows from route counts or accumulated test counts.

## Basis, precedence and scope

The latest bounded closure evidence takes precedence over older gap titles, but
only for its exact demonstrated assertions. Principal sources:

- [WP7 certification plan](../qa/seller-experience/wp7-certification-plan.md),
  [report](../qa/seller-experience/wp7-certification-report.md) and
  [route inventory](../qa/seller-experience/wp7-route-and-capability-inventory.md).
- WP1–WP6 resolution ledgers in `docs/qa/seller-experience/`; particularly
  [WP6B remediation](../qa/seller-experience/wp6b-remediation.md) and
  [financial policy](../qa/seller-experience/wp6b-financial-precision-policy.md).
- [WP7A7 closure](../qa/seller-experience/wp7a7-closure-report.md),
  [gate](../qa/seller-experience/wp7a7-gate.json),
  [R5 gate](../qa/seller-experience/wp7b-r5-gate.json) and
  [consolidated accessibility/cleanup record](../qa/seller-experience/wp7b-consolidated-accessibility-backlog.md).
- [Existing seller roadmap](../ux/seller-os-implementation-roadmap.md),
  [capability matrix](../ux/seller-os-capability-matrix.md),
  [original product roadmap](../product-readiness/18-implementation-roadmap.md),
  [definition of done](../product-readiness/19-definition-of-done.md).

The original WP7 specification and reviewed repository material refer to stopping
before WP8; they do **not** establish an approved detailed WP7C or WP8 contract.
The mappings below are **proposals for owner approval**, not claims that those
packages exist, are implemented, or are now authorized. Historic release-candidate
documents predate the present catalog/marketplace scope and cannot certify it.

## Preserved architecture and implementation boundaries

Current source inspection confirms Angular in `apps/web`, FastAPI in `apps/api`,
Electron in `apps/desktop`, PostgreSQL application persistence and SQLAlchemy
domain authorities. `identity/models.py` retains `ck_users_single_owner`, the
singleton check plus unique singleton key: one owner per installation/database,
not shared SaaS tenancy. Owner isolation tests must not remove that invariant.

`apps/desktop/src/window-options.ts` enables sandbox, context isolation and web
security, and disables Node integration. `main.ts` denies new in-app windows and
permission requests, guards navigation and loads the packaged app scheme. This
source presence is not a fresh packaged-Electron security certification; URL
boundary handling and packaged update/runtime behavior need current-version
tests before release. `main.py` exposes `/health/live` and `/health/ready`; a
404 at `/health` is not proof the API is down.

Canonical domain services remain responsible for goal/plan/run, product identity,
selection, Catalog lineage, supplier evidence/DD, commercial inputs, calculations,
HUMAN decisions, listings, orders, stock, finance and workflow execution. UI/agent
code must not become a second calculation or authorization authority. Preserve
source approval versus execution authorization; freshness fingerprints, expiry,
revocation, one-use/concurrency and replay protections; provenance and audit.

Finance source inspection confirms `FinancialCalculationSnapshot` has a unique
owner/scope/calculation-version key. Same-version updates replace working metrics
and lineage; this is **not append-only accounting revision history**. Decimal
strings, explicit rounding, preserved source totals, currency/FX evidence and
UNKNOWN versus zero remain mandatory. No new ledger or numeric-scale migration
is implicitly approved by a desire for completion.

## Current capability and gap assessment

| Seller capability | Demonstrated local support | Remaining evidence, integration or product boundary |
| --- | --- | --- |
| Owner setup/login/navigation | Protected routes, safe return paths, owner invariant, deep links and mobile navigation have bounded tests. | Manual reader/zoom checks and confirmed empty-login field border defect remain. Packaged Electron is a distinct release target, not certified by Chrome alone. |
| Goals → evidence → selection | Goal/plan/run, category/evidence review, source approval, current vs historical opportunities and HUMAN selection authorities exist; later WP2/WP7A closure supersedes early missing-handoff titles. | Real discovery usefulness, provider quotas/approved fetches and category relevance with actual permitted sources require separate live-read-only authorization/evidence. Zero eligible products can be a legitimate outcome; no fabricated candidate to close a gate. |
| Selection → Catalog | Canonical conversion/lineage, owner/product/goal context and replay/stale handling have later bounded coverage. Manual product entry is independently supported. | Do not reopen the early audit's missing conversion CTA as a current defect without a fresh reproduction. First-time task comprehension and broad conditional coverage are not equivalent to route rendering. |
| Suppliers → DD → sourcing decision | Discovery modes, context preservation, evidence/claims/unknowns, assessment/shortlist, costs, comparison and explicit HUMAN decisions have local synthetic journeys. | Genuine supplier verification, quotes, source entitlements, acquisition or contact are not certified by synthetic fixtures; no permission to contact follows from approval to read. |
| Economics/pricing | Acquisition lineage/freshness, canonical landed/unit costs, exact amount strings, conflict/idempotency guards and deterministic rounding tests exist. Manual costs remain ASSUMED. | Long economics pages remain usability debt. No invented fees/GST/FX. Confirmed quote/source evidence is a real-business prerequisite, not another UI feature. |
| Catalog/variants/private media | Creation/edit/version rejection, secure assets, Product/variant context and controlled listing preparation locally tested. | Current release media ACLs, expiry/access behavior, capacity and independent recovery remain deployment gates. Synthetic assets cannot become business stock by promotion. |
| Inventory/orders | Opening stock, append-only movement/reservation/ATP, SKU mappings, duplicate/concurrent/stale controls and synthetic order ingestion supported. | Real channel reconciliation, unknown-outcome imports, host interruption and credible workload performance need scoped operational proof; no assumed live sync or oversell guarantee from fake orders. |
| Amazon/Flipkart/Meesho | Local draft/review/authorization safeguards and fake transport tests; Meesho manual/local boundary is explicit. | Real registrations, provider eligibility, official contracts, credentials, connectivity and live-read-only certification externally pending. Real submission/spend always requires later exact HUMAN authority. Seller registration does not imply API entitlement. |
| Dashboard/Action Center | Corrected metric labels, signal filtering/lifecycle and canonical deep links locally exercised. Recommendations are advisory. | Generic consequential execution is not implemented and is not required unless owner explicitly chooses it. Do not create a parallel approval engine to make a recommendation executable. |
| Financial projections | Exact Decimal allocation/rounding, known zero/negative profit, missing-cost UNKNOWN, provenance and reload subsets tested. | Mutable same-version projections, rounded order units vs exact source totals, reconciliation/history/period-close/accounting limitations remain. Sole-accounting use is NO-GO without an approved solution. |
| Content/images/video/campaigns/Ads | Later schema repair and WP7A7 immutable artifact, stale/duplicate, local preview and controlled workflow cases close specific earlier gaps. | Historical Ads 502 remains unattributed; provider expiry outside an authoritative contract stays UNVERIFIED. No external render/publish/ad-spend certification. Advanced surfaces need explicit initial-release inclusion decisions, not silent exclusion. |
| Operations/security/recovery | Maintenance, workers, checkpoints, correlation IDs, default-deny modes, production-like Compose/nginx/security and readiness foundations exist. | Host-level restart/power-loss, current packaged release, real monitoring/alert delivery and independent encrypted PC-first restore are separate unclosed launch gates. Backup remains PARKED here. |

This is not a new execution report. WP7A's **48 prioritized functional entries**
(41 inherited + 7 targeted) are locally closed within their contract; they are
not 156 complete workflows. WP7's 156 declarations/124 rendered templates are
inventory/render evidence. No uncovered operation becomes PASS by association.
No current untriaged application P0/P1 is demonstrated by this review; that is
not evidence that no undiscovered critical defect exists.

## Residual risks requiring decisions, not repeated R5 runs

| Risk | Evidence and classification | Required disposition / impact |
| --- | --- | --- |
| Accessibility | Gate A PASS; Gate B NOT PASSED; 9/1/30 across 40 groups. Confirmed 2.09:1 auth boundary plus human/zoom/applicability gaps. | Parallel release-blocking backlog, finite tasks A1–A5. Do not downgrade a demonstrated defect to a documentation limitation. |
| Financial history | `QA-P3-GAP-001`; mutable per-version projections, not immutable ledger. `SE-WP5-PRICE-001` preserves raw precision and warns about rounded units. | Owner chooses planning/projection use with an external accounting authority, or separately designs append-only/reconciliation capability. No implicit acceptance or invented historical precision. |
| Advisory execution | `QA-P3-GAP-002`; canonical Action Center intentionally advisory, no generic execution authority. | Keep truthful advisory scope; new generic automation only under separate requirements/security design. |
| Ads 502 / account 502 | Historical observations, not resolved by later HTTP 200. Proxy classification improves future evidence, not historical attribution. | Bounded failure/recovery tests and observability review. Preserve unknown cause if unavailable; a recurrence with correctness/authority impact escalates immediately. |
| PostgreSQL timestamps | Historical attribution unresolved. Current R5 mount ordering discrepancy is separately explained. | Evidence-only provenance review; no database restart/recovery or assumed actor. Significance must be assessed before release, not falsely closed. |
| QA DROP reliability | Prior timeouts/tombstones required exact approved guarded recovery; latest R5 normal cleanup succeeded. | Test signed lifecycle interruption/cleanup under fresh authority; never reuse an expired token or generalize permission to recover unrelated runs. |
| Schema/index debt | Historical 42-table scoped review: 3 nullable mismatches; 105 unmatched index names, 26 with left-prefix paths and 79 equivalences unproven. | Representative query plans/load and semantics first. Not 105 proven slow queries; no blanket index/backfill/NOT NULL migration. Existing-data repair needs separate authority. |
| Static/dependency debt | WP7 recorded 219 historical mypy diagnostics and `main.py` import-order debt; R5 scoped checks/build pass and one Campaign lifecycle lint warning retained. | Rebaseline affected release paths with exact tool/revision; distinguish new from old. Security/startup/authority/finance implications block release even if old. Suppression or weakening budgets is not closure. |
| Performance/capacity | Earlier small-dataset baselines and current 422.81 kB R5 initial bundle are bounded evidence. | Measure single-seller volumes, query counts, payloads, DB/media growth, worker queues, CPU/RAM/disk and p95. Define owner-accepted workload/SLO before tuning. No SaaS scaling redesign. |
| Observability | Health/readiness, safe correlation/logging, heartbeat/dead-letter/recovery foundations exist. | Demonstrate actionable startup/provider/worker/backup failures, secret-safe logs and actual notification delivery in the intended runtime. No claim from configuration presence alone. |
| Recovery/activation | PC-first encrypted independent restore/destination independence not certified in this workstream. | Remains PARKED, real-data activation blocked until separately authorized rehearsal and key/destination custody checks pass. Existing backups/copy-migration evidence is not interchangeable with this gate. |

## Superseded claims and preserved exceptions

Do not reimplement opening stock (Phase 4B), resolved Phase 2 freshness/HUMAN replay,
Phase 3 synthetic provenance/resolved filtering, WP1–WP6 handoffs or later video/
Ads schema repairs merely because an older backlog lists them. Reopen only with
exact contradictory evidence. Likewise an old bundle warning is not current
initial-budget failure after the validated lazy-loading correction.

L-17's offline authorization interpretation had explicit owner approval. Preserve
that acceptance provenance and the unverified live-provider expiry boundary;
do not invent another waiver or certify real expiry from fake fixtures. R3
auto-reload side effects remain historical evidence, not retrospectively
attributed to owner changes. Earlier audit percentages and dates are not a
current release classification.

## Minimum forward scope

1. Owner approves first-release capability and accounting boundaries.
2. Proposed **WP7C**: bounded residual correctness, security/data-risk and
   operational reliability closure on authorized synthetic infrastructure, using
   existing authorities. Accessibility A1–A5 proceeds in parallel, not as an
   indefinitely repeated prerequisite to functional work.
3. Proposed **WP8**: versioned release-candidate/PC-first deployment qualification
   and owner-controlled pilot preparation after local application gates; actual
   backup resumption, permanent activation and real-provider work each need
   explicit separate authority. No implied live rollout.

See the [execution plan](vayujit-forward-execution-plan.md) and
[release gates](vayujit-release-readiness-gates.md). None of these proposals is
implementation authorization. No new database, app process interruption,
application edit, provider request, branch, commit or push occurred in this review.
