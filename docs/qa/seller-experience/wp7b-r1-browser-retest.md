# WP7B-R1 — independent browser and regression evidence

Date: 2026-11-05, Asia/Calcutta. Every run below used synthetic data and the guarded dedicated QA PostgreSQL authority; no production fixtures or provider calls.

## Preserved baseline and R1 execution

| Execution | Actual result | Meaning |
| --- | --- | --- |
| Original WP7B broad `66af017c1429b89e` | 81 PASS / 11 FAIL | Preserved, not rerun and relabelled |
| Original WP7B focused `071d1158209292db` | 48 PASS / 4 FAIL | Original 52 assertions retained |
| R1 pre-fix `67c081611ec1c006` | 2 PASS / 1 FAIL | Shared Ads unique-insert race reproduced; original endpoint/correlation distinction explained in remediation report |
| R1 pre-fix `cd102dd32f92bcc3` | 1 PASS / 1 FAIL | Actual saved-goals response closes a focused draft |
| R1 cold-start `27c1eddaf9ab91c5` | Runtime readiness BLOCKED; browser NOT EXECUTED | API startup exceeded prior polling budget; signed cleanup PASS. No ownership/token guard bypass |
| R1 native + first replay `e383423462181a8e` | 60 PASS / 8 FAIL | All 8 B-GOALS/B-DIALOG checks passed; added contrast harness exposed bad Campaign route and changing editor nodes |
| R1 expanded replay `9a6fad143ff9e2c5` | 94 PASS / 10 FAIL | All original focused 52 passed; affected broad groups and new regressions executed; remaining failures confined to added manual-contrast checks |
| R1 settled-color retest `5bd3f03205fd40bd` | 28 PASS / 0 FAIL at case level | Text/layout checks passed, but 8 supplemental focus measurements failed. Not a manual accessibility PASS |
| R1 Marketplace-focus replay `428ad971b5ba262d` | 80 PASS / 0 FAIL at case level | Original 52 again pass; Marketplace focus fixed at 8.5590892627:1. Two goal focus measurements still FAIL; retained and corrected separately |
| Final strengthened affected replay `57e1c0c8d2d30df9` | 32 PASS / 0 FAIL | Goals, delayed load, disclosure/errors, Ads modal/reflow and Marketplace focus retested; 0 measured focus failures |

The expanded replay's 104 checks comprise original focused 52, 20 affected broad checks (Research, Opportunity, Finance, Social, Ads), and 32 new R1 checks. It is **not** the complete historical WP7B program or whole-application certification.

| Browser / viewport | PASS | FAIL |
| --- | --- | --- |
| Chrome 156.0.8078.76 / 1440×900 | 24 | 2 |
| Chrome / 390×900 | 24 | 2 |
| Edge 156.0.4314.58 / 1440×900 | 23 | 3 |
| Edge / 390×900 | 23 | 3 |

Expanded replay source manifest matched before/after: true. It recorded 104 axe scans, zero violations, and **72 incomplete rule occurrences**. Incomplete is not PASS; repeated occurrences are not necessarily 72 unique defects.

## What passed independently

- Original goal and dialog assertions across all four contexts, including the three previously failing disclosure contexts and the original Chrome availability context.
- Native disclosure Enter/Space state, `aria-expanded`, textarea keyboard access, short-input validation/recovery, supported reload default and delayed saved-goals response with draft/focus preserved.
- Original catalog keyboard fields, Space checkbox operation, invalid JSON error/recovery and original navigation/import/editor group assertions.
- Ads modal title entry, forward/reverse Tab containment, Space close, Enter reopen, Escape dismissal and return focus. Any initial API 500 still fails the check even if bounded reload recovers it.
- Post-fix 320px Ads geometry in all four contexts: left 16, right 304, width/client/scroll 288, viewport 320. Title visible; keyboard Close and Escape/return focus pass. This is responsive browser evidence, not post-fix native zoom evidence.
- Research/opportunity context, Finance, Social and Ads route-level keyboard/reflow checks; no claim that every operation on these pages was exercised.

## Contrast-specific failures and bounded follow-up

Expanded replay retained six contrast failures (Meesho in four contexts, Flipkart in two) and four Campaign-target failures. The sampled Meesho Product button recorded rgb(88,110,117) on rgb(186,207,215), 3.3299834293:1 against required 4.5. Its saved image showed the settled white-backed state instead. The global style transitions color/background for 180ms; computed values were sampled before the transition finished but screenshot capture occurred afterward. This is conflicting temporal evidence, not proof of a persistent settled-state contrast defect and not justification for suppressing the contrast rule.

The sampler now observes finite transitions completing, without disabling/canceling them, before recording colors; infinite/unsettled transitions remain NOT VERIFIED. A self-test covers that boundary. Targeted follow-up covers dialog, responsive geometry, Social/Flipkart/Meesho/Finance with the same thresholds. Transient-state contrast is still a manual review requirement.

Run `5bd3f03205fd40bd` recorded 173 text PASS, 27 NOT VERIFIED, zero text FAIL; its 28 axe scans had zero violations and 18 incomplete rule occurrences. Crucially, 8 focus-outline measurements were FAIL despite case-level PASS. They were not discarded: actual Marketplace gold-on-white contrast was 2.3286826338:1. The production shared Marketplace focus rule now uses the existing strong brand token; the browser assertion was strengthened to fail on focus failures too. Later evidence must establish its repair; these earlier 28 PASS do not do so. Its tested source was unchanged during execution.

Run `428ad971b5ba262d` independently confirmed the Marketplace outline at 8.5590892627:1 (rgb(7,84,98) on white), but also retained two failing goal focus measurements at 2.3742314409:1. All 80 case assertions passed, with zero axe violations in 80 scans and 60 incomplete rule occurrences. This was not manual gate PASS. Goal/Ads light-surface focus colors were then corrected; goal and explicit Ads Close focus assertions were strengthened. Network evidence in this run: zero page errors, zero API 5xx, zero denied requests; expected unauthenticated bootstrap 401s and deliberate short-input/invalid-JSON 422s explain console error counts (2 desktop Chrome; 3 in each other context).

Final `57e1c0c8d2d30df9` has 32/32 PASS, unchanged source hashes, 32 axe scans with zero violations and 28 incomplete rule occurrences. It measured 138 text PASS / 18 NOT VERIFIED / 0 FAIL and 18 focus PASS / 126 NOT VERIFIED / 0 FAIL (12 rows have no focus measurement). Measured goal, Ads title/Close and Marketplace focus outlines are rgb(7,84,98) on white, 8.5590892627:1. These are sampled measurements, not full manual conformance. The earlier 104-, 80- and 32-check runs overlap; do not sum them as unique coverage.

Campaign route was corrected to canonical `/campaigns/:id`. Its future draft `review_checkpoint` is not eligible for rescheduling: the canonical recovery authority requires a missed activity or a reschedulable video state. The button is correctly absent. No state was forced, approval fabricated, worker started, or eligibility weakened to obtain PASS. The reschedule-panel contrast target remains **BLOCKED — eligible fixture not established**, not an application availability defect. The original failure records remain retained.

## Unit, persisted and quality results

| Suite | R1 result | Scope/evidence |
| --- | --- | --- |
| Backend persisted PostgreSQL `c32ab8336d214ed0` | 36 passed, 0 failed/skipped/errors | 4 new + 32 adjacent Ads version/concurrency and WP6B financial regressions; JUnit and cleanup retained |
| Angular focused | 17 passed | 16 goal tests plus existing Ads keyboard spec |
| Full Angular | 442 passed | Baseline 440 + 2 new goal regressions |
| Node QA first full run | 136 passed | Original 131 + contrast/startup helpers |
| Node QA after sampler regression | 137 passed | Added finite/infinite transition observation test |
| Node QA after focus regression | 138 passed | Added real shared Marketplace focus-token/ratio regression |
| Python QA | 163 passed | Original 161 + 2 safe diagnostic/redaction tests |
| Full/focused web ESLint | PASS | Existing warnings not suppressed |
| TypeScript app/spec | PASS | Both projects |
| Strict mypy | PASS, 5 source files | Ads router/service/optimization, R1 diagnostic and backend regression |
| Ruff / compileall | PASS | Changed Python and Ads scope |
| Black | Corrected focused checks PASS | API config explicitly supplied; changed Ads functions only, avoiding historical unrelated formatting rewrite |
| Prettier | PASS | Changed goal component/spec and Ads component |
| Production build | PASS | Existing initial-bundle warning remains an open performance risk |
| PowerShell parser | 3 files / 0 parser failures | R1 runner, R1 app wrapper, shared package wrapper |
| `git diff --check` | PASS | Rerun after documentation |

Initial `tmp/qa-wp7br1/quality-20261104T233513162Z.json` honestly retains Black exit 1 from the command that resolved default formatting across mixed roots. `quality-supplement.json` supplies corrected commands/results; `quality.json` is the latest full run, with all 15 checks PASS, including 442 Angular, 138 Node and 163 Python QA tests. Neither erases that first timestamped result. Formatting-only cleanup removed unrelated Ads changes; no behavior was rewritten to make checks green.

## Final isolation and restoration

Approved QA container `vayujit-qa-postgres`, ID `a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23`, instance `389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`, role `vayujit_qa_admin`, endpoint `127.0.0.1:55432`. Existing signed lifecycle, exact naming, owner/marker/token and cleanup controls were retained; R1 rejects legacy unguarded fallback.

Independent read-only final audit confirms all 9 R1-owned databases absent, all signed records DROPPED, 23 trace ZIPs with valid CRC, 0 protected-secret matches, 8 original WP7B evidence files unchanged and retained WP7A-7 provenance files unchanged. Tokens: `27c1eddaf9ab91c5`, `67c081611ec1c006`, `c32ab8336d214ed0`, `cd102dd32f92bcc3`, `e383423462181a8e`, `9a6fad143ff9e2c5`, `5bd3f03205fd40bd`, `428ad971b5ba262d`, `57e1c0c8d2d30df9`. No FORCE/drop recovery, unrelated Docker changes, permanent/golden migrations or business-data write commands were issued. This is not a row-level backup/preservation certification.

Normal development API/frontend were restored through the exact recorded R1 process scope after an exact-target read-only startup check found 0 pending campaign waits. Actual frontend `/`, API `/health`, `/health/live`, `/health/ready` all returned 200 with validated response identity; post-resume read-only check also found 0 pending waits. Evidence: `tmp/qa-wp7br1/process-restoration.json`. External mutations remain disabled in the restored process environment. Narrator remains active because desktop automation stopped; the owner may close it manually.

**Final decision: Gate A PASS; Gate B INCOMPLETE; WP7B INCOMPLETE.** Stop for owner review. No WP7C/WP8 or PC-first backup work started.

## Evidence and reproducible commands

Per-case API outcomes/routes, screenshots, traces, measured colors and source manifests are under `tmp/qa-seller-browser/<token>/wp7br1-browser.json`. These ignored local artifacts must be retained or securely exported if needed for subsequent review; their links are not a claim that they were pushed to GitHub.

From repository root, with fresh R1 approval record and protected QA instance already configured:

```powershell
# The wrapper exports protected QA settings only into this process.
& .\scripts\test-seller-wp7br1.ps1 -Action Backend

$env:WP7BR1_MANUAL = '0'
$env:WP7B_HEADED = '0'
$env:WP7B_CASE_IDS = 'B-LOGIN,B-NAV,B-GOALS,B-RESEARCH,B-OPPORTUNITY,B-CATALOG,B-SPACE,B-CATALOG-ERROR,B-MARKETPLACE,B-IMPORT-GROUP,B-MEESHO,B-EDITOR-GROUP,B-FINANCE,B-SOCIAL,B-ADS,B-DIALOG,B-REFLOW,B-320-REFLOW,R1-GOAL-PENDING,R1-GOAL-DISCLOSURE,R1-DIALOG-REFLOW,R1-CONTRAST-SOCIAL,R1-CONTRAST-FLIPKART,R1-CONTRAST-MEESHO,R1-CONTRAST-FINANCE,R1-CONTRAST-CAMPAIGN'
& .\scripts\test-seller-wp7br1.ps1 -Action Browser

$env:QA_ASSESSMENT_PACKAGE = 'WP7BR1'
node .\qa\wp7b-quality.mjs
node .\qa\wp7br1-quality-supplement.mjs
node .\qa\wp7br1-preservation.mjs
.\apps\api\.venv\Scripts\python.exe .\scripts\wp7br1-final-audit.py
```

Do not run lifecycle commands outside the still-authorized R1 task scope. Never use legacy unguarded fallback, FORCE, another connection string or another database to work around a failed guard. Browser runner exit zero means execution/cleanup completed; the report can still contain FAIL assertions, as these runs demonstrate.
