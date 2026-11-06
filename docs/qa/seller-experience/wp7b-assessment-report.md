# WP7B — assessment report

**WP7B INCOMPLETE. Overall application certification INCOMPLETE. No launch or live-provider authorization.**

## Outcome

WP7A's bounded local 48-entry provenance reconciles: 41 inherited + 7 targeted. The approved Ads expiry scope is explicitly narrowed offline scope, not live expiry certification. Historical evidence is preserved. See [provenance](wp7b-certification-provenance.md).

Three minimal frontend corrections: named import-control group, named Meesho editor group, and read-only Ads preview keyboard focus management. No approval, calculation, provider, database schema or single-owner authority was changed. New backend Python source was not edited.

| Correction | Result |
| --- | --- |
| WP7B-GROUP-001 | RESOLVED AND RETESTED |
| WP7B-GROUP-002 | RESOLVED AND RETESTED |
| WP7B-MODAL-001 | RESOLVED AND RETESTED IN FOUR CONTEXTS |

## Actual validation

- Broad Chrome/Edge desktop/mobile: 81 passed, 11 failed / 92.
- Focused independent retest: 48 passed, 4 failed / 52. These scopes overlap and must not be added into unique coverage.
- Backend: 32 passed, zero failures/errors/skips; exact JUnit and signed cleanup retained.
- node: PASS — 131 passed; exit 0.
- python: PASS — 161 passed; exit 0.
- angular: PASS — 440 passed; exit 0.
- lint: PASS; exit 0.
- lint_specs: PASS; exit 0.
- lint_web: PASS; exit 0.
- types_spec: PASS; exit 0.
- ruff_ads: PASS; exit 0.
- black_ads: PASS; exit 0.
- compile_ads: PASS; exit 0.
- types: PASS; exit 0.
- mypy_ads: PASS; exit 0.
- build: PASS; exit 0.
- diff: PASS; exit 0.
- PowerShell parser: three changed scripts, zero errors (independent check).
- Native input BLOCKED; screen-reader speech and actual browser zoom NOT VERIFIED.

Earlier failed test-fixture/lint attempts and browser failures remain in tmp/qa-wp7b execution/quality history; they are not silently erased. The original browser runner exit zero means execution/cleanup completed, **not** that assertions passed. The gate consumes individual assertion results.

## Safety and preservation

Explicit owner approval covers only dedicated vayujit-qa-postgres at 127.0.0.1:55432, role vayujit_qa_admin, signed marker/token/OID/owner lifecycle guards and synthetic data. No authorization is inferred merely from a connection string. Allowed database names: vayujit_qa<16hex>_test. QA role remains non-superuser; source approvals and HUMAN decisions are not bypassed. B reuses the WP7A7 fixture contract, not WP7A recertification. A B-only empty-body recommendation-preview allowance grants no confirm, execution, dispatch, dismissal or provider access.

Read-only final audit: cleanup PASS; 8 task databases checked; 13 trace archives verified; 0 protected-secret matches; WP7A-7 document hashes unchanged: true. See tmp/qa-wp7b/final-audit.json for exact instance/database evidence. No permanent/golden database was accessed by these QA operations. External activity of the older normal API is not represented as a proven permanent-row preservation audit.

The approved process pause failed closed after stopping only its captured tree; an older normal API remained. No Python source edits were made. Exact final listener/restoration evidence is retained separately; do not reinterpret the original failed pause as success.

## Residual decisions

Historical PostgreSQL runtime timestamps remain unattributed; read-only structural preservation and available lifecycle events are recorded separately. No inference of data loss or unauthorized action is made. Historical comparison 502 remains unreproduced/cause unresolved; current local requests are bounded evidence, not proof of repair. New anomaly 500 remains open and is not conflated with the 502.

Financial arithmetic/lineage regression scope is distinct from immutable accounting, statutory reconciliation and financial-history completeness. Schema/index debt needs query-plan/data evidence, not blind migrations. Provider connectivity remains unverified. PC-first encrypted independent backup/restore remains parked and a real-data activation blocker. Full owners, severity/likelihood/impact, mitigations and gates: [residual risk register](wp7b-residual-risk-register.md).

## Reproduce on Windows

From the repository root:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7b.ps1 -Action Browser
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7b.ps1 -Action Backend
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7b.ps1 -Action Quality
```

These are WP7B approved synthetic-only commands; no production URL/credentials should be substituted. Authorization metadata is task-specific; QA instance identity is independently checked by the signed harness. Fresh runs create new disposable tokens and clean only their own positively identified databases. Any cleanup guard failure must stop and be reported, not bypassed.

## Files changed

Production: apps/web/src/app/marketplaces/{marketplace-accounts,meesho-workspace}.component.ts; apps/web/src/app/ads/ads-optimization.component.ts. Corresponding three component spec files. QA foundation: qa/wp7b-{browser,domain-fixture,inventory,provenance,safety,quality,final-audit,report}.mjs and three qa/unit/wp7b-*.test.mjs; narrowly extended qa/{safety,server,seller-browser-explore,wp7-run}.mjs. Scripts: scripts/test-seller-wp7b.ps1, scripts/restore-wp7b-frontend.ps1 and wp7b package name in scripts/qa-wp7a6-app-window.ps1. Six requested WP7B reports and local evidence. No application backend/migration changes.

## Requirements before WP7C gate closure

1. Complete actual screen-reader speech checks with a compatible Windows reader/browser and retain human observations.
2. Complete native keyboard/actual zoom and remaining exact historical contrast/non-text/target checks.
3. Resolve or safely attribute the new Ads anomaly 500; preserve the dialog recovery evidence independently.
4. Triage any remaining focused browser failures without weakening assertions.
5. Review residual risk register and explicitly retain provider, financial-history and independent-backup launch gates.

Actual speech/manual accessibility checks remain required, so CONDITIONAL or PASS would be unsupported. Stop after WP7B. WP7C/WP8, live providers, production launch, branches, commits, pushes and backup work were not started.

## Exact remaining browser outcomes and environment handback

The final 4 failing cases are goal textarea visibility after keyboard disclosure opening in Chrome1440, Chrome390 and Edge1440, plus the initial Ads anomaly 500 in Chrome1440. Edge390 goal entry passed. The direct-summary selector and distinct variant options corrected demonstrated harness problems, but **did not close the three remaining goal visibility failures**. Their application-versus-harness cause remains unclassified; no timeout or assertion was weakened. See WP7B-GOAL-KEYBOARD-001.

All four dialog keyboard sequences passed after the minimal fix. One context needed a single bounded reload after the 500; its overall case remained FAIL. Availability and recovery are not conflated. Both group-role regressions passed in all four contexts. All corrected variant-error recovery cases passed with legitimate distinct combinations.

Full frontend lint currently reports zero errors and two existing use-lifecycle-interface warnings (catch-up-dialog.component.ts:157; reschedule-dialog.component.ts:224). They were not suppressed. The current production build passed; historical bundle warnings are not evidence that this particular build emitted a warning or that WP7B repaired bundle performance. Repository-wide Python typing/lint cleanliness was not tested or claimed; scoped changed/relevant gates are listed above. Unrelated debt still requires assessment of its actual production path.

The normal frontend was restored only after confirming its port was unoccupied and the exact older API PID still matched. Frontend index HTTP 200 and API /health/live HTTP 200 were observed; the API was not restarted or replaced and no database operation was performed. These are serving/liveness checks, not full real-database readiness or live-provider certification. Evidence: tmp/qa-wp7b/app-restoration.json. The original failed pause record remains unchanged.

## Companion evidence

- [Accessibility inventory](wp7b-accessibility-inventory.md)
- [Keyboard/manual evidence and limitations](wp7b-manual-accessibility-evidence.md)
- [Residual risk register](wp7b-residual-risk-register.md)
- [Certification provenance](wp7b-certification-provenance.md)
- [Machine-readable gate](wp7b-gate.json)

The 200% root-text check records a width assertion while enlarged, then resets before its ordinary screenshot/axe capture; it is not a retained zoom-state visual review. Tablet 768/1024 and 360px phone contexts were not executed in WP7B. Exact historical contrast-target adjudication and complete cause-level deduplication remain incomplete, rather than silently inferred from zero fresh axe violations.
