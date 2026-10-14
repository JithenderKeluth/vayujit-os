# PR-UX-01B.2 — PostgreSQL Integration Fixture Repair & Final Certification

**Run date:** 2026-10-10  
**Classification:** **PR-UX-01B — FULLY VALIDATED**

## A. Exact failing test and error

The PR-UX-01B.1 focused integration run previously failed during fixture teardown:

`cannot drop intelligence_supplier_portfolio_assessment_versions because dependent objects remain`

The affected reset was `reset_test_schema(...); metadata.drop_all(connection)`.

## B. Root cause

Migration `20261025_0104_supplier_portfolio_resilience.py` adds the database foreign key `fk_supplier_portfolio_current_assessment` from `intelligence_supplier_portfolio_contexts.current_assessment_version_id` to `intelligence_supplier_portfolio_assessment_versions.id`. The ORM column intentionally remains a plain UUID because the relationship is cyclic, so that migration-created edge is absent from `Base.metadata`.

SQLAlchemy therefore tried to drop the assessment-version parent before PostgreSQL could drop the metadata-invisible context dependency. PostgreSQL correctly rejected the DDL. This was a test reset lifecycle mismatch, not a production schema defect.

## C. PostgreSQL dependency analysis

The disposable database inspection found 12 child foreign keys referencing assessment versions, including the context pointer and the immutable input, concentration, dependency, resilience, risk, recommendation, simulation, and alternate-readiness tables. All are `ON DELETE CASCADE` except the context pointer’s `ON DELETE SET NULL`. The dependency was verified directly through `pg_constraint` before repair.

## D. Fixture lifecycle before and after

Before: integration fixtures attempted metadata-only `drop_all/create_all`, which could not see migration-only foreign keys.

After: the existing fail-closed fast reset path is enabled for integration tests with `VAYUJIT_FAST_TEST_RESET=1`. It validates the disposable target, terminates only stale sessions for that target, then executes `TRUNCATE` over mapped tables with `RESTART IDENTITY CASCADE`. This preserves the migrated schema, all foreign keys, and the marker table; it does not drop schema objects or suppress teardown errors.

## E. Files changed

- `apps/api/tests/conftest.py` — enables the dependency-safe reset for shared integration fixtures; keeps test provider/network settings fail-closed.
- `apps/api/tests/test_certification_fixture_stability.py` — adds the repeated-reset dependency/zero-row/marker regression.
- `scripts/test-api-integration.ps1` — exports the same reset mode for the supported integration runner.
- `docs/ux/pr-ux-01b2-validation.md` — this report.

No production model, migration, canonical authority, or frontend source was changed for PR-UX-01B.2.

## F. Regression test added

`test_migrated_supplier_assessment_dependencies_survive_repeated_reset` performs three resets and verifies:

- required portfolio/assessment tables remain present;
- the migration-only current-assessment foreign key remains present;
- mapped tables contain zero stale rows after reset;
- the disposable database marker remains valid.

The existing 20-run certification fixture test was retained and run as well.

## G. Previously failing suite

The four previously failing product-opportunity modules now pass:

`test_product_opportunity_foundation.py`, `test_product_opportunity_intelligence.py`, `test_product_opportunity_scoring.py`, and `test_product_opportunity_synthesis.py` — **9 passed, 0 errors** (20 warnings).

## H. Repeated database lifecycle

- New dependency regression: **1 passed, 20 deselected, 2 warnings**.
- Full disposable fixture stability: **21 passed, 0 failed** across 20 repeated client lifecycles plus the dependency regression (42 warnings).
- Migration certification: **2/2 runs passed**, each performing upgrade-to-head, focused downgrade, re-upgrade, marker verification, and disposable database removal.

## I. Product-opportunity regressions

The product-opportunity foundation/intelligence/scoring/synthesis matrix passed **9 tests**. Comparison, insufficient-evidence behavior, replay, canonical projection, and HUMAN selection remained green.

## J. Supplier assessment regressions

- Supplier portfolio foundation/integration/analysis/resilience/simulation modules: **10 passed** (22 warnings).
- Supplier portfolio hard certification: **17 passed** (36 warnings).

## K. PR-9A/PR-9B and security regressions

- Supplier security suite: **70 passed** (2 warnings).
- PR-9A.1, PR-9A.2, live-supplier certification, and PR-9B controlled-source suites: **55 passed** (28 warnings).

No live supplier acquisition or external network write was performed.

## L. Commerce Journey and handoff regressions

Commerce integration, PR-4 supplier journey, and PR-4.2 functional journey tests: **4 passed** (10 warnings).

## M. Angular results

No frontend code changed in PR-UX-01B.2, so the authenticated browser evidence from PR-UX-01B.1 remains valid. The Angular suite was nevertheless rerun: **60 test files passed, 213 tests passed**. Lint passed with the two pre-existing lifecycle-interface warnings. Production build passed; the existing initial bundle warning remains at **507.67 kB** against a 500 kB budget. No browser rerun is claimed for this fixture-only change.

## N. Static and technical checks

- Focused Ruff: passed.
- Focused Black: passed.
- Strict mypy on changed fixture files: passed.
- Python compileall: passed.
- `git diff --check`: passed (only normal Windows line-ending warnings).

## O. Golden database and disposable-database safety

Only `vayujit_ux01b1_test` and the migration certification database were used. Both disposable databases were removed after validation. `vayujit_golden_test` was only checked read-only for presence and was never modified.

## P. External effects

No supplier was contacted. No RFQ, email, purchase, payment, marketplace mutation, or external write occurred. HUMAN approval and canonical owner isolation remained in force.

## Q. Final classification

**PR-UX-01B — FULLY VALIDATED**

The PostgreSQL teardown root cause is understood and repaired at the test lifecycle boundary. Repeated disposable setup/teardown, migrations, populated product-opportunity behavior, supplier-assessment dependencies, journey handoff, security regressions, Angular validation, and focused static checks all pass. No production schema or canonical application authority was weakened.
