# VAYUJIT forward execution plan

2026-11-06. **Proposed plan for review, not an implementation instruction.**
R5 is closed; no R6 or replacement standing QA session is proposed. WP7C/WP8
names below are provisional mappings requiring owner approval because the
reviewed material does not define their detailed approved scope.

## Execution policy

Work advances through bounded causes, not repeated whole-app retesting. Freeze
the expected artifact/state and original acceptance assertion before each task;
reproduce once, correct the root cause minimally, add focused regressions, then
independently retest the changed and dependent journey. Retain failed attempts.
End each package with exact PASS/FAIL/BLOCKED/NOT VERIFIED evidence and cleanup.
Do not automatically extend sessions, add checks or initiate the next package.

Prioritize demonstrated security/financial/data-integrity failures over cosmetic
improvements. None is newly demonstrated as P0/P1 in this planning review; a
historical/unreproduced risk is not relabelled a confirmed critical bug. Conversely
historical origin does not excuse a production-critical defect once demonstrated.

Preserve one owner per installation, PostgreSQL, canonical Angular/FastAPI/
Electron boundaries, owner-scoped access, HUMAN approvals, provenance/lineage,
Decimal/currency rules, UNKNOWN, audit, concurrency and idempotency. Never alter
business behavior or QA thresholds solely for a green test.

## Priority and dependency sequence

| Package / priority | Objective and dependencies | Implementation scope / exclusions | Tests and objective acceptance | Effort and main risks |
| --- | --- | --- | --- | --- |
| D0: first-release contract / first | Owner chooses included seller operations, supported runtime, financial authority and acceptance owners. Input: remaining-work assessment and existing 48-entry closure. | Requirements/evidence reconciliation only: map each included capability to current evidence, exclusions and live dependency. No feature coding. Explicitly decide advanced Ads/video/autonomous exposure, not silent route deletion. | Every included critical operation has an original acceptance source and evidence or named gap. Owner signs scope; unresolved items cannot disappear. No synthetic-to-real equivalence or sole-accounting implication. | 0.5–1 engineering day plus owner decisions. Risk: scope inflation/waiver disguised as clarification. |
| C1: WP7C residual integrity/security / next implementation candidate | D0 approved; fresh disposable QA authority and frozen source/tool baseline. Parallel with A tasks. | Exercise exact owner/HUMAN/fingerprint/replay/stale/UNKNOWN/financial lineage boundaries across research→selection→Catalog→supplier/DD→economics→decision and stock→orders→finance. Reuse WP7A evidence; implement only newly reproduced, approved low-risk defects, at most three root causes per batch. No new accounting engine, integration or schema repair. | Persisted positive/negative/concurrent/reload tests plus authenticated affected Chrome/Edge desktop/mobile journeys; independent expected Decimal amounts, raw-source vs rounded-unit checks, no hidden context substitution, synthetic provenance retained, no external egress. Existing 48 entries not silently narrowed. Zero unresolved P0/P1 in included operations and documented status for every risk. | 2–4 days for bounded review/tests, not a promise to fix unknown failures. Risks: stale historical findings, authority duplication, overbroad QA setup. Escalate high-risk change separately. |
| C2: WP7C reliability/diagnostics / after C1 boundary baseline | Fresh QA authority; retain historical Ads 502, PG timestamp and cleanup evidence. | Bounded controlled provider-unavailable/timeout, worker interruption, unknown committed outcome/retry, session expiry and safe error/health propagation. Improve diagnostics only for demonstrated gaps; no real publishing, host-wide interruption or permanent data. Read-only PG attribution review cannot mutate/recover data. | Deterministic local fake faults, no duplicate action, durable identity/checkpoint/freshness, redacted correlation and useful recovery UI. Exact process ownership and default-deny assertions. Normal cleanup verified; if not, stop and obtain exact recovery authority. Historical unknown cause may remain unknown but must have an impact/mitigation decision. | 2–3 days. Risks: confusing a proxy 502 with app failure, recovery masking original error, orphaned QA. No unlimited historical-cause hunt. |
| C3: WP7C affected-path quality/performance / after D0, parallel C2 | Owner-defined single-seller workload, hardware and data volume assumptions. | Review current package/dependency/static baseline, Electron boundaries, hot query/payload paths; measure before tuning. Correct only approved demonstrated release-path defects. No broad typing refactor, arbitrary indexes, SaaS scaling or silent budget increases. | Exact version/tool and warning inventory; strict changed-path checks, Angular/build, backend/QA/security tests, migration tests only under fresh DB authority. Profile p95/query count/pool/CPU/RAM/disk at agreed load; no new release-path type/lint defects; remaining debt explicitly assessed for startup/auth/finance impact. | 1–3 days; load thresholds require owner agreement, not invented retrospective PASS. Security dependency advisories need an approved current source/update step if network access is needed. |
| A1: auth boundary / parallel release blocker | Separate minimal application-fix approval; fresh QA if rendered retest needed. Does not wait for C1–C3. | Auth-local empty-input boundary correction only; keep existing 8.56:1 focus fixes and all auth behavior. No new R6. | [Consolidated A1 criteria](../qa/seller-experience/wp7b-consolidated-accessibility-backlog.md): essential border ≥3:1 in exact empty states, affected error/focus/disabled states, focused auth regressions and actual browser evidence. | 0.5–1 day plus independent retest; risk: global theme spillover. |
| A2–A5: accessibility evidence / parallel | Fresh bounded QA authority, human listening slot, reliable exact-window/native-zoom control. Prepare from existing evidence before opening session. | One grouped speech batch, four-screen native zoom sweep, conditional contrast/targets and cause-level legacy reconciliation. No automatic app fixes; no repeat of already sufficient login speech. | All 40 original IDs retained and sufficiently disposed, no blocking defect. Actual speech, native zoom proof, visible focus and pixel/state measurements; no axe/DOM-only speech claim. If environment blocks a row, retain NOT_VERIFIED and close session safely. | 1–3 preparation/review days plus approximately 15–20 minutes grouped human listening; native zoom may need a separate concise operator step. Not a guarantee that all checks fit one session. |
| C4: WP7C integration decision / after C1–C3 | Changed-path closure and approved release contract; accessibility remains a separately visible gate. | Evidence consolidation and bounded whole-release regression once, after changes stabilize. No new feature discovery sprint under this label. | Included critical seller journeys, security/data invariants, current Electron smoke, Angular/backend/QA, build/static/migration evidence; clear inherited vs new counts. Cleanup and provenance verified. Gate B must separately pass before full application release classification. | 1–2 days; missing evidence is BLOCKED, not inherited PASS. |
| R: PC-first recovery / parked, separate activation prerequisite | Explicit owner resumption; exact disposable target, tooling/key/destination approval. Not automatically part of C2. | Resume existing encrypted backup/independent restore work only. No permanent initialization or production restore. | Full actual encrypted rehearsal, database/media/financial precision/source preservation, wrong-key/corruption, recovery and independently verified destination. Tool install/key custody/task scheduling require their own authority. | Unknown until existing blocker is revalidated. Risk: assuming a folder on same disk is independent. No runtime PASS without actual rehearsal. |
| W8: proposed WP8 release candidate / later | C4 local application decision, A closure, recovery prerequisite as applicable; explicit WP8 scope approval. | PC-first/package configuration, secure install/update, deployment rollback, monitoring, owner onboarding and runbook qualification. No real deployment/credentials/data promotion by default. | Exact release artifact hash, packaged startup/deep links/media/session controls, migration rehearsal, safe rollback and recovery, alert visibility, owner runbook acceptance. Local release qualification distinct from real-business activation. | Estimate after D0/C4; packaged/runtime gaps may differ from Chrome. |
| E: authorized real-provider qualification / external lane | Genuine seller accounts, eligibility, official API contract verification and narrowly scoped credentials/consent. | Separate provider-specific work orders: registration → API entitlement → contract → supported sandbox → approved live read-only. External writes are a further gate. | Evidence from the actual authorized environment, quotas/errors/revocation/replay/provenance; UNVERIFIED for unavailable provider contracts. No fake transport promoted to certification. | External lead time unknown. No provider action authorized now. |
| U: seller usability polish / after critical integrity | Prioritized observed friction, not a redesign mandate. | Propose economics anchors/summary, consistent labels and cost/evidence hierarchy; validate with seller task success before bigger changes. Existing dense-page/currency recommendations reconciled by stable ID. | Task completion, correct context, keyboard/mobile and no misleading estimates; no altered formulas, new rankings or automatic decisions. | 1–2 days per approved small batch; larger flow redesign needs separate specification. |

Estimates are planning ranges for bounded engineering effort, not delivery dates
or commitments to resolve unknown/external causes. A newly confirmed security or
data-integrity issue interrupts lower-priority work; otherwise accessibility and
C tasks progress independently toward the same release decision.

## Rollback and authorization per lane

| Lane | Rollback / failure containment | Exact authority required before execution |
| --- | --- | --- |
| D0 | Revise proposed scope; retain earlier contract and evidence. No runtime effect. | Owner acceptance of release inclusion/exclusions and accounting role. Planning alone does not accept risk. |
| C1–C4 | Small reviewable patches, retain user's unrelated work; reverse only package-owned changes with a targeted patch, never hard reset. Stop isolated runtimes through their normal controls. No permanent schema/data to roll back. Unexpected migration/financial-architecture need stops implementation for a separate decision. | Approved proposed WP7C contract; dedicated QA instance/role/loopback and fresh allowed naming/token lifecycle; explicit scope for synthetic DB creation/cleanup and owned process controls. Normal dev processes cannot be paused without separate permission. |
| A1 | Revert only auth-local boundary patch if regression; preserve R4/R5 valid focus changes. Do not ship a known failed field state as closure. | Explicit login-border fix approval and affected auth tests; fresh disposable rendered test authority. |
| A2–A5 | Stop input if exact QA window uncertain; save partial evidence, retire session and verify cleanup. No inferred manual result. | Fresh QA session/database lifecycle authority and consenting human observer; no old R5 token reuse. |
| R / W8 | Retain previous release/config and encrypted backup; restore rehearsal must target a separate marked environment. No permanent migration/restore without exact later authorization. | Explicit backup resumption, key/destination/tool approval, then separate packaging/activation scope. No scheduled task registration or real-data activation inferred. |
| E | Revoke unused authorization/credentials through approved canonical workflow; preserve audit; never retry an unknown write blindly. | Separate exact provider/environment/operation/budget/time approval, official contract and HUMAN source/execution requirements. Live read-only authority does not authorize writes. |

## Proposed next authorization, not exercised

Recommended next implementation package: **C1, the bounded WP7C residual
integrity/security batch**, after D0 decisions. In parallel, approve A1 as a
separate small fix and schedule A2–A5 once; do not use accessibility uncertainty
to restart the entire product QA loop.

Suggested owner authorization must explicitly state all of the following:

1. Approve the proposed WP7C scope C1–C4, or approve C1 only with a stop after its
   report. Recommended first authorization is **C1 only**.
2. Choose the first release's included seller workflows/runtime and whether
   Finance is a disclosed estimate/projection tool with separate accounting.
   Sole-accounting use remains prohibited without an approved solution. Keep
   Action Center advisory unless a separate workflow design is approved.
3. Authorize fresh marker-protected synthetic databases only on the dedicated
   `vayujit-qa-postgres` instance `389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`,
   `127.0.0.1:55432`, non-superuser `vayujit_qa_admin`, naming
   `vayujit_qa<16-hex>_test`, using signed instance/owner/token/marker/OID lifecycle
   guards and normal cleanup. Every run requires current preflight/expiry;
   no blanket tombstone recovery or permission derived from a connection string.
4. Permit only C1-owned app/QA processes; either keep dev services untouched in
   an isolated source/runtime arrangement or separately approve an exact normal
   API/frontend pause/restore window. No such pause is authorized now.
5. Permit focused test additions and at most three demonstrated low-risk C1
   root-cause fixes under existing authorities. Stop for schema/permanent-data,
   accounting architecture, new capabilities or broader authority changes.
6. Separately say **“Approve A1 auth-local login boundary remediation and
   independent retesting”** if desired; C1 permission alone does not include it.
   Human observation availability and a fresh A2–A5 session need explicit scope.

Neither proposed authorization includes real provider calls, supplier contact,
marketplace writes, procurement, payment, production initialization, unrelated
Docker cleanup, branches, commits, pushes, WP8 implementation or backup resumption.

## Preventing another open-ended loop

- One cause register, one 40-ID accessibility crosswalk, one release gate ledger.
  Occurrence counts and viewport samples are not extra defects or whole journeys.
- Freeze acceptance before a batch. Do not add mandatory checks without their
  criterion/source and an explicit scope decision.
- Reuse adequate unchanged-source evidence; rerun affected paths, not every
  historical suite after each observation. Run the consolidated matrix once at C4.
- Cap each implementation batch; new scope becomes a decision record, not an
  automatic next R-package. Every active QA session has an expiry and verified exit.
- Missing manual/live/backup evidence remains an honest separate gate; successful
  local functional work still counts as progress without pretending launch PASS.

Current output is four planning documents. No WP7C, WP8, application correction,
new DB lifecycle operation or full suite execution has started.
