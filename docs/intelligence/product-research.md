# Product Research Slice 1

## Business Agent live discovery and source review (2026-10-24)

The historical foundation classification below is not a live-provider certification.
The current Business Agent can run bounded `LIVE_READ_ONLY` discovery through the
configured provider, subject to the existing source policy and product identity gates.

- Explicit categories without a matching canonical concept use a category-led search
  scope. Household fixture concepts must not be relabelled as unrelated categories.
- Search results and category seeds are discovery inputs, never accepted product evidence.
- Missing source approval is reported as `SOURCE_APPROVAL_REQUIRED`. The Business Agent
  shows recorded queries, page outcomes, and a **Review blocked sources** panel, including
  for older runs whose stored failure message was generic.
- A HUMAN must review robots, terms, and access permission and explicitly
  approve each permitted domain. The panel uses the existing authenticated
  `POST /api/v1/intelligence/external/source-profiles/admit` authority with `HUMAN`
  provenance. The required audit purpose is recorded automatically; an additional policy
  review note is optional. No approval or fetch is performed on page load.
- Approval is owner-scoped and durable for the domain and its subdomains (including future research), not
  proof of product identity or permission for supplier contact. Unknown/prohibited policies
  must stay unapproved. Network, redirect, kill-switch, and product eligibility controls remain.
- Discovery selects the most specific enabled/approved owner source profile. A later
  explicit retry uses normal search reuse and normal fetch validation; approval itself
  never starts discovery. Existing canonical approvals are reloaded on refresh.
- Fetch attempts, successful new fetches, and successful reused fetches are separate.
  Blocked attempts are not reported as fetched pages. Old inaccurate counters are not used
  by the review panel.
- Current-run canonical candidates are projected even if a subsequent step budget stops
  execution. Unrelated owner history must not appear as this run's candidates.
- The live branch returns a blocked outcome only when no canonical product was found.
  Previously it returned unconditionally, leaving a successful retry `RUNNING` with an old
  source-approval failure. The disposable replay explicitly rejects that stale outcome.

### Operator sequence

1. Restart the local API if reload is not active and refresh Business Agent.
2. Keep the explicit category goal. For a run made before this repair, retry discovery once
   to generate the corrected category-led queries. Do not approve unrelated historical sources.
3. If source approval is required, review the newly discovered source/page and its policies.
   Approve only permitted access using the panel; do not disable source approval in `.env`.
4. Choose **Continue product discovery** after source review (or **Retry failed discovery**
   when resolving another discovery blocker). This rechecks evidence through canonical authorities.
5. Review any accepted candidates in **Product opportunities**. Product selection remains an
   explicit HUMAN decision before supplier continuation. No successful result is guaranteed.

### Verification scope

Focused offline tests cover category scope, raw-goal precedence, approval-required outcomes,
other security rejection reasons, distinct fetch counters, canonical profile selection,
authenticated approval replay, search reuse, persisted product/fetch lineage, current-run
candidate isolation, and unauthenticated denial. Angular tests cover the source-review panel,
failed approvals, refresh, changed-domain confirmation reset, safe links, and legacy messages.
An axe component scan excludes color contrast because it runs in jsdom; it is not a complete
WCAG or real authenticated Chrome certification. No live provider call or real-domain
approval is part of this repair's tests. No migration or environment change is required.

Recorded local results (2026-10-24):

- Backend unit/provider/quota regressions: **104 passed**.
- Canonical PostgreSQL source-review integration: **1 passed**, including denied access
  before approval, disabled-profile denial, explicit re-admission, idempotent approval,
  search reuse, one transport fetch, canonical product persistence, fetch lineage,
  current-run history isolation, and unauthenticated denial.
- Adjacent Business Agent/supplier regression run: **19 passed, 1 failed**. The unchanged
  `test_provider_neutral_supplier_research_local_fixture_is_bounded_and_replayable`
  expects `LIVE_READY` while the isolated fixture forces `LOCAL_FIXTURE` and the canonical
  readiness API returns `LIVE_CONFIGURATION_INCOMPLETE`. It fails before discovery is
  invoked. This separate readiness-fixture assertion was not changed and live protections
  were not enabled to make it green.
- Full Angular suite: **238 passed across 65 files**. This includes the source-review axe
  component scan (no serious/critical findings in its tested scope; contrast excluded).
- Changed-file ESLint, application/test TypeScript, Ruff, Black, focused strict mypy
  (seven Python sources), compileall, and `git diff --check`: passed.
- Production Angular build: passed with an initial-bundle warning (**514.48 kB** against
  the **500 kB** warning threshold; below the 1 MB error threshold).
- Real authenticated Chrome layout/keyboard certification and real Brave discovery were
  **not executed** for this repair. No live success or platform-wide certification is claimed.

Reproducible focused backend checks (use the normal marker-protected disposable test
database runner, never the golden or business database):

```powershell
npm run test:api:integration -- -TestPath tests/test_product_source_review_integration.py
```

Focused Angular checks from `apps/web`:

```powershell
npx ng test --watch=false --include="**/product-discovery-review.component.spec.ts" --include="**/business-agent-workspace.component.spec.ts"
```

## Discovery usability and cache corrections — 2026-10-25

These corrections supersede the older approval-form and cache-reuse behavior above; they
do not constitute a live-provider or platform-wide certification.

- **Optional note, mandatory consent:** the UI displays the standard audit purpose
  `Read-only product discovery requested by the workspace owner.` and appends any optional
  note. The canonical API still receives a nonempty reason. All three policy confirmations,
  authenticated HUMAN admission, domain scope, and existing safety controls remain required.
- **Approval is a review boundary:** waiting source review uses a warning state and one
  **Continue product discovery** action rather than duplicate failed-step/resume actions.
- **No approval for obvious non-products:** search, marketplace home/category, supplier
  directory, policy, and obvious editorial URL surfaces are skipped before fetching or
  requesting approval. Nested concrete product paths remain eligible for normal fetch and
  identity checks; passing this URL filter never establishes a product identity.
- **Historical evidence stays intact:** the read-only API review projection marks old
  non-product attempts as ineligible for approval and adds current guidance. Original
  recorded failures and evidence are not rewritten or deleted.
- **Safe failure diagnostics:** known fetch failures, including `dns_rebinding_blocked`,
  propagate through an allowlisted code and safe explanation. Unknown native/provider
  output is not exposed. Approval cannot override DNS, IP, redirect, or other network guards.
- **Shared cache lineage:** reuse now reconstructs canonical results using the existing
  owner-scoped search execution's ordered `result_ids`. A result shared by multiple queries
  no longer disappears from the second query merely because it has one original parent.
  Legacy requests without a completed execution retain their original parent-based lookup.
- **Bounded recovery:** a third plain-language retail/product-specification refinement is
  available only within the existing configured query limit. No forced refresh, increased
  budget, unbounded cache retry, fabricated page, or relaxed identity gate is introduced.
  Pending source approval stops further searches until explicit user continuation. Fully
  reused, exhausted plans report `CACHED_QUERY_PLAN_EXHAUSTED`, not new provider spend.
- **Truthful counts:** search attempts, reused searches, new search executions, skipped
  non-product pages, actual fetch attempts, and successful fetches are distinguished.

Validation actually executed:

| Check | Result |
|---|---|
| Focused backend URL/recovery/provider/quota tests | 110 passed |
| Disposable PostgreSQL approval/cache/safe-error scenarios | 4 passed |
| Search idempotency and minute/hour/day quota concurrency | 6 passed, 9 unrelated tests deselected |
| Full Angular suite | 240 passed across 65 files |
| Changed-file ESLint and application/test TypeScript | Passed |
| Ruff, Black, focused strict mypy (5 sources), compileall | Passed |
| Production Angular build | Passed; existing 514.48 kB initial bundle / 500 kB warning |
| Real Brave / supplier / marketplace calls | Not executed |
| Authenticated real-Chrome certification | Not executed |

A rollback-only/read-only inspection of the existing local run verified that its TradeIndia
directory and Amazon search URL no longer qualify for approval prompts. Each of its three
cached requests reconstructed all three recorded canonical results through execution lineage,
with **zero provider calls and zero saved data changes**. This is not proof that any of those
results survives real HTML fetching or product identity validation.

Integration tests used only the marker-protected disposable database
`vayujit_quotade6c004a_test`, synthetic canonical fixtures, and fake provider transports.
The business and golden databases were not migrated, seeded, or changed. No environment,
encryption, DNS-fetcher, ownership-model, or marketplace-execution setting was weakened.
The earlier unrelated supplier-readiness fixture assertion and existing migration lag remain
separate limitations; neither is claimed resolved by this correction.

Actual focused commands, with the guarded disposable database supplied through both
`VAYUJIT_DATABASE_URL` and `VAYUJIT_TEST_DATABASE_URL` for integration runs:

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_product_discovery_boundaries.py apps/api/tests/test_gp76_product_research.py apps/api/tests/test_external_quota_windows.py apps/api/tests/test_live_search_provider.py --no-cov -q -m "not integration and not certification_infrastructure"
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_product_source_review_integration.py --no-cov -q
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_external_true_concurrency.py -k "true_search or provider_rate_limit or expired_provider_quota or legacy_provider_quota" --no-cov -q
```

Frontend validation used `ng test --watch=false`, `ng build --configuration=production`,
changed-file ESLint, and both application/spec `tsc --noEmit` checks. The existing axe
component check passed in its jsdom scope; automated results are not full WCAG certification.

## Historical foundation scope

Slice 1 provides owner-scoped research projects, local research-run lineage, manual/source registry foundations, immutable evidence, claims, configurable deterministic rules, rule evaluations, opportunities, and explicit shortlist/reject/approve review.

Supplier directories (IndiaMART, Alibaba, TradeIndia, Global Sources), manufacturer sites, offline suppliers, trade fairs, referrals, live web research, RFQs, purchasing, and Product conversion remain future boundaries. An approved opportunity is not automatically converted into an existing Product.

Expected certification: **INTELLIGENCE CORE — LOCAL CERTIFIED**; **PRODUCT RESEARCH — FOUNDATION**; **SUPPLIER INTELLIGENCE — FOUNDATION ONLY**; **AUTONOMOUS RESEARCH — NOT YET ENABLED**; **EXTERNAL RESEARCH — DISABLED**.
