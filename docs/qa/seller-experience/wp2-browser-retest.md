# WP2 — Real browser retest evidence

Date: 2026-10-29. **Bounded local WP2 replay passed; application INCOMPLETE.**

## Environment and execution boundary

Actual production-built Angular in installed Chrome, desktop1440×900 and mobile390×844
with touch/mobile emulation. Fresh UI owner and mobile UI login; real cookie-based API
authorization. No auth bypass. Disposable signed PostgreSQL17 instance
`389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`, container `vayujit-qa-postgres`,
127.0.0.1:55432, role `vayujit_qa_admin`, exact token-owned naming contract.
No connection string was taken as authorization. Credentials stayed in private QA
storage, outside production .env and generated documents.

Canonical API fixture preparation is explicit: two **manual synthetic** Kids product
identities, constraints and insufficient-evidence assessments/scores, an owned brand,
and a QUEUED Business Agent run with zero provider budget. No run start/acquisition.
The UI really created the goal/plan, compared, selected/rejected/reselected, converted
to Catalog and followed the supplier handoff. Fixture preparation is not claimed as
successful product research, demand verification, live category eligibility or source approval.

## Before / failed attempts / final replay

All roots are `tmp/qa-seller-browser/<token>/`; local evidence is ignored by Git.
Traces contain synthetic authentication/session data; do not publish unreviewed.

| Token | Actual outcome and retained evidence |
| --- | --- |
| d3ed32edeca09126 | Before: empty goals/opportunities, missing projection feedback, zero Catalog conversion controls; select→reject still appeared selected. Four PNGs, intact trace and wp2-before.json. Its case-sensitive completion-text flag is false because rendered eyebrow was uppercase; the screenshot/body explicitly show RESEARCH COMPLETE. Original flag preserved, not silently rewritten. |
| c6f7856d9beb99de | First replay stopped at comparison: QA guard denied score/rank POST. Five preceding checks passed, not a product comparison PASS. Narrow non-executing allowance added and tested. |
| 845a3f09608906d9 | Six passes, then an overly broad heading-count assertion failed (the page legitimately had two headings with the product name). Corrected to exact h1 identity; six research404 responses retained. |
| 91647b25bb684f44 | First full replay:21 passed. Accessible summary-group incomplete results led to the in-scope semantic-role correction. |
| 34876f223ae01225 | Unused preflight runtime, no browser findings. Normal cleanup failed; exact signed invalid tombstone recovered separately. |
| 376a1f099a552823 | Expanded replay:14 preceding checks passed, then injected503 revealed collapsed conversion form during retry. Fixed and independently rerun. |
| 8995d15e3cbdc76d | Expanded replay23 passed, including empty-opportunities and failure recovery;4 axe scans0 violations/0 incomplete. |
| **7cc1ce7878744301** | **Final build replay23 passed,0 failed**, after final goal query/history synchronization;12 PNGs, two finalized CRC-checked traces,4 axe scans0/0. |

Earlier test-tooling issues were not relabelled production defects: wrong fixture module
import, missing paginated fixture pages property, absent public lineage.id (replaced by
an independent persisted row-count assertion), changed child read-model setup in old
Angular tests and an incorrect local tooling working directory. Original business/UI
assertions were retained.

## Required journey matrix

| Journey | What actually ran | Result / boundary |
| --- | --- | --- |
| 1. New seller/no goals | Real owner setup; My Research empty; Opportunities not started | PASS, no research-complete claim |
| 2. Create goal | Short-goal negative; actual Kids/INR300000 goal; UI versioned plan | PASS; no guarantee of products/profit |
| 3. Find opportunity | Two persisted synthetic identities in the original goal's run-linked cohort | PASS for fixture review; **live discovery NOT EXECUTED** |
| 4. Research opportunity | Open exact detail; load all six saved research areas | PASS for saved evidence feedback; no provider research |
| 5. Insufficient evidence | Six genuine missing-projection404s, unknown score/evidence, next-workspace guidance | PASS; no fabricated result/score |
| 6. Compare alternatives | UI selected both exact alternatives; canonical rank response NOT_COMPARABLE | PASS for evidence/gap comparison; no invented ranking |
| 7. Select product | Explicit confirmation; persisted HUMAN decision with correct assessment | PASS |
| 8. Reject product | Cancel test writes nothing; confirmed reject clears selected projection | PASS |
| 9. Revisit decision | Reload rejected state; explicit reselection appends history; three retained decisions | PASS; prior history not overwritten |
| 10. Continue to Catalog | Brand selected; confirmation required; injected503; reload/retry; real conversion201, lineage and Catalog refresh | PASS; local draft only, price/cost UNKNOWN |
| 11. Continue to suppliers | Exact selected opportunity in supplier workspace, correct enabled LOCAL_FIXTURE CTA | PASS for handoff; no acquisition requested |
| 12. Reload/preserved state | Mobile saved goal→scoped opportunities; selected detail; alternative switch; Back/refresh; Catalog deep link | PASS for tested subset; not every journey independently repeated at every viewport |

Goal revision was tested as a new draft: original persisted raw goal remains unchanged.
No unsupported in-place editing success is claimed. Backend tests additionally cover
unrelated goal409, current-vs-stale assessment, replay conflicts, concurrent HUMAN
replay and concurrent one-product/one-lineage conversion.

## Final evidence references

Final folder `tmp/qa-seller-browser/7cc1ce7878744301/`:

- `wp2-browser.json`:23 actual checks, four complete axe results, fixture IDs.
- `wp2-desktop/browser-evidence.json` and `mobile/browser-evidence.json`:
  rendered text, controls, routes and sanitized request paths/status.
- `wp2-desktop/trace.zip`, `mobile/trace.zip`: finalized and CRC-checked.
- Desktop `002-research-not-started.png`, `004-not-comparable-alternatives.png`,
  `005-research-gaps-feedback.png`, `006-rejection-history.png`,
  `007-conversion-failure-recovery.png`, `008-converted-catalog.png`,
  `009-supplier-handoff-no-acquisition.png`; mobile three viewport captures.
- `session-final.json`: CLEANED, child0, marker verified/database absent/signed lifecycle.

Final disposable IDs: goal `6e004018-8688-4d71-8f7c-39e8c7e23ec6`, opportunities
`b3948bd5-029b-4a83-a79c-8798e0e74d81` and `9be147d0-a570-4105-b4b4-8a60de9c0980`,
Catalog product `e30113a4-ed7d-48da-90fc-c5e7c7ef572f`. These records have been deleted.

Screenshots were visually reviewed. They are viewport captures, not all full-page
screenshots; action/state assertions and traces establish below-fold controls. The
remaining repeated breadcrumbs and journey-banner height are not silently resolved.

## Accessibility / console / recovery

Four final axe scans (desktop comparison, desktop insufficient-research detail, mobile
saved research, mobile selected product) each have **0 violations and0 incomplete**.
Named generic divs were corrected to appropriate group semantics; no rule suppression.
Keyboard Tab/Shift+Tab moved between Reject and supplier handoff with visible focus;
confirmation cancel and form validation exercised. Full keyboard, screen-reader, zoom,
forced-color, physical-device and every-state WCAG certification remain incomplete.

Final desktop:9 console resource errors correspond to two expected absent plan/run404s,
six missing research-projection404s and one explicitly injected conversion503. Mobile:
one expected /auth/me401 before sign-in. Both contexts:0 uncaught page errors,
0 failed requests,0 guard-denied requests. The503 is a recovery seam, not an observed
unforced production outage. No real supplier/provider endpoint was called.

The final read-only audit checks all13 signed WP2 databases absent/DROPPED, original10
containers unchanged and original network/volume sets preserved. Two earlier normal
cleanup failures are retained and separately recovered, not overwritten as initial
success. Evidence survives cleanup. No Docker pruning or unrelated process termination.

## Exact Windows reproduction

From the repository root, with the already-approved QA instance available:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp2.ps1 -Action Backend
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp2.ps1 -Action Adjacent
npm.cmd run build --workspace @vayujit/web

# Terminal1: emits a NEW signed READY token; keep it running.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp2.ps1 -Action Browser
# Terminal2: use only Terminal1's token, not any historical/deleted token.
node qa/wp2-browser-retest.mjs tmp/qa-seller-browser/<READY_TOKEN>/session.json
# Replay requests owned shutdown. Terminal1 must report CLEANED; verify cleanup.

npm.cmd run test --workspace @vayujit/web -- --watch=false
npm.cmd run qa:unit
$env:PYTHONPATH='apps/api'
& apps/api/.venv/Scripts/python.exe -m pytest qa/unit -q
git diff --check
```

`python -m qa.wp2_final_audit` is a read-only audit of retained WP2 token evidence,
not a cleanup command. It will fail if any included database is still active/present.
PC-first backup/restore is parked and is not invoked by these commands.
