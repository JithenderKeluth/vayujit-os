# WP7B consolidated accessibility backlog and R5 closure

Assessment date: 2026-11-06. Planning/documentation only. This is an index and
forward plan, not another remediation cycle, new execution authorization, or a
replacement for historical evidence.

## Decision and preserved baseline

- **Gate A: PASS**, inherited from WP7B-R1; not rerun here.
- **Gate B: NOT PASSED**. The retained machine gate says `FAIL`, not merely a
  missing-evidence result, because an essential empty field boundary fails.
- **WP7B: INCOMPLETE**. Application certification remains INCOMPLETE.
- Campaign focus: corrected from 2.37:1 to **8.56:1**; authenticated R5 retest
  24 PASS/0 FAIL. Login focus: corrected to **8.56:1** in R4. Do not reopen either
  demonstrated correction solely because other matrix rows are incomplete.
- Empty enabled, unfocused login Email boundary: **2.09:1**, required 3:1 in the
  demonstrated state. `WP7B-R5-EMPTY-FIELD-BOUNDARY-001`, P2, remains a confirmed
  release blocker. **No correction authorized or implemented in this task.**
- Original matrix: **40 groups: 9 VERIFIED_PASS, 1 VERIFIED_FAIL,
  30 NOT_VERIFIED; 17 have partial coverage; no NOT_APPLICABLE dispositions**.
  Partial is an overlapping evidence attribute, not an additional group count.

Sources: [R5 gate](wp7b-r5-gate.json), [R5 matrix](wp7b-r5-accessibility-matrix.md),
[R5 results](wp7b-r5-automated-results.md), [R5 risk update](wp7b-r5-risk-update.md),
[R2 original checklist](wp7b-r2-manual-checklist.md). Their acceptance criteria,
expected behavior, original source references and historical verdicts remain
authoritative; this document does not shorten or silently waive them.

## R5 execution safely closed

The R5 session was still active when this request began. At 03:12 UTC its
pre-existing authorization had not expired (expiry 03:24:34.779 UTC). Only the
existing allowlisted `done` control was sent, through
`tmp/qa-wp7br5/manual-requests.json`. The already-running controller closed its
owned browser and invoked its existing signed cleanup path. **No new lifecycle
authority, direct DROP, recovery, permanent data operation or new QA run was used.**

| Check | Actual evidence and result |
| --- | --- |
| Exact R5 target | Token `c110d6b49e2648a3`; database `vayujit_qac110d6b49e2648a3_test`; approved instance `389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`, loopback `127.0.0.1:55432`, QA role `vayujit_qa_admin`. |
| Normal completion | `tmp/qa-wp7br5/session-control.json`: ended `2026-11-06T03:13:09.799Z`, runtime exit 0, child exit 0, CLEANED, marker verified, database absent, signed lifecycle. `tmp/qa-seller-browser/c110d6b49e2648a3/session-final.json` agrees. Verification remained incomplete, not falsely passed. |
| Independent database read | Existing `QaInstance.verify_server()` and signature-checked `load(token)`, then parameterized `pg_database` count: absent; signed state DROPPED; zero lifecycle operations during this independent check. |
| Owned processes | Exact launcher/controller/runtime/watcher PIDs 31620/37708/41356/28848 absent; no R5 token/script-matched process after excluding the diagnostic command itself; no listener at port 63247. No unrelated process was stopped. |
| Normal development | Seven captured API-tree identities unchanged. Normal frontend was already absent at prelaunch and was not stopped, started or reconfigured. No live normal-app endpoint was invoked to manufacture a health claim. |
| Docker preservation | Fresh comparison of prelaunch/current instance, container identities, images, states, start/finish times, mounts and networks matches after canonicalizing unordered inventories. No actual resource change found. |
| Watcher discrepancy | Raw `final-cleanup-audit.json` remains INCOMPLETE: DB absence and API-tree checks passed, ordered Docker comparison failed. Independent comparison demonstrates only the order of five identical QA-container mount entries changed. The running watcher retained its older order-sensitive comparator. Its receipt is preserved, not overwritten or represented as PASS. This does **not** resolve the separate historical PostgreSQL timestamp discrepancy or an earlier unmatched snapshot. |
| Evidence | 36 pre-R5 preserved reports checked: zero SHA-256 mismatches. 25 retained ZIP trace archives checked: zero invalid archives. All eight R5 reports retained. Post-cleanup preservation set: 510 files, aggregate SHA-256 `4842ea9e3c7511fc72e4d143819a17b25a94e60a54ee169d8a1829f9b3002df8`. |

The preservation set comprises all regular files under `tmp/qa-wp7br5` and
`tmp/qa-seller-browser/c110d6b49e2648a3`, plus the eight R5 documents. Relative
path/SHA-256 pairs are sorted with Node `localeCompare`, JSON encoded, then hashed.
No symlink/nonregular entry is accepted. The existing R5 watcher finalized its
reports during normal cleanup; the fingerprint starts **after** that finalization.
The old assessment's active-session wording is historical, superseded by the
closure receipts above. Its original text is not rewritten.

**R5 cleanup: independently VERIFIED.** All R5-owned synthetic databases (one
session target) are absent and QA processes stopped. No authorization remains
available to launch a replacement session. Narrator is not an R5-owned process
and was not terminated. Backup certification remains parked.

## Cause-level tasks, not repeated whole-application cycles

| Task | Type / priority | Bounded work and objective closure | Authorization / stop condition |
| --- | --- | --- | --- |
| A1: essential auth field boundary | Confirmed defect / release blocker P2 | Inspect the existing auth-local styling; change only the necessary boundary token, retaining focus/error/disabled states. Test empty enabled Email at Chrome/Edge 1440/390: rendered essential boundary at least 3:1 against actual adjacent colors, keyboard focus still visible, no auth semantics change. Check password/other affected auth states; regressions and independent browser retest required. Four failing samples are one cause, not four fixes. | Separate application-change authorization plus fresh guarded synthetic QA authority. Do not alter global theme without demonstrated need. |
| A2: remaining spoken behavior | Evidence gap / release gate | One grouped human-assisted session covering remaining SR-02–13 with actual utterances, browser/reader versions, action and verdict per row. Retain prior login speech without asking the owner to repeat adequate observations. Resolve SR-01 provenance explicitly; do not promote it from availability alone. | Fresh isolated QA authorization and human listener appointment; no speech inference from DOM/axe. Stop if exact QA window cannot be identified. |
| A3: native zoom/reflow | Evidence gap / release gate | Four screens, three actual native settings each; capture browser menu percentage, window/viewport, reflow, focus, errors and modal keyboard behavior. One screen/settings sweep maps to all 12 Z rows. Existing percentage screenshots can be reused only for their demonstrated assertions. | Fresh QA authority; reliable zoom proof or human operator. CSS scaling, emulated DPR and a screenshot alone cannot close the interaction requirement. |
| A4: conditional contrast/focus | Evidence/applicability gap / release gate | C09/C11/C13: expose exact Ads states, focused controls and transitions, align pixels/computed state/time, apply correct criterion and threshold. Preserve indeterminate temporal samples; adjudicate, do not call them confirmed low-contrast defects. | Fresh QA authority. New demonstrated defect needs separate bounded implementation authority. No universal 3px native-focus requirement. |
| A5: targets and legacy reconciliation | Evidence/applicability gap / release gate | C14/C15: review target spacing/exceptions and map legacy occurrences to stable causes, existing fixes or justified non-applicability. Each original key has a disposition and evidence link; no blanket closure of 3,169 records. | Read-only analysis possible now; interactive gaps require fresh QA authority. Do not delete difficult nodes or suppress rules. |

Normal text contrast uses its applicable 4.5:1 threshold (3:1 for qualifying large
text); essential non-text indicators use applicable 3:1 comparisons. Focus
visibility, target geometry and exceptions are separate acceptance questions.
Decorative borders do not automatically require 3:1; the demonstrated empty
Email field has no internal value, placeholder, icon or other delineation.

## Preserved 40-group crosswalk

The following is the complete stable-ID crosswalk. Detailed criteria and original
expected assertions remain in the linked R2 checklist and R5 JSON; task grouping
does not remove any requirement. PASS below means retained evidence only, not a
new test in this planning task. NV means NOT_VERIFIED; F means VERIFIED_FAIL.

| Original ID | Original area / setting | Retained verdict | Next task or retained evidence |
| --- | --- | --- | --- |
| R2-SR-01 | Sign-in labels | NV, partial | A2: retain supplied login speech; reconcile provenance, no gratuitous repetition. |
| R2-SR-02 | Navigation, landmarks, headings | NV | A2 |
| R2-SR-03 | Goal disclosure | NV | A2 |
| R2-SR-04 | Goal fields/help/required state | NV | A2 |
| R2-SR-05 | Form errors/recovery | NV, partial | A2: retain login subset, complete remaining goal behavior. |
| R2-SR-06 | Marketplace import controls | NV | A2: identify controls, do not execute import. |
| R2-SR-07 | Meesho editor | NV | A2: actual groups/buttons, no invented tablist. |
| R2-SR-08 | Ads dialog entry | NV | A2 |
| R2-SR-09 | Ads containment/dismissal/return | NV | A2 |
| R2-SR-10 | Dynamic loading/status/retry | NV | A2 |
| R2-SR-11 | Review/HUMAN prerequisites | NV | A2: no approval activation. |
| R2-SR-12 | Research/selection/context | NV | A2: read synthetic/UNKNOWN context, no selection action. |
| R2-SR-13 | Table/list relationships | NV | A2 |
| R2-Z-01 | Goals 100% | NV | A3 |
| R2-Z-02 | Goals 200% | NV | A3 |
| R2-Z-03 | Goals 400% | NV | A3 |
| R2-Z-04 | Imports 100% | NV | A3 |
| R2-Z-05 | Imports 200% | NV | A3 |
| R2-Z-06 | Imports 400% | NV | A3 |
| R2-Z-07 | Meesho 100% | NV | A3 |
| R2-Z-08 | Meesho 200% | NV | A3 |
| R2-Z-09 | Meesho 400% | NV | A3 |
| R2-Z-10 | Ads 100% | NV | A3 |
| R2-Z-11 | Ads 200% | NV | A3 |
| R2-Z-12 | Ads 400% | NV | A3 |
| R2-C-01 | Social image-review textarea | PASS | Retain R5 matrix evidence. |
| R2-C-02 | Social timeline strong text | PASS | Retain R5 matrix evidence. |
| R2-C-03 | Flipkart labels/forms | PASS | Retain R5 matrix evidence. |
| R2-C-04 | Flipkart remaining buttons | PASS | Retain R5 matrix evidence. |
| R2-C-05 | Meesho remaining buttons | PASS | Retain R5 matrix evidence. |
| R2-C-06 | Mobile Meesho/goal fields | PASS | Retain R5 matrix evidence. |
| R2-C-07 | Financial captions | PASS | Retain actual text measurement, not oversized box. |
| R2-C-08 | Financial headers | PASS | Retain R5 matrix evidence. |
| R2-C-09 | Ads obscured heading/state | NV | A4 |
| R2-C-10 | Campaign reschedule textarea | PASS | Retain text evidence; R5 focus repair also retained. |
| R2-C-11 | Remaining interactive focus | NV, partial | A4; resolved login/Campaign causes are not all-app closure. |
| R2-C-12 | Essential boundaries/state indicators | F | A1; keep broader applicability evidence. |
| R2-C-13 | Transition/hover/selected contrast | NV | A4 |
| R2-C-14 | Target size/spacing/exceptions | NV | A5 |
| R2-C-15 | Legacy target reconciliation | NV | A5 |

Deduplication rules: reuse valid evidence for unchanged source/state; one cause
may close several occurrence records only through explicit mapping. The 3,169
legacy keys (2,774 manual-required, 395 historical-violation classifications) are
not 3,169 current defects. R5 Ads attempts with indeterminate exposure/temporal
checks remain retained failures/unknowns, not fabricated PASS. No new Narrator
utterance or R5 native zoom verification was obtained. Zero axe violations cannot
substitute for these manual gates.

## Finite exit and escalation

Authorize A1 separately; schedule A2–A5 as one prepared evidence batch, not another
broad R6. Each row ends PASS, demonstrated FAIL, NOT_VERIFIED with exact blocker,
or justified NOT_APPLICABLE. Any new cause goes to a separate scoped decision;
do not automatically repeat all suites. Gate B passes only when all required
rows have sufficient evidence and no blocking defect remains. WP7C planning or
authorized independent functional work may proceed in parallel; release cannot
waive this gate. See the [execution plan](../../roadmap/vayujit-forward-execution-plan.md).

No application tests were rerun here. New checks were cleanup, process/resource
comparison, evidence integrity and documentation validation only. Historical
WP7A provenance, Ads 502, PostgreSQL timestamp attribution, financial-history,
provider and parked recovery limitations remain unchanged.
