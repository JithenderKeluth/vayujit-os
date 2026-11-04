# WP7A-7 closure report — 4 November 2026

**WP7A PASS — LOCAL SUPPORTED FUNCTIONAL COVERAGE.**

Original denominator preserved: **48 entries = 41 inherited closed + 7 newly
closed**. No PARTIAL entries remain in this gate. Overall application
certification remains **INCOMPLETE**. This is not live-provider, production
accounting, full accessibility, backup/restore or real-business launch certification.

Machine decision: [wp7a7-gate.json](wp7a7-gate.json).
Assertion-level history: [wp7a7-coverage-ledger.json](wp7a7-coverage-ledger.json).
Original requirements and explicit HUMAN decisions:
[closure plan](wp7a7-closure-plan.md).

## Seven-entry reconciliation

Each row passed in installed Chrome **156.0.8078.76** and Edge
**156.0.4314.58**, at **1440 and 390 pixels**. The required assertion keys are
unchanged; adjacent tests were not substituted for these journeys.

| Stable ID | Supported local outcome | Required assertion keys | Contexts |
|---|---|---:|---|
| R-3feda36d | Image-only Social draft, exact HUMAN approval, stale edit rejection, failed-save recovery, replay, reload, no publication | 9 | 4/4 PASS |
| R-55e822d5 | Overview and exact accounts distinguish sandbox configuration from live connectivity; missing/invalid/expired/revoked represented states, recovery and default deny | 7 | 4/4 PASS |
| R-551d2f8c | Flipkart unpublished preparation, legitimate readiness correction, exact review, authorization renewal/revocation/expiry, stale/conflicting requests and no submission | 10 | 4/4 PASS |
| R-db243c36 | Meesho unpublished preparation and price persistence, missing prerequisites, truthful manual/live-unverified boundary, duplicate/invalid price and no dispatch | 8 | 4/4 PASS |
| R-d6a495d5 | Amazon actual local-draft creation, variants/price/image, canonical readiness, exact review/authorization, stale/replay/reload, no SP-API submission | 10 | 4/4 PASS |
| L-16 | Immutable artifact replacement, changed dependency graph, stale fingerprint rejection, explicit fresh reschedule confirmation, replay and persisted no-release state | 9 | 4/4 PASS |
| L-17 | Content/image creative readiness, exact immutable identity, represented missing/disabled authorization, stale preview, HUMAN confirmation, concurrent replay, recovery/reload and no spend | 10 | 4/4 PASS |

L-17's original acceptance remains quoted in the plan and ledger. The owner
explicitly approved the narrow expiry clarification. Real provider token expiry
remains **UNVERIFIED**; no expiry model or provider success was invented.

## Root causes and corrections

[Defect register](wp7a7-defect-register.md) separates application defects from
harness defects and retains failed attempts. The three requested fixes reuse
existing Social and marketplace authorities; there are no new database models,
migrations, marketplace integrations or approval systems.

- Social image approval now requires the exact reviewed fingerprint and explicit
  HUMAN confirmation. It cannot schedule or publish. Owner/post locks serialize
  relevant creates, edits and approvals.
- Amazon local preparation uses opt-in `prepare_only` and existing local variant,
  price and image authorities, never the connector. First-price timestamps are
  populated. Existing review fingerprints include preparation inputs.
- Meesho no longer requires submission before a local draft can receive its
  required price. Canonical pricing policy and validation remain authoritative.
- Editors retain the exact account/product/artifact. Saved price/readiness is
  reloaded. The final matrix exposed a late-hydration race: two new Meesho tests
  failed before correction and passed afterward. Meesho and equivalent Flipkart
  pricing controls now wait for hydration and ignore obsolete selection responses.
- Flipkart authorization rechecks readiness after review. Amazon/Flipkart project
  existing expiry timestamps truthfully and reject conflicting replay keys.
- Campaign's existing fingerprint now includes sorted persisted dependency edges.
  The synthetic missed-intent fixture is explicitly historical/synthetic; no
  real worker execution or Campaign release is claimed.
- Ads prospective readiness reuses the creative validator with the selected owned
  account. Exact creative and credential version enter the preview. Existing
  campaign, creative, budget and queued intent persist atomically after HUMAN
  confirmation. No worker success, remote campaign or spend is manufactured.

Image identity is the approved immutable Output UUID and matching Media UUID,
checksum, dimensions and size. The consumer `image_version` field is not claimed
to be a new authoritative source-version counter.

## Actual final validation

| Gate | Actual result |
|---|---|
| Backend, ten focused/adjacent files | **105 passed**, 0 failed/errors/skipped; final run `f38c0a55864b4da1` |
| Seven browser journeys × four contexts | **28 passed**, 0 failed/blocked/partial; final run `daf1450bc1179b3d` |
| Node QA self-tests | **128 passed**, 0 failed/skipped |
| Python QA self-tests | **161 passed** |
| Independent final Angular suite | **438 passed**, 88 files; `tmp/qa-wp7a7/angular-final.json` |
| Focused Meesho regression | Before: 4 passed/2 failed. After: **6 passed**; included in the final Angular suite |
| Production build | PASS |
| Focused ESLint, application/spec TypeScript | PASS |
| Strict mypy, 12 changed backend source files | PASS |
| Focused Ruff, Black, compileall | PASS |
| PowerShell/Node parser checks | PASS |
| `git diff --check` | PASS; rerun after documentation |

The quality batch recorded 437 Angular tests while the final Flipkart regression
was being added. An independent subsequent full run executed **438**, with no
source edits afterward. These are repeated runs, not additive test counts.
Timestamped quality records and original failures are preserved.

Backend source hashes matched during the final run and still matched at gate
generation. Browser source/build hashes matched at start and finish. The gate
uses explicit run IDs, not modification-time precedence or a mixture of old passes.

## Browser, accessibility and security evidence

[Browser evidence](wp7a7-browser-evidence.md) lists corrected attempts and final
artifact locations. The final run contains four valid traces and owned persisted
snapshots, screenshots and network outcomes. Expected negative HTTP outcomes
include 401/404/409/422; unexpected API 5xx/render errors were not accepted.

There were **40 actual axe scans, zero reported violations**, and **22 incomplete
rule/context occurrences**. These incomplete checks are not PASS results. Exact
rules/targets and manual-review requirements are in the browser report. Basic
focus, Tab/Shift+Tab and Ads HUMAN-checkbox Space interaction were exercised.
Full keyboard/screen-reader/visual accessibility compliance is not certified.

Isolation uses the single-owner installation model, authenticated normal APIs,
anonymous denial, invalid-resource rejection and owned snapshots. It does not
claim shared-database multi-tenancy or pretend a second owner was permitted.
`ck_users_single_owner`, emergency stop, provenance and HUMAN boundaries remain.
No real marketplace, Social, Ads, AI or supplier action occurred.

## Independent cleanup and preservation

`tmp/qa-wp7a7-final-audit.json` independently confirms **19 task-owned databases
absent**, each signed lifecycle `DROPPED`. No recovery or FORCE operation was
needed in this package. Eleven retained traces passed integrity inspection;
protected QA credential scans found zero matches. Forty-four historical baseline
files, including WP7A-6 guarded recovery evidence, remained byte-identical.

The audit deliberately exits nonzero for the carried **historical environment
baseline drift**: `/infrastructure-postgres-1` has different StartedAt/FinishedAt
timestamps. Structural identities and network/volume collections are unchanged.
The cause remains **UNATTRIBUTED**. Database-absence status is independently PASS;
the overall Docker preservation audit is not misrepresented as green.

Normal development API/frontend were restored under the owner's explicit
approval. A separate read-only check of the exact previously running `vayujit`
database found zero incomplete Campaign waits, avoiding normal startup recovery
writes. No fixture, migration or repair targeted that database. Final loopback
checks: API `/health/ready` **200**, frontend `/` **200**. The frontend needed its
normal startup build before responding. External mutation emergency stop remains
enabled. No permanent/golden database data or schema was changed by certification.

## Changed-file scope

The existing dirty worktree is preserved; this is not a claim that all repository
changes belong to this package.

- Backend: `social/{schemas,router,service}.py`,
  `commerce/{schemas,router,amazon_router,flipkart_router,meesho_router}.py`,
  `campaigns/recovery_service.py`, `ads/{schemas,router,service}.py`.
- Backend regressions: `apps/api/tests/test_seller_wp7a7.py` (11 tests).
- Angular: Social workspace/service/spec; Amazon, Flipkart, Meesho and Ads
  workspace components/specs under `apps/web/src/app/`.
- Existing QA plumbing: `fixture_server.py`, `wp7a_fixture.py`, `wp7a2_fixture.py`,
  `wp7a3_fixture.py`, `wp7a4_fixture.py`, `seller-browser-session.mjs`,
  `seller-browser-explore.mjs`, `safety.mjs`, `server.mjs`, `wp7-run.mjs`,
  `wp7a4-browser.mjs`, `wp4_final_audit.py`, `wp7a4_final_audit.py`.
- New QA: `wp7a7-{contract,diagnostic,quality,register,report,safety,scenarios,source}.mjs`,
  `wp7a7_{fixture,snapshot,status,final_audit}.py`; corresponding contract,
  diagnostic, safety, fixture and Campaign-fingerprint unit tests in `qa/unit/`.
- Scripts: `test-seller-wp7a7.ps1`, package-specific recovery record support in
  `qa-wp7a6-app-window.ps1`, read-only `wp7a7-resume-preflight.py`.
- The six requested WP7A-7 documents/JSON files and the traceable canonical matrix
  addendum. No historical ledger or recovery record was rewritten.

## Reproduction

From the repository root, with the already-approved dedicated QA instance:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a7.ps1 -Action Backend
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7a7.ps1 -Action Browser
node qa/wp7a7-quality.mjs
npm.cmd run test --workspace @vayujit/web
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "& './scripts/qa-postgres.ps1' -Action Environment; & './apps/api/.venv/Scripts/python.exe' -m qa.wp7a7_final_audit"
```

The existing QA harness obtains protected QA configuration without printing it.
Do not point these commands at another database. Use a separately approved app
pause window before future code edits; do not reuse this package's consumed pause
record. Read-only audit exit 1 for historical Docker timestamp drift is distinct
from a failed database-absence check.

## Remaining risks and stop boundary

Carry forward, without invented resolution: PostgreSQL timestamp discrepancy;
historical Ads 502; incomplete/manual accessibility checks; repository-wide typing
and lint debt; financial-history/reconciliation and production-accounting limits;
parked PC-first backup/restore certification. Only scoped static checks were run;
repository-wide debt has not been cleared or declared safe for production launch.

The earlier legacy-content request to Studio regeneration returned 500. Using the
matching generation authority corrected the fixture, not that incompatible route.
The Ads image form still requires an exact Output ID; this package is not a broad
usability redesign. Live expiry/provider behavior requires a separately verified
contract and authorization.

No branch, commit, push, unrelated Docker change, permanent initialization or next
work package was performed. **Stop here for review; do not start WP7B/WP7C/WP8.**
