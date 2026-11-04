# QA Agent Phase 2 - persisted seller journeys and financial correctness

This extends Phase 1. It is a test system, not an autonomous production fixer.
The original Phase 1 report and findings remain historical evidence, not silently
replaced or closed by a later run.

## Actual authorities reused

| Journey segment | Existing authority | Phase 2 exercise |
| --- | --- | --- |
| Candidate and constraints | ProductOpportunity APIs and assessment versions | Manual, explicitly synthetic bottle candidate; capital/category constraints |
| HUMAN product selection | Assessment score and decision APIs | Authenticated explicit shortlist, no automatic sourcing approval |
| Supplier association | Provider-neutral `LOCAL_FIXTURE` supplier research | Persisted source, evidence and product link; replay; no website acquisition |
| Supplier review | Cross-marketplace reconciliation and shortlist contexts | One synthetic supplier, unverified lineage, HUMAN `KEEP_UNDER_REVIEW` |
| Due diligence | Canonical DD assessment and context ledger | Missing evidence remains gaps; no waived controls or supplier contact |
| Costs and economics | Commercial readiness, PR-5B landed cost, PR-5C unit economics | Explicit scenario assumptions, independent Decimal oracle, reload and history |
| Tax arithmetic | Existing customs/tax contexts, rate evidence and snapshots | Arbitrary assumed rate and explicit taxable basis; NOT verified Indian GST |
| Business decision | Recommendation/HUMAN decision and Commerce Journey APIs | Ineligible Proceed, explicit review, replay, persisted history, unauthenticated/AI rejection |
| Catalog handoff | Canonical opportunity conversion and product API/form | Real persisted conversion, INR edit/cancel, keyboard submission, immutable scenario history |

Discovery here begins with a manual synthetic candidate. Live product discovery,
category/cache correctness, multiple suppliers and switching are NOT certified.
The reused supplier fixture actually describes insulated water bottles. QA uses
that product context rather than attributing it to an unrelated kids lunch box.

## Execution architecture and isolation

`npm.cmd run qa:phase2` uses the existing runner, production Angular build,
fresh token-marked PostgreSQL database, actual authenticated API, proxy and Chrome.
Each viewport receives a different disposable database. No test fixture reuses a
business/golden database. The API test process is separate from the API server;
its database verification uses a read-only transaction and checks both the exact
database name and marker before querying persisted Decimal values and DD lineage.

Phase 2 enables only the existing `LOCAL_FIXTURE` supplier mode in the test API
process. Both external research kill switches and the external-mutation emergency
stop remain enabled. The canonical fixture URL validator performs DNS validation
even for supplied text. Therefore the QA network guard returns a synthetic public
IP only for the exact `example.org` fixture hostname, without DNS/network access.
All socket connections to that address remain denied. No source safety function
or authentication dependency is replaced. Tests prove the DNS exception is opt-in,
does not include subdomains, and cannot enable external TCP connections.

The proxy permits a narrow preparation/assessment allowlist. Supplier research
also requires a parsed body with `mode: LOCAL_FIXTURE`; LIVE_READ_ONLY, missing
mode and provider-neutral alternatives fail closed before reaching the API.
No worker, publishing, RFQ, marketplace or financial transaction endpoint is allowed.

As in Phase 1, disposable schemas use ORM metadata, NOT migration replay. This is
explicitly not migration certification. Only guarded database creation/marker and
cleanup use infrastructure SQL. Business fixtures use canonical application APIs.
No Docker stop/down, volume deletion or PC-first backup script is invoked.

## Independently calculated financial expectations

Rules were traced to `landed_cost_service.py`,
`product_opportunity_unit_economics_service.py`, `economic_customs_service.py`, and
`economic_calculation_service.py`, not inferred from planning documents.
`qa/financial_oracle.py` imports none of those calculation functions.

For the explicit same-currency scenarios, eight decimal places use ROUND_HALF_UP:

- Landed total = unit acquisition cost x quantity + explicit shipment freight.
- Landed/unit = rounded landed total / quantity.
- Modeled selling/unit = selling price x explicit percentage / 100 + explicit
  per-order amount / modeled quantity + explicit per-unit amount.
- Contribution/unit = selling price - rounded (landed/unit + selling/unit).
- Contribution margin = contribution / selling price, a fraction, not percent.
- Upfront capital = rounded landed/unit x quantity, as the current contract defines.
  It excludes future selling costs; no sales velocity, safety buffer or net profit
  is inferred. Negative contribution and capital shortfall must not become zero.

Reference case: cost INR 100.125, freight INR 2500, Q=500, sale INR 250,
hypothetical 10% selling cost and INR 50 per modeled order: landed/unit 105.125,
selling/unit 25.1, contribution 119.775, margin 0.4791, upfront capital 52562.5.
The percentage is a QA input, NOT an Amazon or Flipkart fee schedule.

The customs engine expresses rates as FRACTION_OF_ONE, unlike the unit-economics
percentage component. An explicit assumed 0.075 x INR 1234.56 produces INR 92.592.
Unknown basis must be excluded, not zero. Its separate canonical context avoids
overriding PR-5B's explicit UNKNOWN components, which have documented precedence.
This proves arithmetic, not GST applicability, input-tax credits or legal eligibility.

## Reporting and evidence

`qa/phase2_api.py` writes individual API outcomes, a synthetic artifact manifest,
supplier evidence, stale-input observations, tax calculations and database proof.
`qa/tests/phase2.spec.mjs` records routes, HTTP failures, console/page errors,
screenshots, retained failure traces and actual axe output. No axe rule is disabled.
Serious/critical findings fail the scenario; a functionally successful scenario
can therefore still FAIL accessibility. Keyboard scope includes product-cost focus,
Tab/Shift+Tab, Cancel with Enter and Save with Space, not complete keyboard conformance.

`finding-v2.schema.json` extends the compatible Phase 1 schema with required area,
journey and business impact. Assertion failures start SUSPECTED; confirmed defects,
subjective usability recommendations and coverage gaps remain distinct.

Generated outputs: `phase-2-report.json`, `phase-2-report.md`,
`phase-2-coverage.json`, `defect-backlog.json` and the Phase 2 section in the
shared coverage matrix. Raw evidence remains under ignored `tmp/qa-agent/<token>`.
Do not publish synthetic session traces or arbitrary raw subprocess logs.

## Windows execution

From the repository root, use an already available local disposable PostgreSQL
administrator. Do not point this variable at a business database or change `.env`.

```powershell
$env:QA_DATABASE_ADMIN_URL = 'postgresql+psycopg://<test-admin>:<password>@127.0.0.1:5432/postgres'
npm.cmd run qa:phase2
npm.cmd run qa:unit
apps/api/.venv/Scripts/python.exe -m unittest discover -s qa/unit -p 'test_*.py'
npm.cmd run test:web
```

The runner uses existing installed Chrome, Playwright, axe-core and Python tooling.
No paid service, new dependency or live credential is needed. A nonzero suite exit
is expected while application assertions remain open; never relabel that PASS.
Read `cleanup` in the report to confirm each exact disposable database is absent.
The standalone Node proxy regression explicitly skips if no Angular build exists;
the main Phase 2 runner always builds first. Such a skip is not a successful test.

## Recommended Phase 3

1. Authorized remediation and retesting of demonstrated financial, replay and
   accessibility defects; preserve canonical approvals rather than relax assertions.
2. Migration-driven fixtures, multiple-supplier switching and explicit context
   changes, stale HUMAN approvals and cross-installation foreign IDs.
3. Deterministic orders, fees, refunds and settlements oracles using actual domain
   rules, effective dates and precision; concurrency/overselling tests.
4. Broader keyboard, focus restoration, screen reader review and mobile task-flow
   tests. Real providers remain a separately authorized certification milestone.
