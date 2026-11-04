# WP7 — Integrated application certification plan

2026-10-31. Certification-first; **no production-launch claim**. This work stops before WP8.

## Authority and environment

The attached WP7 specification controls scope. Reconcile the original audit, 20 browser findings, WP1–WP6B reports/ledgers and current TypeScript/Python source inventory. Do not treat earlier assertion passes, route headings or API registration as whole-feature certification.

Use only the previously authorized, attested `vayujit-qa-postgres` instance, loopback `127.0.0.1:55432`, dedicated non-superuser `vayujit_qa_admin`. Each run receives a fresh `vayujit_qa<16-hex>_test`, signed lifecycle and marker/owner/OID verification. Full Alembic migrations, canonical synthetic owner setup and persisted APIs, external emergency stops, TCP egress guard and same-origin proxy remain required. No permanent/golden database access, real provider credentials, marketplace/supplier calls or unrelated Docker changes. Backup remains parked.

## Execution

1. Fresh AST route/capability/model/test inventory, dependency lock hash and exact Git base revision (dirty worktree explicitly recorded).
2. Fresh production Angular build, all Angular and QA guard/oracle self-tests.
3. Migration-backed 26-module backend matrix: WP1–WP6B, scoring/Catalog/Agent/source review, economics/readiness/HUMAN decisions, inventory/orders/Finance/Action Center, concurrency/provenance and upgrade/rollback tests.
4. Independently rerun eight existing real authenticated browser suites, each in a separate fresh disposable installation. Preserve their original assertions and failures.
5. Extend to every actual static application page and legitimately populated detail routes. Full read/layout/axe inventory in Chrome desktop and Edge mobile; critical routes additionally Chrome mobile, Edge desktop and Chrome tablet. Record artifact-dependent unexecuted pages as BLOCKED, not PASS. A route render is not a submitted business operation.
6. Capture screenshots, traces, sanitized console/network evidence, user-visible errors, keyboard/menu/history/reload/deep-link/session boundaries. No fabricated provider output to fill coverage gaps.
7. Fresh-process read-only cleanup/isolation/secret/trace audit. Record exact commands/counts and all skips/failures; no forced cleanup or unrelated deletion.

## Decision

PASS requires all supported critical journeys and required security/data-integrity/accessibility gates demonstrated. CONDITIONAL is available only when critical journeys pass and remaining gaps are bounded/lower severity. Significant missing required coverage or critical failures means FAIL even if regressions pass. Automated axe success is not WCAG compliance. Real integrations, financial accounting readiness, backup/restore and production launch are separate gates.

No high-risk schema, new financial-history architecture, destructive migration or new business capability is authorized to force a green result. Minimal confirmed in-scope fixes need root-cause evidence and independent retest. Otherwise record the defect and required approval.
