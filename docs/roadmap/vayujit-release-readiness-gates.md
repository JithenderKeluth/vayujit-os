# VAYUJIT release-readiness gates

2026-11-06. **Application INCOMPLETE; production readiness NOT ESTABLISHED.**
This ledger separates supported local functionality from accessibility,
operational qualification and actual external activation. It grants no authority
and does not reinterpret historic results. See the
[assessment](vayujit-remaining-work-assessment.md),
[execution plan](vayujit-forward-execution-plan.md) and
[accessibility backlog / cleanup proof](../qa/seller-experience/wp7b-consolidated-accessibility-backlog.md).

Status vocabulary: VERIFIED PASS is limited to cited scope; NOT PASSED includes
a demonstrated failure; NOT VERIFIED is missing sufficient evidence; PENDING
DECISION requires owner scope/acceptance; PARKED means intentionally not resumed.
NOT APPLICABLE requires evidence and an approved scope rationale, not omission.

## Gate ledger

| Gate | Current status and evidence | Objective exit / accountable role |
| --- | --- | --- |
| G01: R5 isolation and cleanup | **VERIFIED PASS by independent post-cleanup checks**. R5 target absent, signed DROPPED, owned processes/listener absent, normal API tree preserved, frontend already absent. Raw watcher ordered-mount warning retained and separately explained. | Preserve receipts and fingerprint. Future runs require fresh authority. QA owner; current closure is not a new session permission. |
| G02: supported local functional scope | WP7A **PASS, LOCAL SUPPORTED FUNCTIONAL COVERAGE**: 48 prioritized entries (41 inherited + 7 targeted), not whole application. [WP7A7 gate](../qa/seller-experience/wp7a7-gate.json). | D0 scope map and C1/C4 evidence for every included critical operation, positive/negative/concurrent/persisted/reload/error/context paths. No unresolved P0/P1 or material authority/data failure. Product owner + engineering + independent QA. |
| G03: WP7B Gate A | **PASS inherited from R1**; valid R4 login and R5 Campaign focus corrections retained at 8.56:1. | Do not reopen without contrary evidence or affected-source change. Accessibility reviewer. |
| G04: WP7B Gate B / required accessibility | **NOT PASSED**; raw R5 gate FAIL. 40 groups: 9 PASS, 1 FAIL, 30 NOT VERIFIED. Empty Email border 2.09:1; speech/zoom/applicability incomplete. | Separately authorized A1 fix; A2–A5 actual manual/rendered evidence; all mandatory rows sufficiently disposed, no blocking defect. No DOM-only reader proof or axe-only WCAG claim. Accessibility reviewer + actual human listener. |
| G05: owner/HUMAN/provider security | Bounded local negative/concurrent/default-deny tests exist; current release-wide certification **NOT VERIFIED**. `ck_users_single_owner` and Electron secure defaults source-confirmed. | Included endpoints/UI/worker/Electron paths preserve exact owner/artifact/version, distinct source/execution permission, expiry/revocation/stale/replay/concurrency, session/origin/SSRF/private-media controls; no unexpected external call. Current security/dependency assessment, no unresolved critical issue. Security/engineering + QA. |
| G06: financial/data correctness | Bounded Decimal/provenance/freshness/replay tests PASS; source vs rounded order-unit limitation retained. Full intended-use integrity **NOT VERIFIED**. | Literal independently calculated Decimal/currency expectations, UNKNOWN not zero, conserved allocations, no stale READY or synthetic-to-real upgrade, persisted source/lineage and context consistency at release baseline. Financial domain engineer + QA. No invented fee/GST schedule. |
| G07: accounting/retention purpose | **PENDING DECISION**. Same-scope/version working snapshots are mutable; no immutable ledger/period close/statutory reconciliation certification. Sole-accounting use NO-GO. | Owner explicitly chooses disclosed projections plus a separate appropriate accounting/record authority, or separately approves and validates missing history/reconciliation architecture. Scope decision cannot claim a ledger was implemented. Owner/accounting adviser. |
| G08: schema/migration compatibility | Later local repairs/rehearsals exist; historical 3 nullable mismatches/105 unmatched index names remain classified debt. Full deployment/historic-data compatibility **NOT VERIFIED**. | Current exact migration graph, fresh and representative existing-data isolated upgrade tests, preserved values/constraints and tested rollback/recovery. No blind stamping, backfill or blanket index creation. Source/permanent migration requires separate exact authorization. DB/engineering + QA. |
| G09: reliability/recovery semantics | Local workflow checkpoints/idempotency/guarded cleanup evidence exists; broader operational proof **NOT VERIFIED**. Historical Ads/account 502 and PG timestamp attribution unresolved. | C2 bounded interruption/unavailable/timeout/unknown-outcome tests; correct original-error preservation, no duplicates, recoverable state and safe diagnostics. Unknown historical cause disclosed with impact/mitigation, not invented resolution. Engineering/operations + QA. |
| G10: encrypted independent backup/restore | **PARKED / NOT CERTIFIED for PC-first activation**. No successful complete independent rehearsal or verified independent destination inferred here. | Separately authorized actual encrypted DB+media backup/restore into isolated target, canonical records/financial precision/source integrity, wrong-key/corruption, durations, ACL/key custody and physically independent destination evidence. Restore actually executes. Operations + owner. |
| G11: performance/capacity | Historical small-dataset baseline; R5 production build PASS, initial 422.81 kB. Intended workload/SLO **NOT VERIFIED**. | Agree single-seller volumes and host budget; measure p95, query/payload counts, queue throughput, connection pools, CPU/RAM/disk/media growth under representative synthetic load. Tune demonstrated bottlenecks, not speculative SaaS infrastructure. Owner + performance/operations. |
| G12: maintainability/static/dependencies | Recent scoped checks PASS; historical repository mypy/lint/schema debt and Campaign lifecycle warning retained. Whole-release state **NOT VERIFIED**. | Current affected-path strict checks and explicit old/new diagnostic ledger; no suppressed new errors. Assess each debt item touching startup/auth/finance/worker integrity. Current dependency/license/security review, scoped remediation or explicit risk decision where appropriate. Engineering/security. |
| G13: packaged runtime / installation / rollback | Electron secure defaults and old smoke evidence exist. Current package qualification **NOT VERIFIED** by R5 browser results. | Exact artifact/hash/config, install/upgrade/startup/shutdown, app-scheme deep links, private media/session/origin boundaries, safe update rollback and no lost data in isolated rehearsal. Windows runtime evidence separate from desktop viewport emulation. Engineering/operations + QA. |
| G14: monitoring and runbooks | Health, readiness, safe logs/correlation, maintenance/worker/doctor foundations exist; actual intended-runtime alert delivery **NOT VERIFIED**. | Startup/DB/worker/provider/backup failure visible and actionable; PII/secret-safe logs and retention; owner can identify failed service, stop external actions, recover and escalate. Verify intended notification path, not real commercial actions. Operations + owner. |
| G15: genuine business onboarding | **EXTERNALLY PENDING**; no genuine seller readiness claimed from fixtures. [Activation plan](../seller-os/production-activation-plan.md). | Owner enters genuine identity/registration/tax/category information as applicable, products/SKUs/counts/costs/media and evidence with unknowns explicit. No synthetic account/order/finance/inventory promotion. Owner and appropriate advisers. No legal/tax requirements invented in this review. |
| G16: actual provider read-only certification | **NOT VERIFIED / EXTERNAL DEPENDENCY**. Fake transport and local preparation are not Amazon/Flipkart/Ads/etc connectivity proof. | Provider-specific official contract and eligibility verified, genuine credentials securely issued, supported sandbox evidence then separately approved live read-only with bounded budget, provenance/error/revocation checks. Unsupported contract details remain UNVERIFIED—HUMAN FOLLOW-UP REQUIRED. Owner/provider/security. |
| G17: external writes/commercial execution | **NOT AUTHORIZED**. HUMAN workflow presence is not consent to any real action. | Separate exact operation/artifact/provider/account/environment/time/budget authorization, all canonical prerequisites, kill switch/revocation/expiry/idempotency/audit intact, unknown-outcome recovery. Never infer permission from G16 or a UI button. Owner. |
| G18: final release/activation decision | **NO COMPLETE APPLICATION OR PRODUCTION PASS**. No WP8 execution authorized. | Signed versioned scope + gate evidence + prohibited uses + owner acceptance; required failures/unknowns remain blockers, not renamed warnings. Local application approval and real-data/provider activation are separate decisions. Owner + independent QA + engineering/operations. |

## Decision rules

1. Supported **local application** release requires G02–G09 and G11–G14 to satisfy
   their approved local scope, with G03/G04 explicit and no unresolved blocking
   authority/data/security/accessibility defect. G01 and every new QA cleanup
   must be verified. An old conditional report cannot overrule a new confirmed
   failure. Evidence-only exceptions need explicit acceptance provenance and
   cannot falsely assert unexecuted behavior.
2. **Real-data PC-first activation** additionally requires G10, G15, intended-use
   G07, operational/host readiness and the relevant G18 owner decision. Recovery
   remains parked until separately resumed, so activation is not authorized now.
3. **Provider use** additionally requires relevant G16; real commercial writes
   additionally require G17 for the exact action. No requirement to certify
   unsupported providers merely to use an approved offline/local feature, but
   owner must approve truthful release boundaries. No silent menu/scope exclusion.
4. Do not equate locally certified, externally pending, unsupported, and defective.
   No single green percentage substitutes for this gate ledger. No automatic
   waiver of accessibility, accounting or recovery in exchange for other tests.

## Evidence freshness and bounded regression policy

For each gate retain source/build/dependency fingerprints, tool/browser/runtime
versions, synthetic/live provenance, exact command, expected/actual outcome,
independent assertions, sanitized trace/screenshot references, cleanup and
reviewer. Inherited counts are labelled inherited; overlapping suites are never
added into a fictitious unique total. Preserve failures and unknowns.

Changed code requires affected tests and dependent-path retests; C4 performs the
consolidated release matrix once after stabilization. Manual speech and native
zoom cannot be inherited from mere availability or CSS simulation. Live
certification cannot be inherited from fake data. Backups cannot be certified
from an artifact listing or an unexecuted restore plan.

## Validation performed for this planning delivery

No application/browser/regression suite rerun, new QA database, migration,
application change, normal process interruption, provider call or backup rehearsal.
New evidence is limited to R5's already-authorized normal shutdown/cleanup and
independent read-only checks: one target database absent/signed DROPPED, no owned
process/listener remaining, normal development identities preserved, canonical
Docker inventory unchanged; 36 preserved reports/0 mismatches and 25 trace
archives/0 CRC failures. The post-cleanup 510-file fingerprint is preserved.

Executed documentation checks:

| Check | Actual result |
| --- | --- |
| Requested artifacts | 4/4 present. |
| Local Markdown link targets | 27 checked, 0 missing. |
| Stable accessibility crosswalk | 40 rows, 40 unique IDs, all 40 original groups represented, 0 verdict mismatches against R5 JSON. No acceptance source edited. |
| Post-cleanup R5 preservation | 510 files including 8 R5 reports; aggregate SHA-256 still `4842ea9e3c7511fc72e4d143819a17b25a94e60a54ee169d8a1829f9b3002df8`. |
| Tracked worktree whitespace | `git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check`: exit 0; existing LF/CRLF conversion warnings retained, no whitespace errors. |
| New untracked documents | Separate read-only Node check: 4 files, 0 trailing-whitespace/conflict-marker/missing-final-newline failures. Git's tracked diff check alone does not cover these new files. |

Link/matrix/fingerprint checks used a read-only Node module via PowerShell stdin
(`node --input-type=module`); no report generator, application test runner or
service was launched. These are documentation/integrity results, **not new
application test passes**. Stop for owner review; no WP7C/WP8 implementation or
backup resumption follows automatically.
