# WP1 — Actual browser retest

Date: 2026-10-28. Scope: supplier discovery → HUMAN shortlist → existing-evidence
assessment → scoped economic inputs. **Bounded local WP1 PASS; application INCOMPLETE.**

## Isolation

Approved container `vayujit-qa-postgres`, instance
`389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`, loopback `127.0.0.1:55432`,
non-superuser role `vayujit_qa_admin`. Only signed, token-owned
`vayujit_qa<16-hex>_test` databases. Credentials remain in ignored ACL-protected QA
storage; production .env was not edited. Server-side and browser/proxy network
controls block external execution. Fixture records explicitly synthetic.

## Before and after evidence

All paths below are repository-relative local evidence, ignored by Git. Browser
traces contain synthetic sessions and should not be published as production data.

| Run | Actual evidence/outcome |
| --- | --- |
| Historical 28be28cb826accab | Original screenshots and trace actions inspected; not new retest evidence |
| Before eca20e8eced7f200/wp1-before | Fresh UI reproduction: LOCAL page submits LIVE (proxy403); economics201 lacks lineage; unassessed gaps0/no assess. Three PNGs and intact trace.zip |
| Main d13067df8b66b91a | wp1-browser-checks.json, wp1-desktop (20 PNGs), mobile (7 PNGs). 31 final checks pass. Desktop trace intact; mobile trace incomplete after REPL timeout, PNG/JSON remain. Do not cite it as a finalized trace |
| Failed replay 8c8e0f00a236849d | 1 check passed then fixture missing description excluded by existing meaningful-opportunity rule; Find suppliers absent. No rule bypass; fixture corrected. Intact diagnostic trace |
| Failed replay c46926f3a9d35b94 | 6 checks passed then new plain-hash economics jump navigated to base /. Corrected to scope-preserving router fragment. Intact diagnostic trace |
| Final baa7fa4093efbf17 | wp1-final-browser.json: 13 PASS, 0 FAIL; final-desktop and final-mobile: 5 PNGs, 2 intact traces, browser-evidence.json |

Final identifiers: opportunity `5e5cc6af-202b-475d-b759-63af80027f4b`, canonical
supplier `b0827019-6240-4dc0-a2cb-d194ed4726de`, saved economics context
`e093921a-e7bb-4927-b076-7e341ba7b390`. These were disposable and have been deleted.

The main browser's early fixed-500ms scope observation is retained as FAIL; the
authoritative settled-state retest passed. Discovery replay checks use the actual
nonempty request.id, not an undefined search_id. New replay uses awaited API/UI state.

## Journeys genuinely exercised

| Case | Browser/API outcome |
| --- | --- |
| Product detail → HUMAN selection → Find suppliers | Decision201, canonical selected scope, UI submits LOCAL_FIXTURE, research200/external_calls=false |
| Discovery replay / duplicate action | Same request identity; busy controls prevent duplicate assessment/context creation |
| Compare | Correct #comparison, selected opportunity query preserved, no Dashboard fallback |
| Supplier detail → Evaluate shortlist → HUMAN shortlist → Assess | Existing authorities only; UNKNOWN before assessment; actual missing-evidence gaps afterward, not SUFFICIENT |
| Scoped economics create/reload | Context201 includes typed canonical opportunity/supplier; saved context ID in URL, exact readback; INR/100 input persisted |
| Cross-page and mobile reload | Assessment → economics retains supplier; refreshed shortlist can resume existing verification; desktop reopens mobile-created evaluation |
| Missing/invalid/stale scope | Missing opportunity with supplier, invalid UUID/context, unrelated supplier/opportunity, product-B URL with product-A evaluation, archived opportunity all block without substitution |
| Backend failure and retry | Explicit injected503 seams: discovery clears usable mode; assessment preserves prior version; context failure retains scope; recovery retry passes |
| Unauthorized acquisition | Injected DISABLED projection disables CTA. This is a test seam, not live authorization or a changed production provider setting |
| Keyboard | Enter assessment, Space while busy yields one request, keyboard create, Tab/Shift+Tab field order, visible focus; mobile Back/Forward/refresh persist scope |

UI viewports: desktop1440×900 and mobile390×844. Main mobile run used touch/mobile
emulation; final replay used a narrow responsive Chrome viewport (not physical-device
certification). No complete multi-browser or whole-application claim.

## Accessibility and errors

Final axe scans: desktop economics0 violations/0 incomplete; mobile economics0/0;
mobile assessment0 violations/**17 incomplete color-contrast nodes** (partially obscured
Status/Action header and table cells); desktop assessment0/0. Rules were not suppressed.
Incomplete nodes and exact HTML/targets remain in wp1-final-browser.json. Manual review
of horizontal-scroll table content is still required; not full WCAG certification.

Final desktop: 0 console/page/failed-request/guard-denial errors. Final mobile: 0 page
errors/failed requests/guard denials, one expected unauthenticated /auth/me401 while
entering Login. No post-login unexpected API error in final replay. Earlier injected503
responses are explicitly test-induced. Screenshots were visually reviewed, including
mobile economics focus/layout and scoped assessment states.

## Cleanup and persistence

Fresh process readback during the main run checked canonical IDs, INR quantity
100.00000000, one user, ck_users_single_owner and Alembic head20261204_0147. Final
UI refresh/deep-link readback checked the final saved artifact before cleanup.
All owned runtime child reports CLEANED except the preserved earlier preflight
CLEANUP_BLOCKED; its explicit guarded recovery is documented in remediation.
`tmp/qa-wp1-final-audit.json` independently verifies eleven signed DROPPED/absent
databases, original ten containers unchanged, original networks/volumes preserved,
zero configured QA credential matches in reports/docs/log scan, and final trace CRCs.

## Reproduce on Windows

From repository root, with the approved QA instance available and existing dependencies:

```powershell
# Backend: new signed disposable DB, migrations, 13 focused persisted tests, cleanup.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp1.ps1 -Action Backend

# Build frontend; no dependency installation or external acquisition.
npm.cmd run build --workspace @vayujit/web

# Terminal 1: starts an owned runtime, prints READY token/path. Keep it running.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp1.ps1 -Action Browser

# Terminal 2: substitute ONLY Terminal 1's new token; creates synthetic fixtures via APIs/UI.
node qa/wp1-browser-retest.mjs tmp/qa-seller-browser/<READY_TOKEN>/session.json
# Replay writes stop.request; Terminal 1 must finish CLEANED. Never reuse historical tokens.

npm.cmd run test --workspace @vayujit/web -- --watch=false
npm.cmd run qa:unit
$env:PYTHONPATH='apps/api'
& apps/api/.venv/Scripts/python.exe -m pytest qa/unit -q
git diff --check
```

Focused checks actually executed: Ruff14 changed Python files; Black11 application/
fixture files at100 columns plus3 QA files at existing88-column style; compileall;
strict mypy economic_models.py/economic_schemas.py/economic_service.py/supplier_router.py;
ESLint10 affected TypeScript files; PowerShell5.1 parser0 errors; Node syntax replay.
The read-only `python -m qa.wp1_final_audit` refers to this execution's historical
tokens, not a general reset command. It performs no deletion.

No full historical browser matrix or repository-wide static debt closure was claimed.
Initial tooling invocations used an incorrect workspace CLI path and were corrected;
new Angular fixture initialization assertions initially failed, then the final suite
passed280 without removing the navigation assertion.
