# PR-SOS-08 — Authorized Amazon India & Flipkart Connectivity

## A–Z local validation report

**Scope.** This milestone implements the authorized local/read-only portion of
PR-SOS-08. It does not authorize seller-account OAuth, real Amazon SP-API or
Flipkart API calls, supplier activity, RFQs, payments, fulfilment, refunds,
listing publication, inventory/pricing writes, golden-database changes, commits,
or pushes.

**A — Authority audit.** Existing `MarketplaceAccount`, provider connector,
Catalog, `MarketplaceListing`, `MarketplaceOrder`, `MarketplaceInventory`,
`MarketplaceSettlement`, Financial, Action Center, and single-owner authorities
remain canonical. `MarketplaceImportJob` is only a durable execution/evidence
ledger; it is not a second catalog, order, inventory, or financial authority.

**B — Business journey.** The supported local path is Connect account → inspect
capabilities → run a synthetic read-only import → inspect durable evidence →
review reconciliation exceptions. External provider activation is an explicit
HUMAN/deployment boundary.

**C — Capability classification.** Amazon and Flipkart are marked
`repo_supported=true` and `synthetic_fixture=true`; official provider
contracts are `UNVERIFIED`; sandbox and live read-only are
`NOT_CONFIGURED`; live write is `DENIED`. No official seller certification is
claimed.

**D — Durable data.** Migration `20261203_0146` adds owner/account-scoped
import jobs with operation, mode, status, correlation ID, checkpoint, safe
summary, provenance, record counts, errors, completion, and stale timestamps.

**E — Encryption and privacy.** Existing account credential encryption and
write-only responses are reused. Import responses contain no credentials or raw
provider secrets; buyer data remains under existing masked order projections.

**F — Fail closed.** `SANDBOX` and `LIVE_READ_ONLY` requests return 409 with an
authorization-required message and `X-VAYUJIT-External-Write: denied` until a
separately authorized transport exists. No job is created for blocked modes.

**G — Idempotency.** `(owner, account, operation, idempotency_key)` is unique.
Replaying a synthetic import returns the original durable job and does not
duplicate the canonical order or settlement.

**H — HUMAN boundaries.** Account validation remains the existing explicit
operation. Synthetic validation reports `UNVERIFIED`; it never turns a local
fixture into a real `CONNECTED` seller account. Canonical listing/HUMAN
approval authorities were not bypassed.

**I — Import operations.** Catalog imports reuse category/listing projections;
order imports reuse `import_fake_order`; inventory imports record provider
observations without overwriting canonical quantities; financial imports reuse
`import_fake_settlement` and settlement-line evidence.

**J — Job recovery.** Jobs retain checkpoints and safe error fields. Completed
jobs cannot be cancelled. Partial/retry worker execution remains a future
provider-activation concern; this synchronous synthetic path has no network
retry loop.

**K — Kill switch and transport.** Existing emergency-stop, provider runtime
mode, origin, credential, and safety middleware remain in force. No outbound
request is made by `SYNTHETIC` imports.

**L — Lineage.** Every completed job preserves provider, account, mode, source,
capture time, correlation ID, operation, checkpoint, and canonical authority in
safe JSON fields.

**M — Migration.** A fresh marked disposable PostgreSQL database upgraded from
the repository base to `20261203_0146 (head)` successfully. The previous
`vayujit_golden_test` database was not touched.

**N — Navigation/UI.** `/marketplaces/accounts` now acts as the Connection
Center: it shows connection/permission/transport state, synthetic import
buttons, durable import history, stale-operation summary, and the next manual
reconciliation action.

**O — Owner isolation.** All account, job, detail, and reconciliation queries
include the authenticated owner and account. Unknown or foreign IDs return 404.

**P — Provider differences.** Amazon and Flipkart remain separate adapter
implementations behind the common connectivity contract. The capability matrix
does not imply identical official APIs or permissions.

**Q — Quality checks.** Focused Ruff and Black checks pass for all new/changed
Python implementation and test files. Type-checking and repository-wide static
checks retain the pre-existing unrelated dirty-tree findings; no new broad
refactor was attempted.

**R — Reconciliation.** The endpoint reports canonical listings, inventory,
orders, settlements, latest and last-failed jobs, per-operation freshness,
import counts, exceptions, stale operations, and a manual next action. The
Connection Center renders those counts and freshness states. It never silently
overwrites local stock, status, price, or financial values.

**S — Security.** External modes fail closed; credentials are not serialized;
authorization is owner-scoped; live write is denied; and synthetic summaries
explicitly state `external_writes=false`.

**T — Test evidence.** Focused PR-SOS-08 integration coverage includes
capability classification, all four synthetic operations, idempotency replay,
external-mode replay protection, reconciliation freshness/counts, blocked
external modes, owner/job isolation, detail reads, and completed-job
cancellation. The final focused suite produced **5 passing scenarios** on the
initialized disposable PostgreSQL database. An earlier aggregate attempt
exposed the existing fixture’s stale-session teardown race; the final rerun
completed successfully.

The adjacent Action Center regression also passed **4/4** after the new
marketplace-import warning projection.

**U — Angular evidence.** The Accounts/Connection Center UI and typed service
methods are covered by **63 test files / 224 tests passed**, the production
build, and lint. The UI is responsive through the existing shared marketplace
breakpoints and uses visible focus styles, semantic tables, status text,
freshness/exception summaries, and `aria-live` completion feedback.

**V — Validation limits.** No authenticated browser session against a running
API/web pair was used for a live seller account because no provider credentials
or external authorization were supplied. Browser/axe certification of the new
controls therefore remains a local follow-up gate, not a claimed live-provider
pass.

**W — Write boundary.** No listing publication, inventory mutation, order
acknowledgement, fulfilment, refund, payment, supplier contact, RFQ, or
marketplace external write occurred.

**X — Exceptions.** Official Amazon/Flipkart contract verification, OAuth/token
refresh, real pagination/rate-limit semantics, provider webhooks, and sandbox
certification remain unverified. Existing repository-wide historical Ruff,
Black, mypy, and bundle advisory findings are outside this bounded change.

**Y — Activation checklist.** Before any external activation, a HUMAN must
  (1) approve provider terms and regions; (2) configure provider-specific OAuth
  or credentials in the approved secret manager; (3) verify scopes and seller
  identity; (4) configure a provider transport allowlist and rate/retry policy;
  (5) run a sandbox/read-only certification; (6) review import evidence and
  reconciliation exceptions; and (7) separately authorize any future write
  milestone. Until then keep `SYNTHETIC`, external writes denied, and account
  state `UNVERIFIED`.

**Z - Historical 08.1 classification.** The earlier API-only report retained
`IMPLEMENTED / LOCAL CERTIFICATION PENDING` while the browser harness was
blocked. That status is superseded by the PR-SOS-08.2 closure below; real
Amazon/Flipkart connectivity remains separately uncertified.

## Business Agent integration

The existing read-only Action Center now projects failed/partial or stale
`MarketplaceImportJob` evidence as owner-scoped HUMAN-review signals linking
back to the Connection Center. It never mutates catalog, order, inventory, or
financial records.

## PR-SOS-08.1 certification closure

The browser/accessibility/regression closure is maintained in
[`pr-sos-08-2-validation.md`](pr-sos-08-2-validation.md). The local synthetic
connectivity milestone is now fully validated: 35/35 browser assertions,
12/12 axe states with zero violations, focused and adjacent PostgreSQL
regressions, Angular tests/build/lint, migration head, and static checks all
passed. No real provider call is claimed.

**PR-SOS-08 - FULLY VALIDATED (LOCAL / SYNTHETIC MARKETPLACE CONNECTIVITY /
NO REAL PROVIDER CALLS).**
