# WP6B — Bounded quality remediation and risk disposition

2026-10-30. Application certification remains **INCOMPLETE**. No WP7 execution,
business activation, permanent upgrade, live provider call or backup certification.
Final actual results and recommendation are in `wp6b-quality-gate.json` and the
browser/accessibility reports; old failed attempts are not overwritten.

## Final decision and executed results

**WP6B BOUNDED LOCAL QUALITY WORK VALIDATED. GO for WP7 comprehensive testing
only, subject to owner review; WP7 was not started. Real-business activation is
NO-GO and application certification remains INCOMPLETE.**

- Final new backend28 PASS (`64b108e20bd44e44`), adjacent49 PASS
  (`8118ef894b5f40f5`), zero failed/error/skipped assertions, both runners exit0
  with normal marker-verified cleanup and explicit90s DROP deadline recorded.
- Main browser8 groups and original-node follow-up4 groups PASS; one baseline
  repeats, not12 unique complete workflows. Both accepted runtimes clean normally.
- Angular373/81files, Node66, Python57 PASS. Build422.71kB below unchanged500kB
  budget. Focused lint/format/types/strict new-module mypy/parsers/compileall and
  git diff whitespace checks PASS. No repository-wide debt recertification.
- Final read-only audit: **15/15 signed DROPPED and independently absent**,
  original10 Docker containers/networks/volumes preserved,14 traces CRC PASS,
  current approved credential matches0, no raw container logs retained.
- Five earlier interrupted drops required exact guarded recovery. Original
  nonzero exits/failure reports remain; the final two backend and two browser
  runs clean normally. Do not rewrite the earlier results as successful runs.

No evidenced WP6B application-owned P0/P1 is left untriaged. Remaining P2 items:
unreproduced Ads502, rounded order-unit/source reconciliation boundary, financial
history/sole-accounting guarantees, historical constraint/load/index risk, and
explicit manual accessibility scope. Host deletion latency remains a classified
QA infrastructure risk even though the bounded deadline correction is validated.

## Baseline inventory and corrections

Read WP6/WP6A remediation, retests, quality debt and ledgers; earlier seller
findings and their explicit follow-up dispositions remain authoritative history.
Current migration head is `20261206_0149`. No new migration, dependency, historical
migration edit, numeric-scale change or single-owner architecture change in WP6B.

| ID / initial risk | Root cause / evidence | Bounded action |
| --- | --- | --- |
| SE-WP6-ADS-502-001 /P2 | Historical final Edge390 trace has exactly one GET `/api/v1/ads/comparison`502, empty content, unknown MIME. It carries no retained transport error or upstream cause. | Repeated actual browser/API reads, plus forward-safe QA proxy classification and negative/recovery self-test. **Unreproduced /cause unclassified**, not resolved by later200s. |
| WP6B-MONEY-ALLOC-001 /P1 | Independent per-line paise rounding loses/duplicates recorded deductions (one paise split equally can become two zeros). Zero-total weights previously repeated the deduction for every item. | Decimal largest remainder, stable tie order, conserved known total; zero-basis amount retained once with explicit missing allocation basis/UNKNOWN profit. Persisted canonical projection and literal independent expectations. |
| WP6B-MONEY-POLICY-001 /P2 | Percent quantize implicitly used HALF_EVEN unlike money HALF_UP; private monetary helper returned0 for None. | Explicit HALF_UP; UNKNOWN rejects422. Nullable evidence paths preserved. Projection policyv2 preserves prior-version working snapshots. |
| WP6B-CAPTION-001 /P1 | Two identical caption forms, both unbound; Add track submitted hardcoded `Reviewable caption cue` instead of the entered text. | One existing labelled form bound to captionText; submit trimmed actual text; disable/reject missing text/locale. Same canonical review API, no auto-approval or provider execution. Angular request-body and browser inert-edit coverage. |
| WP6B-ARIA-001 /P2 | `.quick-actions` labelled generic div lacks an appropriate role; six original axe incomplete occurrences. | Add group role, preserve six actions and accessible name; actual browser semantics/keyboard checks. |
| WP6B-TABLE-001 /P2 | Video empty row spans9 columns under8 headers. | Correct colspan8 and explicit column scopes; original content retained, structural regression and browser review. |
| SE-WP5-PRICE-001 /P2 | Raw sub-paise source versus two-decimal order projection is a storage/rounding boundary, not FX. | Preserve source and existing scales; document precision policy and reconciliation limitation; no invented historical digits. |
| QA-P3-GAP-001 /architecture risk | Finance same-scope/version snapshots overwrite metrics/lineage. | Correct model documentation, preserve older-version row during v2 calculation, explicitly distinguish projections from immutable accounting; no ledger implementation. |

Caption coverage does not certify caption creation against a generated real video:
the exact existing API body is unit-tested; the browser edits the inert draft input
with no selected generation and cannot queue it. No fabricated render is used to
claim a supported provider journey. Full provider/generation/approval certification
remains outside this local work package.

## Ads502 evidence-backed disposition

Actual router `ads/optimization_router.py:provider_comparison` delegates to
owner-scoped SQL `compare_providers` in `ads/optimization.py`. This read does not
call an external advertising provider. The old missing campaign columns caused
500s, but that does not prove the isolated502 cause.

The QA reverse proxy in `qa/server.mjs` previously emitted an empty502 on native
upstream request error. That is consistent with the old trace but is **not proof**
that the historical error was ECONNRESET, a timeout or schema-related. No raw
historical socket/exception data exists to resolve that uncertainty.

Future QA transport502s now carry allowlisted `X-QA-Error-Origin` and
`X-QA-Transport-Code` headers plus a safe generic JSON error. Raw exception messages,
credentials, query strings, request arguments and stderr are not persisted. A
local Node test actually stops/restarts its own synthetic upstream: application500
passes through unchanged; refused/reset transport is identified as QA proxy502;
the next healthy request recovers200. This does not modify production nginx.

Disposition: **P2, unreproduced historical reliability observation, explicitly
deferred for broader stress/recovery testing**, not an open untriaged application
P1 and not falsely closed. Exact accepted replay attempt counts are in browser report.

## Historical schema/index classification

Fresh signed read-only inventory:42 tables,712 columns, no absent canonical ORM
columns at head149. Every one of105 missing ORM index names is individually listed
and classified in the retained `wp6b-schema-review.json` and final gate data:

-26 have an existing nonpartial index/unique/PK left-prefix access path: maintainability/
  naming debt, not26 proven missing indexes. Operator classes/order/collation/unique
  semantics and query plans are not certified by a prefix comparison.
-79 lack that evidence: deferred reliability/performance risk, **not** proven slow
  or incorrect merely from a name difference. Need representative load/EXPLAIN before
  adding indexes; blanket creation would add write/storage cost without evidence.
-Three nullable mismatches (`audio_mode`, `request_snapshot_json`,
  `source_media_ids_json`): nonblocking historical constraint risk in the demonstrated
  workflows. Fresh NULL counts0 do not prove historical rows are safe to tighten.
  No unsafe backfill or NOT NULL migration. Bulk provider workflows remain unexecuted.
-Three Float/DOUBLE PRECISION renderings: PostgreSQL Alembic type comparison confirms
  equivalence; nonblocking representation issue, not a monetary floating-point fix.

No active schema correctness defect was demonstrated in these remaining entries.
This is not repository-wide schema, performance or historic-data certification.

## Architecture and safety

See [precision/history decision](wp6b-financial-precision-policy.md): estimates and
mutable projections are not verified transactions or immutable accounting history.
Sole-accounting use remains blocked; no general ledger is authorized.

Only attested `vayujit-qa-postgres`, instance389b97d2-a4cd-4d9b-972e-6bb2bf5785eb,
loopback55432, non-superuser QA role and signed marker/owner/OID-scoped disposable
databases used. WP6B inherits the exact WP6A local preparation allowlist, not live
execution permissions. Golden/permanent data, external writes, credentials and
the parked PC-first backup work remain untouched. No branches, commits or pushes.

Some normal disposable drops were interrupted with OperationalError at the guarded
DROP statement. Exact-token signed resume (same identity/owner/OID, marker lineage,
no active sessions, no FORCE/termination) recovered them. Reports retain original
nonzero runner exits; assertion passes are distinguished from cleanup outcome.
This is QA infrastructure reliability debt, not a license to delete guessed targets.
Final independent absence/isolation evidence is required before any GO recommendation.

Bounded reproduction of the same signed interrupted DROP under the original15s
limit returned SQLSTATE57014 after16.5s. The configured query deadline cancels the
operation; why host deletion takes longer is not established. The WP6B runner now
explicitly requests a90s deadline **only for its guarded DROP connection**. All
other runs retain the15s default. Both values remain bounded15–90s; no global
server/role setting, marker/owner/OID check, active-session refusal, FORCE policy
or fail-closed behavior changed. Three new safety regressions verify invalid
deadlines never reach SQL, normal extended deletion retains marker/identity checks,
and active sessions still prohibit deletion. Old failed reports remain unchanged.

## Changed files

Production: `commerce/money.py`, localized `commerce/financial_router.py`, truthful
`commerce/financial_models.py` docstring; `ai/ai-video.component.ts` and spec.
No source event rewrite, persisted numeric schema change, financial approval bypass
or arbitrary fee/currency conversion introduced.

QA: `scripts/test-seller-wp6b.ps1`; `qa/wp6b-browser-retest.mjs`,
`wp6b-accessibility.mjs`, `wp6b_schema_review.py`, `wp6b_final_audit.py`,
`unit/wp6b-safety.test.mjs`; `apps/api/tests/test_seller_wp6b.py`;
bounded additions to existing fixture allowlist, session/exploration helpers,
proxy diagnostics, phase policy and read-only audit package selector.
The same scoped QA correction updates `qa/postgres_instance.py`,
`qa/unit/test_postgres_instance.py` and the fixture's reported DROP deadline;
mechanical string wrapping/environment-variable casing in that QA module also
meets project lint without changing its Windows identity checks.
Five required WP6B reports plus explicit status addenda preserve prior evidence.
