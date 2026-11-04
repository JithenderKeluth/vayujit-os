# WP3 — Supplier, sourcing and profitability remediation

Date: 2026-10-29. Scope: one owner, synthetic disposable PostgreSQL only.
Application certification remains **INCOMPLETE**. No live supplier/provider,
marketplace, purchasing or backup certification is implied.

## Scope selected from the actual ledger

WP1 resolved 001–004; WP2 resolved 005/008/011/014. Of the twelve remaining
original findings, WP3 addresses **SE-BROWSER-006/007/013/015/016**. The other
seven (009/010/012/017/018/019/020) are preserved, not silently closed.
The separately suspected Advanced-link contrast issue is not globally certified.

Read the [browser retest](wp3-browser-retest.md) and machine-readable
[resolution ledger](wp3-resolution.json) for the accepted execution and limitations.
Historical audit observations, screenshots, failed attempts and WP1/WP2 reports
are retained; their historical counts have not been rewritten.

## Browser-first evidence and root causes

The before-change replay used actual authenticated Chrome, the production Angular
bundle and canonical APIs on migrated, marked disposable installations. It did not
intercept provider data to manufacture supplier or financial success.

| Finding | Confirmed root cause | Bounded correction |
| --- | --- | --- |
| 006 Catalog currency | Template ignored canonical `base_currency`. | Prefer that field; preserve UNKNOWN when absent and link to the exact opportunity. |
| 007 shortlist count | Operations were read only at initial load, before context/evaluation/HUMAN decision writes. | Re-read authoritative counts after saves. Refresh failure renders UNKNOWN without undoing a saved decision. Block duplicate pending clicks. |
| 013 Suppliers destination | Primary Suppliers pointed at the later-stage sourcing/RFQ form. | Open actual supplier discovery; expose Requirements & quotes separately. Existing routes/authorities remain. |
| 015 economics hierarchy | Live-acquisition controls dominated local costing; raw persisted dictionary strings were printed as seller explanations. | Decision-facing summary, real section links and progressive disclosure. Plain-language evidence labels with exact original detail retained. No parsing dictionary strings into business facts or rewriting readiness fingerprints. |
| 016 financial display | Raw decimal strings and ratio were displayed directly. | Exact-string/BigInt display rounding, Indian grouping, explicit currency, ratio-to-percent presentation. Stored decimals and calculations are unchanged. Exact values remain available. |

Before fixture `c664f26be17f72e7` measured 12,080px desktop / 29,885px mobile.
This is the WP3 baseline, not the older audit's different 42,933px fixture. The
before report's `rawDictionaryWarning:false` detector missed the actual
`source_references` spelling; retained page text/screenshots establish the raw
dictionary observation. That faulty detector is not used as a passing assertion.

## Closely related defects found and corrected

### Local quotation identity and response envelopes

Authenticated before replay `8d0cfff3b3f4abeb` returned **422**, not the harness's
initially expected 404: `product_id` was an empty UUID string. Source tracing also
showed canonical ProductOpportunity IDs sent into the *legacy* opportunity field,
and the UI reading an RFQ `{rfq: ...}` response as though the ID were top-level.
The original failed expectation and trace are retained, not relabelled PASS.

The UI now resolves the owned ProductOpportunity's existing Catalog Product ID.
It resolves supplier source IDs through existing canonical supplier identity and
product-research projections, never by substituting a canonical ID into a legacy
Supplier FK. Missing Catalog lineage or unrelated suppliers block preparation.
Multiple source identities remain explicit choices; no supplier or quote is
automatically chosen. Existing owner-scoped backend authorities validate writes.
Research records are labelled AVAILABLE FOR REVIEW, not HUMAN-shortlisted. Multiple
source records are not presented as proof of independent supplier companies or
supplier concentration; the canonical identity/portfolio authorities remain separate.

Requirements, saved local RFQs and quotations are scoped to the product. The
current requirement version is used. The exact selected pricing draft is carried
in the URL and restored on reload. Unknown price/MOQ remains blank; decimal price
entry is supported. Expiry is optional and unknown/expired terms are labelled.
Seller-entered quotes are unverified and are **not** automatically imported as
the economics cost basis. A local draft remains `not_sent`, with no approval.

Identical quote requests use stable content-derived replay keys, including after
reload. Changed replay material returns 409. PostgreSQL transaction locks serialize
exact-key replay and quote-version allocation; a concurrency collision cannot
silently return another request's version. Immutable quote snapshots, source
lineage, approval controls and arithmetic are preserved. No migration is needed.

### Empty economics contract and rendering error

Review of retained console evidence exposed a genuine in-scope error that journey
assertions alone missed: the no-calculation projection omitted
`scenario_comparisons`, but Angular read `.length`. The compiled template location
and producer were traced. Both no-context and no-calculation responses now return
empty comparison collections and explicit null calculations/unit economics.
Readiness stays NOT_EVALUATED and gaps remain; no zero-price or READY result is
invented. A persisted regression covers both states.

The QA gate now rejects Angular **console** errors as well as uncaught page errors.
Earlier 16-check reports are not accepted as clean certification because their
console contained this error. Only the deliberately injected exact-route 503 and
an actual GET `/auth/me` 401 while on anonymous `/login` are classified expected;
unit tests prove protected-page 401s and TypeErrors still fail.

### Scope, freshness and converted currency

Saving a supplier economic context is an explicit prerequisite for loading its
brief. The formerly enabled no-op now explains how to recover. A missing supplier
calculation never substitutes a product-wide model. Query-scope changes reset
supplier/quote/decision inputs and stale asynchronous scope reads are discarded.

Backend-converted selling-cost `per_unit_amount` is labelled in **model base
currency**, not original component currency. Dedicated display tests cover this,
unknown conversion and zero. This is source-contract/unit coverage, not a claim
of FX-provider or FX-specific browser certification. Stale acquisition handling
and recalculation authorities were reused, not rebuilt.

## Changed files and architecture impact

Production backend:

- `apps/api/vayujit_api/intelligence/sourcing_service.py` — exact replay material
  checks and transaction locks; no schema or financial-formula change.
- `apps/api/vayujit_api/intelligence/economic_integration_service.py` — stable empty
  projection shape only. Earlier WP1 edits in this already-dirty file are preserved.

Production Angular:

- `shared/seller-navigation.component.ts` — discovery versus local quote navigation.
- `catalog/catalog-workspace.component.ts` — currency/context and honest manual-lineage guidance.
- `intelligence/cross-marketplace-supplier.component.ts` — existing manual-register
  and local quotation paths, with prerequisites and provenance explanation.
- `intelligence/supplier-shortlisting.component.ts` — authoritative summary refresh.
- `intelligence/sourcing-workspace.component.ts` and `intelligence.service.ts` —
  scoped existing quotation authorities, response envelopes, replay, reload and errors.
- `intelligence/sourcing-economics-workspace.component.ts` — hierarchy, section
  navigation, prerequisite feedback, and view-only formatting.
- New `seller-financial-format.ts` and `economic-evidence-note.component.ts` —
  reusable presentation, not duplicate financial or approval business logic.

Regressions and executable QA:

- `apps/api/tests/test_seller_wp3.py` (7 persisted tests).
- New Catalog economics presentation, financial-format and evidence-note specs;
  updated navigation, shortlist, sourcing and economics Angular specs.
- `qa/wp3-fixtures.mjs`, `wp3-before.mjs`, `wp3-sourcing-before.mjs`,
  `wp3-browser-retest.mjs`, `wp3-reporting.mjs`, `unit/wp3-safety.test.mjs` and
  read-only `wp3_final_audit.py`.
- `scripts/test-seller-wp3.ps1`, `qa/fixture_server.py` explicit test-file allowlist
  and `qa/safety.mjs` narrow local requirements/RFQ-draft/quote write allowance.
  Dispatch, approvals, workers and external origins remain denied.

The repository already contained unrelated work, including parked backup changes.
This list describes WP3 edits, not ownership of the entire dirty worktree.

## Remaining limits and decisions

- Manual Catalog products are not invented researched opportunities. A Product-only
  EconomicContext and missing-cost calculation are persisted-API tested, but the
  complete seller-facing manual-product quote/cost-input editor is still a coverage/
  UX gap. Full opportunity profitability/HUMAN decisions require genuine lineage.
- Existing manual supplier entry is linked, with provenance/verification warnings.
  Automatic manual-supplier-to-selected-product association is not invented or
  certified. This fixture exercises discovery-related identities, not that separate path.
- Legacy quotation comparison alone checks currency; it does not establish matching
  commercial units, freight, tax, expiry or verified terms. No automatic winner or
  cost import is introduced. Fully compatible real quotations remain unverified.
- No live discovery, real supplier evidence, marketplace fee schedule, GST treatment,
  provider authorization or two-real-supplier commercial comparison is certified.
- Keyboard Enter, focusable disclosure/links, reload and responsive overflow were
  exercised. Comprehensive assistive-technology/manual WCAG certification remains out
  of this bounded result. Do not close historical cross-application accessibility findings.
- Strict mypy for the legacy sourcing service still reports 29 existing diagnostics;
  an untouched HEAD shadow-file run reports the same 29 categories/functions. New
  replay helpers are typed. Projection strict mypy passes. Debt remains relevant to
  future maintenance, but was not hidden or disabled to obtain a green report.
- Production build retains the existing 500kB initial-bundle warning (518.25kB).
- Four interrupted disposable drops required exact-token guarded recovery during
  concurrent QA activity. Original failed cleanup records remain; independent
  absence/signature checks, not edited exit codes, establish eventual cleanup.
  The retained diagnostic is OperationalError at guarded DROP; its exact PostgreSQL
  error text was not retained. A longer bounded recovery timeout succeeded, but
  the precise initial database-error cause is not asserted as proven.

Stop after WP3. No new milestone, permanent database, production activation,
supplier contact, RFQ dispatch, provider calls, commits, pushes or branches.
