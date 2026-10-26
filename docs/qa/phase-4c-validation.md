# Phase 4C — consolidated certification and launch-readiness audit

**Application certification: INCOMPLETE. First real operation: NO-GO.**

This is a completed bounded audit, not production implementation, a finding waiver,
or permission to initialize the permanent seller database. Passing application
tests cannot satisfy the missing encrypted backup, independent restore and physical
backup-destination requirements. No owner risk acceptance is inferred.

## Decision and evidence

| Area | Verdict | Supporting evidence and limit |
| --- | --- | --- |
| Application QA | INCOMPLETE | [Current checks and source proofs](phase-4c-certification.json), [12 open findings](phase-4c-findings.md), [route reconciliation](phase-4c-route-control-coverage.md). Bounded passes do not demonstrate complete application coverage. |
| Accessibility | INCOMPLETE | [Current full-document/targeted results](phase-4c-accessibility.json): 34 scans, zero recorded violations, eight incomplete rule/state occurrences; two targeted caption checks pass. [4A evidence](phase-4a-accessibility.json) and the manual item remain. No WCAG conformance claim. |
| Financial safety | INCOMPLETE | Current focused persisted tests and earlier independent Decimal/freshness/provenance evidence pass only modeled synthetic subflows. Real taxes/fees/costs/settlements are not established; exact operational historical reconstruction remains missing. |
| Inventory/order readiness | INCOMPLETE | [4B opening-stock closure](phase-4b-resolution.json) and current Phase 3 API matrix. Local conservation/replay/races work in tested cases; real order imports/fulfillment and full interruption recovery are not certified. |
| PC-first operational readiness | INCOMPLETE | [Runtime-only record](../seller-os/pc-first-disposable-certification.json), [backup guide](../seller-os/pc-first-backup-recovery.md). No successful encrypted independent restore/physical destination proof. |
| Marketplace readiness | NOT CONFIGURED | [Activation plan](../seller-os/production-activation-plan.md) and registration checklists. No evidence of real Amazon India/Flipkart seller registration and distinct API authorization. Fixture accounts are not real registrations. |
| Overall first-real-operation readiness | **NO-GO** | Mandatory recovery/safety gates remain unmet. Local synthetic success is not operational authorization. |

The machine-readable [certification record](phase-4c-certification.json) contains
actual counts, verdicts, exact evidence paths, preserved source/report hashes,
unexecuted gates and cleanup. The [seller-journey matrix](phase-4c-journeys.md)
assesses all thirteen required journeys separately.

## Evidence reconciliation: history is not a current failure count

| Phase | Preserved historical result | Subsequent disposition / baseline used here |
| --- | --- | --- |
| 1 | 6 browser passed / 2 failed; contrast and landmark findings | Phase 2 remediation; latest 4B baseline smoke 8 passed. Original report remains unchanged. |
| 2 | API 20 passed / 2 failed; browser 2 passed / 6 failed | Acquisition-lineage freshness, supplier-scoped HUMAN replay and semantics remediated. Latest baseline API 22 and browser 8 passed; original financial expectations retained. |
| 3 | API 24 passed / 12 failed; browser 10 passed / 2 failed | Seven correctness/filter roots, overlapping repeated installation failures; not fourteen independent defects. |
| 3A | Five bounded roots repaired; API 34 passed / 2 failed; browser 10 passed / 2 failed | Synthetic fallback provenance and resolved filter remained open until 3B. |
| 3B | API 36 and browser 18 passed; targeted 37 passed | Seven roots plus current-page navigation independently revalidated; historical projection/generic execution/opening-stock gaps and UX/manual review retained. |
| 4 | Browser 36 passed / 8 failed; API 36 passed | Broad route/axe exploration exposed area/rule buckets, not eight independent roots. Original evidence preserved. |
| 4A | Original browser 44 and focused 6 passed; 322 axe scans, zero violations, 84 targeted passes | 115 stable records resolved, not 115 distinct code bugs; 14 records remained open. Original caption/header targets verified, other full-document incompletes retained. |
| 4B | Backend 81; opening browser 16; existing browser 44/18/8/8; Angular 267; QA self-tests 77 | Two stock records closed. 129 active baseline records: 117 resolved, **12 open**. 26 axe scans, zero violations, six targeted passes; stock numeric-cell manual review remains. |
| 4C | Separate current execution and quality records | No production correction, finding closure or acceptance. Named new route/context checks supplement, not replace, earlier proofs. |

These are suite executions, often duplicated across viewports and phases. They are
**not summed as unique business requirements**. The 81-case 4B batch and full earlier
browser matrices were reviewed/reused, not all rerun in this audit. Exact 4B source
hashes are checked against current files. Earlier fixture/cleanup timeouts remain
in historical reports; later normal cleanup does not erase those events.

The active backlog is unchanged. Eleven historical already-resolved records that
old report generators reintroduced remain explicitly archived in
[4B historical reconciliation](phase-4b-historical-records.json). Some older report
fields count all inherited records as “open”, and the original source coverage
table still starts at 154 routes. Those are reporting debt, not a current recurrence.
Use the 4C reconciliation and 4B ledger, not an unqualified old report counter.

## Current execution and boundaries

| Executed in 4C | Actual final result | Evidence |
| --- | --- | --- |
| Authenticated Chrome audit, desktop 1440×1000 / mobile 390×844 | **8 passed; 0 failed/skipped** | Four scenarios per independent installation; `8644b989a75faaef` / `c84e3310c5656b03` |
| Persisted Phase 3 HTTP/API matrix | **36 passed; 0 failed/errors/skipped** | 18 in each final browser installation; existing assertions retained |
| Focused landed-cost / unit-economics / decision-readiness / HUMAN workflow | **11 passed; 0 failed/errors/skipped** | `tmp/qa-agent/5275b9c72e4a4473/backend-results.xml`; 21 existing framework warnings; 202.51s |
| QA self-tests | **49 Node + 28 Python = 77 passed** | Current quality logs; negative reporter fixture prints an intentional failure line, but the suite passes |
| Full Angular | **267 passed, 71 files** | Current quality `angular.log`; no production changes |
| Production build | PASS with existing warning | Current browser runner builds source first; initial 517.89 kB vs 500 kB advisory budget |
| Current axe | **34 full-document scans, 0 violations; 8 incompletes** | Two targeted inventory-caption checks: actual contrast PASS, no targeted violation/incomplete |
| JS/TS quality | PASS | QA ESLint/Prettier; app/spec TypeScript; web ESLint 0 errors / 2 existing OnInit warnings |
| Python quality | PASS, focused | Ruff; Black 18 QA files; compileall; configured strict mypy for new read-only verifier (one file). Not whole-repository typing certification |
| Preservation | **794 hashes unchanged** | Production sources and prior QA reports; all 19 checked 4B source hashes still match |
| Cleanup | **5 exact task-owned databases absent** | [Independent read-only metadata proof](phase-4c-cleanup-verification.json), includes both initially blocked installations and final browser/backend installations; final children exit 0 |
| Git whitespace | PASS | Normal `git diff --check`; existing CRLF-conversion notices are not whitespace failures |

The initial blocked setup also ran its 18-case API matrix twice successfully, but
those repeated checks are **not added** to the final 36 or counted as more unique
requirements. The 11 focused cases overlap earlier phases and are not eleven new
business capabilities.

Run-specific results, including any actual failure, are in
[execution JSON](phase-4c-execution.json), [quality commands/exit codes/logs](phase-4c-quality.json)
and [certification JSON](phase-4c-certification.json). Browser screenshots and
sanitized network/console artifacts are linked per scenario under ignored
`tmp/qa-agent`. The report does not infer browser success from API/unit tests.

The audit reuses the existing production build, isolated local Chrome, Phase 3
canonical API setup, marker-protected PostgreSQL lifecycle, reverse proxy and
unchanged default-deny browser/network policy. New artifacts are an owned local
draft Campaign and uploaded synthetic private PNG, created through normal APIs.
Settings use real supported section names, not fake UUIDs. No approval is seeded
to unlock an unavailable route. The application is not changed.

An initial setup attempt correctly failed its own draft contract assertion:
generic `POST /api/v1/marketplaces/listings` calls the deterministic fake connector
and persists `active` plus a fake remote ID. That operation is **not** the channel-
specific local draft API. Two synthetic fake-adapter records were created, then
removed with their disposable databases; no external request occurred. They are
not called live evidence, local draft success or publication. The failed attempt
and both normal cleanup proofs are preserved in
[initial blocked execution](history/phase-4c-initial-fixture-contract-blocked.json).
The corrected audit does not call that endpoint or reuse those IDs. Channel draft
routes remain untested until legitimate approved-artifact/catalog mapping setup.

The first quality wrapper also selected `ng lint`, but the repository intentionally
uses an npm ESLint script, not an Angular lint target. Its actual command failure
is preserved in [initial quality record](history/phase-4c-initial-quality-command-error.json).
The corrected wrapper invokes the existing ESLint configuration; no package,
production behavior or lint threshold was changed. Initial audit-only lint defects
(undefined Node globals and a long Python string) were corrected, not suppressed.

## Route and control reconciliation

Current AST inventory: **155 declarations**, adding only the authenticated
`/marketplaces/inventory/opening` route to the earlier 154. Redirects/guest flows
are not counted as populated business pages. See every declaration and every one
of the original **26 artifact-dependent routes** in the
[route/control matrix](phase-4c-route-control-coverage.md) and its JSON.

Six artifact declarations are targeted with canonical disposable context:
four Campaign routes, Media detail and Settings section. Exact outcomes depend on
the recorded scenario assertions, not merely route matching. Remaining routes are
investigated against their component/API contracts and explicitly NOT EXECUTED
when an owned artifact, worker heartbeat or approved version was not prepared.
Safe draft SocialPost, mock-destination, workflow and portfolio fixtures remain
feasible follow-up work, not technical impossibilities or silently covered pages.

Source review also finds that Trends resolves the current journey rather than
consuming `contextId`, Ads account detail maps to the accounts section, and Campaign
Video consumes the campaign ID but not the declared activity ID.
These are **suspected context-contract gaps requiring two-distinct-context tests**,
not new confirmed failures or permission to fix production. Rendering a shared
heading would not certify correct deep-link identity. No valid context is invented
and no unvisited page is labelled unreachable merely for lack of a fixture.

DOM control occurrences include repeated sidebar/header controls. They do not
measure unique requirements, activated controls, hidden dialogs or workflow
completion. Only named actions/assertions in actual tests have execution evidence.
No complete 155-route or backend-to-UI capability certification is claimed.

## Financial and operational safety audit

| Boundary | Demonstrated evidence | Remaining limit |
| --- | --- | --- |
| Financial lineage/freshness | Phase 2 readiness → landed → unit lineage, material change blocks old READY; original immutable commercial snapshots retained; current focused economics tests | All material real-world inputs/category taxes/FX/evidence-aging combinations not tested. Operational current projections remain mutable. |
| UNKNOWN vs zero | Latest UNKNOWN cost revision blocks old known values; explicit known zero retained; absent fee/refund/settlement stays UNKNOWN | Not a real fee/GST schedule certification; no tax advice implied. |
| Synthetic vs real | Phase 3B fallback propagates synthetic ancestry; unrecognized/missing provenance stays UNKNOWN; UI labels tested | Canonical fake adapters do not prove genuine external data; live imports not performed. |
| Stock ledger integrity | 4B opening movement/audit atomicity, immutable reviewed intent; Phase 3 reserve/release/consume/conservation | Full SKU/location/counting practice and production concurrency load are not established. |
| Replay/concurrency | Unchanged replay stable; changed stock/financial/HUMAN intent 409; concurrent final-unit and duplicate delivery/decision cases | Not every endpoint/race/connection interruption is covered. |
| HUMAN authority/auth/audit | Normal one-owner auth, anonymous denial, foreign IDs, AI impersonation rejection; explicit selection/review authorities retained | One owner per database; no second-owner shared-database test or SaaS claim. Full attack matrix not rerun. |
| Interruption recovery | Lost HTTP reply after real local commit, same-key retry, refresh/new tab/fresh process | Not encrypted independent restore, OS reboot, disk loss or publishing-worker recovery. |
| External safety | QA origin/mutation guards, LOCAL_FIXTURE, credential-free disabled sandbox accounts, emergency stops and egress guard | Test-process guards are not host/firewall certification. No real acquisition, authorization, dispatch or publication tested. |

Historical `QA-P3-GAP-001` mentions absent cost IDs; current code now records
`cost_evidence_ids` and `unknown_cost_evidence_ids`. This narrower improvement does
not supply immutable operational projection history. Preserve the original finding
and require explicit scope/acceptance or a separately authorized history design.
`QA-P3-GAP-002` similarly retains its original response wording, while the current
response truthfully states no approval/execution was recorded. The missing generic
durable action lifecycle is still absent; neither record is silently closed.

## Accessibility and seller usability

Review current rule IDs/impacts/targets and incompletes in
[exact accessibility evidence](phase-4c-accessibility.json). Current checks use the
existing axe engine and unchanged full-document rules. Settings links and Currency
exercise focus, Tab/Shift+Tab; private media is authenticated and survives reload;
inventory caption is scrolled/focused for targeted contrast inspection. Campaign,
settings, catalog and media screenshots retain actual desktop/mobile UI evidence.

The eight current full-document incompletes repeat four rule/state combinations
across the two viewports: Accounts `aria-prohibited-attr` on the Read-only imports
action group; Video `aria-prohibited-attr` on summary/actions; Video `color-contrast`
on offscreen/conditional textarea/metric cells; Product create `color-contrast` on
the two description textareas. Exact selectors and engine diagnostics remain in
the JSON. They are review requirements, not newly proven violations. Current
accounts GET returned 200 in both audit contexts, not a root-cause fix for the
historical 502. Captured warning-screen widths are observations, not overflow
finding closures. Product creation again displays USD in both contexts.

Visual review actually opened the current desktop/mobile Campaign screenshots
and the mobile pricing screenshot: the draft title/actions wrap in the 390px
viewport and Currency retains a visible focus outline with USD selected. This
does not certify offscreen controls, every page width or every state. Screenshot
paths are attached to the corresponding current browser records.

The original **85 incomplete rule/state occurrences are not 85 confirmed defects**.
The stock numeric cell and unreviewed calendar/conditional ARIA/empty-table cases
remain manual work. Exact 4A caption/header passes cannot close unrelated nodes.
Screen-reader reading order, all modal traps/restoration, zoom/high-contrast/theme,
physical mobile devices and all conditional states are not certified. No axe rule
or node was removed to make a report green. Do not infer full WCAG from zero
violations in a subset.

All eight open UX occurrences are classified individually in the 12-finding matrix:
two currency defaults; two long-economics occurrences; pre-run guidance; two
desktop overflows; long research pages. Owner acceptance is **not recorded**.
Potentially deferrable exclusions need explicit owner agreement and safe working
instructions. A history or generic-execution gap becomes launch-critical if that
unsupported capability is part of the initial business operation.

## PC-first operational gate and security risk

| Gate | State / evidence | Required exit evidence |
| --- | --- | --- |
| Disposable deployment/runtime | Historical bounded PASS, not rerun here | Retain production-like proxy/isolation/persistence record; no permanent initialization implied. |
| Encrypted DB + media backup | NOT CERTIFIED; checked-in record says NOT_RUN; later owner reports fail | Actual stage-specific successful artifact/encryption/integrity report, not a generic subprocess exit. |
| Independent restore | NOT CERTIFIED | Separately marked target restore, records/Decimal/media comparison, wrong-key/corrupt-ciphertext rejection, source unchanged, timed recovery. |
| Physical backup destination | UNVERIFIED | Host/Docker data-disk relationship and different physical destination witnessed; different folder/partition is not off-device protection. |
| Key custody/schedule | Pending HUMAN-controlled verification | Owner/SYSTEM-only key ACL, offline recovery copy, approved retention/schedule and failure visibility. No task registered here. |
| Host/security/dependencies | INCOMPLETE | Owner Windows/BitLocker/firewall/Docker/secret-custody review, current dependency advisory review and migration-backed validation. |
| Marketplace accounts/API | NOT CONFIGURED / externally pending | Separate registration, verification/category eligibility, API entitlement, credentials, official-contract check and authorized read-only certification. |
| External mutations | Intentionally DENIED | Separate canonical HUMAN approvals only after all applicable gates; not required to turn switches on for local QA. |

The checked-in older guide says Node/Python/Docker were unavailable in its shell.
This audit's approved environment runs Node, Python and Chrome and locates Docker;
it does not reuse that historical environment diagnosis as current fact. `age` and
`age-keygen` were not resolved by this shell's PATH probe; that does not prove they
are absent from the owner's Windows environment. Docker daemon/backup/key tests
were deliberately not invoked, preserving the separate certification workstream.

Historical security evidence is scoped: PR-SOS-01.4 once reported 10 dependency
vulnerabilities; later PR-SOS-07 reported zero **production** npm vulnerabilities
after Angular updates. Neither is a current full dependency advisory result.
This audit does not contact a registry or mark repository-wide security green.
Existing schema mypy `Field(ne=0)` debt, duplicate OpenAPI operation ID, deprecated
startup handlers, two OnInit lint warnings and the **517.89 kB vs 500 kB** initial
bundle warning remain disclosed. Typing/tooling warnings are not automatically
runtime defects, but zero-delta adjustment semantics and API-client contract
generation need focused follow-up before claiming those boundaries safe. Do not
modify unrelated schema/video tables to manufacture a green report.

## Minimal prioritized launch-blocker plan

1. **P0 operational safety:** close the existing PC-first encrypted backup and
   independent restore gate in its own authorized workstream. Diagnose the child
   report failure; verify recovery of API/worker and source integrity. Attach a
   physically independent encrypted destination and witness key custody/recovery.
   Do not initialize the permanent business database yet.
2. **P1 intended-operation decision:** owner states whether initial use is only
   offline catalog/stock/modeling or real marketplace selling. Real selling remains
   blocked on genuine account/API onboarding and read-only certification. Never
   promote fixture accounts/orders/stock/financial events to business data.
3. **P1 evidence gaps:** complete relevant manual/assistive accessibility review,
   investigate the historical accounts 502 and suspected deep-link identity
   contracts; create legitimate fixtures for required remaining contexts. Fix only
   independently demonstrated defects under separate authorization.
4. **P1 financial scope:** owner decides whether a separately retained accounting
   ledger/current-estimate-only operation is acceptable. If immutable reconstruction
   or generic Action Center execution is required, those are blockers, not waivers.
5. **P2 bounded UX:** explicitly accept/exclude or authorize minimal improvements
   for each open recommendation. Confirm INR on every creation until currency
   preferences are legitimately changed. Preserve all evidence and HUMAN gates.
6. **Release review:** fresh deployment/migration/security review and owner signoff
   after required gates pass. This audit grants no acceptance or external authority.

## Exact Windows verification commands

From repository root with existing dependencies, local PostgreSQL and Chrome.
No production `.env` edit is required. Supply a dedicated loopback QA admin URL
targeting `postgres`, never the golden or permanent business database. Run browser
suites sequentially because build output is shared.

```powershell
$env:QA_DATABASE_ADMIN_URL = 'postgresql+psycopg://LOCAL_QA_USER:URL_ENCODED_PASSWORD@127.0.0.1:5432/postgres'
node qa/run.mjs --phase4c
node qa/phase4c-quality.mjs

$env:PYTHONPATH = 'apps/api;.'
$env:QA_ORIGIN = 'http://127.0.0.1:4200'
$env:QA_PHASE = '3'
$qaAuditToken = [guid]::NewGuid().ToString('N').Substring(0,16)
& .\apps\api\.venv\Scripts\python.exe qa/fixture_server.py --port 0 --token $qaAuditToken --output "tmp/qa-agent/$qaAuditToken" --pytest test_pr5b_landed_cost.py test_pr5c_unit_economics.py test_pr6a_decision_readiness.py test_pr6c_decision_workflow.py
& .\apps\api\.venv\Scripts\python.exe qa/verify-phase4c-cleanup.py "tmp/qa-agent/$qaAuditToken"
node qa/certify-phase4c.mjs "tmp/qa-agent/$qaAuditToken"
git diff --check
Remove-Item Env:QA_DATABASE_ADMIN_URL
```

Do not rerun the immutable baseline-capture command to replace evidence. Optional
broader existing regressions: `npm.cmd run qa:phase4b`, `npm.cmd run qa:phase4`,
`npm.cmd run qa:phase3 -- --preserve-inventory`, `npm.cmd run qa:phase2 -- --preserve-inventory`,
`npm.cmd run qa:smoke -- --retest --preserve-inventory`. These regenerate their own
reports; preserve history and reconcile the known legacy reporter debt explicitly.
They are not claimed all rerun in 4C.

Backup rehearsal belongs to the separate workstream, only after owner destination
and tool review: `scripts/test-pc-first-disposable.ps1` supports explicit
`-BackupDestination` and `-EvidencePath`. Consult the existing backup guide; no
permanent-init, scheduling, live credentials or marketplace activation command is
part of this audit.

## Files and safety

Changed only QA harness/configuration and new Phase 4C documentation/evidence:
`qa/run.mjs`, `qa/playwright.config.mjs`, new `phase4c-fixtures.mjs`,
`tests/phase4c.spec.mjs`, `capture-phase4c.mjs`, `phase4c-quality.mjs`,
`certify-phase4c.mjs`, `verify-phase4c-cleanup.py`, and `docs/qa/phase-4c-*` plus
explicitly preserved intermediate evidence under `docs/qa/history`.

The immutable baseline hashes current application sources and earlier QA reports.
No production source, migration, authority, ownership constraint, permanent/golden
data, backup script/runtime, Docker resource, external provider, branch, commit or
push is changed. Cleanup is exact-token/marker guarded; independent read-only
metadata proof is recorded separately. No full backup/restore PASS is claimed.
