# QA Agent Phase 1 — implementation and validation handoff

Date: 25 October 2026, Asia/Kolkata. **Foundation IMPLEMENTED / APPLICATION FINDINGS OPEN.**

This phase delivered executable testing infrastructure. It did not authorize
production application fixes or certify the entire Seller OS. The smoke command
currently exits **1** correctly because of an open serious accessibility finding.

## Deliverables and implementation

- [Architecture, environment safety, all major seller journeys and phases](architecture.md).
- [Every declared page/redirect and source-test coverage](coverage-matrix.md).
- [API/model/service/test source inventory](application-inventory.json).
- [Actually registered runtime API operations](runtime-api-inventory.json).
- [Executed route coverage, distinct from source inventory](executed-coverage.json).
- [Generated human-readable report](initial-report.md) and [JSON report](initial-report.json).
- [Finding JSON schema](../../qa/finding.schema.json) and [reviewed usability recommendations](review-findings.json).
- Executable `qa/` tooling, pinned Playwright dependency/lockfile,
  `qa:audit`, `qa:unit`, `qa:smoke` npm commands and `scripts/run-qa-phase1.ps1`.

Source audit: **154 route declarations (148 page entries and 6 redirects), 1,610
static API declarations, 1,629 runtime OpenAPI operations, 421 model/table
declarations, 388 backend test files with 1,393 static test functions, 65 Angular
spec files**. These are different measures, not interchangeable coverage percentages.
Every page entry resolves to a component. Eighty page entries have no directly
corresponding component spec file; route reuse/shared tests mean that is not proof
of eighty entirely untested features. Backend-service string matching is a triage
aid, not proof that an endpoint is reachable or absent from the seller UI.

Only QA tooling, package metadata and new QA documentation changed in this phase.
The worktree was already dirty. Existing application, backup, infrastructure and
milestone changes were preserved. No business schema or migration was edited.

## Actual execution results

| Check | Actual result | Scope |
| --- | --- | --- |
| Playwright + installed local Chrome | **6 PASS / 2 FAIL / 0 SKIPPED** | Four scenarios each at desktop 1440×1000 and mobile 390×844, persisted synthetic PostgreSQL data |
| Owner onboarding | PASS both viewports | Empty installation, invalid email, mismatched password, Tab/Shift+Tab, UI owner creation, second-owner 409 |
| Catalog seller journey | PASS both viewports | Brand UI, product UI, INR price/cost exact persistence, edit, refresh, catalog context, legitimate readiness blockers, unavailable economics, back/forward, overflow assertion |
| Recovery and protected navigation | PASS both viewports | Catalog/Action Center/launch-readiness navigation, explicitly injected product-list 503, Retry against restored real local API, logout, protected route and API denial |
| Goal → canonical plan | Functional assertions completed; scenario FAIL both viewports | Goal/plan persisted with correct goal ID; no Start run, product discovery or supplier execution. Serious axe contrast rule fails the scenario |
| Axe | **12 real Chrome scans, 8 violation occurrences across 4 rule IDs, 2 incomplete rule/state occurrences** | No rules disabled. Incomplete checks retained for manual review; not WCAG certification |
| QA Node harness tests | **12 PASS** | Allowlists, narrow 503 exception, finding schema against actual results, fail-closed classification, inventory resolution, report failure semantics |
| QA Python harness tests | **6 PASS** | Database name/token guards, golden/business target rejection, real Windows socketpair, denied external/other-local TCP and external DNS |
| Existing Angular suite | **240 PASS in 65 files** | Actually rerun after adding the QA dependency; not merely inventoried |
| Current-source production build | PASS with existing warning | Initial bundle 514.48 kB exceeds 500 kB warning budget; not the 1 MB error budget |
| QA ESLint / Prettier | PASS | New JavaScript modules and finding schema |
| Focused Ruff / Black | PASS | Six QA Python files; repository API configuration |
| Focused strict mypy | PASS, 4 source files | Fixture server, network guard, AST backend audit, Python guard tests; local MYPYPATH |
| Python compileall | PASS | QA Python tooling |
| PowerShell parser | PASS | New wrapper only; no policy or scheduled-task change |
| Git diff whitespace | PASS | Existing CRLF-conversion notices remain; no commit/push |

The unit reporter regression deliberately simulates a failed scenario; its console
line is not a failed unit test. The suite's actual passed/failed totals are above.

## Confirmed findings and recommendations

The generated JSON stores exact rule IDs, affected selectors, remediation text,
screenshots, traces, confidence and retest status. On Business Agent:

1. **Serious `color-contrast`:** journey status text has 3.52:1 rather than 4.5:1.
   `.blocked` opacity applies to anchors that remain interactive. This is not an
   exemption for a genuinely disabled control.
2. `landmark-main-is-top-level`: page-level main is nested inside the shell main.
3. `landmark-no-duplicate-main`: shell and page main landmarks coexist.
4. `landmark-complementary-is-top-level`: the next-action aside is nested.

Those four rule types occur in both viewport scans: eight occurrences, not eight
independent source bugs. Both failing smoke scenarios fail on the same serious
contrast gate. Moderate landmark issues remain recorded even though only
critical/serious axe results fail that assertion.

Subjective recommendations are separately labelled: USD default in the Indian
seller creation journey (two viewport observations), indistinguishable active
parent/current sidebar links, and pre-run action/mode wording. No monetary error,
authorization defect or broken provider flow is inferred from these recommendations.
No production remediation was performed.

## Reproducible commands

From the repository root, in Windows PowerShell:

```powershell
npm.cmd run qa:audit
npm.cmd run qa:unit
& .\apps\api\.venv\Scripts\python.exe -m unittest discover -s qa/unit -p 'test_*.py'

# Current-shell-only variable: use an approved LOCAL PostgreSQL admin account.
$env:QA_DATABASE_ADMIN_URL = 'postgresql+psycopg://LOCAL_QA_USER:URL_ENCODED_PASSWORD@127.0.0.1:5432/postgres'
npm.cmd run qa:smoke
Remove-Item Env:QA_DATABASE_ADMIN_URL

# Existing frontend regression command:
npm.cmd run test:web
```

No `.env` edits are required. The smoke runner builds current production assets,
starts only its own loopback services, creates fresh marker/token databases and
removes them through the guarded child lifecycle. It does not start/stop Docker,
reuse a normal logged-in Chrome tab, or touch ongoing PC-first certification.

## Safety, cleanup and limitations

The final run's two database names and marker-verified absence proofs are in the
generated report. Both children exited 0 after cleanup even though Playwright
returned failure for the known application finding. Earlier harness startup
failures were not certified as passes. Synthetic private media and evidence remain
locally in ignored `tmp/qa-agent`; no important user files were removed.

The egress guard is test-process instrumentation plus canonical default-deny
configuration and a browser/proxy allowlist, **not an operating-system firewall
certification**. Credentials and `.env` settings are not loaded into the synthetic
API. Actual normal authentication and single-owner constraints are retained.

ORM metadata fixture creation is **not Alembic/migration certification**. Health
liveness and canonical APIs were exercised; health-ready's actual body is retained
without stamping a false migration revision. Full backend regressions, private
media/foreign-ID matrices, all keyboard/dialog behavior, live providers, external
marketplaces, financial calculations and Electron were not executed by this phase.
No normal or golden database, marketplace, supplier, payment or procurement action
was targeted. No branch, commit or push was created.

## Recommended next phase

Phase 2: migration-backed disposable fixtures and the P0 seller journey from goal
through product HUMAN selection, relevant supplier evidence, due diligence and
commercial decision, plus independent Decimal calculation oracles and unknown/stale/
replay cases. Keep synthetic evidence explicit. The confirmed accessibility defects
can be a separately authorized bounded production-fix workstream; do not silently
turn the QA Agent into an autonomous production fixer.
