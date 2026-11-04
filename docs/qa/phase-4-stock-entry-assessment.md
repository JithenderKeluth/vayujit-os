# Initial canonical stock entry — Phase 4B implementation

The previously launch-critical UI handoff is now implemented at
`/marketplaces/inventory/opening`, reached through **Inventory → Add opening stock**.
Final certification is governed by [Phase 4B validation](phase-4b-validation.md)
and its executable [resolution ledger](phase-4b-resolution.json), not by this
source review. Whole-application certification remains **INCOMPLETE**.

## Implemented contract and architectural decisions

- Existing canonical `POST /api/v1/inventory/items`, ledger, audit and owner
  authorization remain the authorities. No duplicate ledger, approval system,
  migration, stock synchronization or marketplace operation was introduced.
- A dedicated lazy Angular screen searches owned physical Products across owned
  brands, optionally selects a matching non-archived variant, and rereads current
  stock before review. Draft physical products are eligible; archived and
  nonphysical products are rejected by the backend as well as the UI.
- SKU, location, unit, counted whole quantity and alert threshold are reviewed.
  The quantity starts empty, not zero. The API's historical default-zero contract
  is preserved for existing callers; the seller must explicitly enter a count.
  Reason remains canonically **Opening balance**; there is no source/reason input
  contract to invent. No supplier, cost, account or listing prerequisite is added.
- Strings are trimmed before validation/lookup; blank strings, noninteger/coerced
  counts and unsupported actor/source fields are rejected. Bounds remain
  0–2,000,000,000. Missing commercial information remains unknown.
- The seller reviews and checks an explicit local-count confirmation before save.
  No stock is written by selecting, reviewing, cancelling, refreshing or opening
  a deep link. Later receipts/corrections use the existing reasoned/versioned
  **Adjust stock** action, never rewriting an opening movement.
- A short transaction locks the existing owner row to serialize opening keys and
  SKU/location creation. The original normalized intent is stored in the existing
  movement provenance JSON. Exact authorized replay returns the current item
  without another movement/audit; changed intent or already initialized
  SKU/location conflicts. Legacy unambiguous keys compare the immutable opening
  movement quantity, not today's adjusted quantity; ambiguous history fails closed.
- Review/pending identity is scoped to the authenticated owner and browser tab.
  Reload never submits automatically and requires confirmation again. Transport
  timeout is bounded at 20 seconds; uncertain outcomes retain the same key and
  cannot be edited into another opening. Definitive rejections permit correction.
  A committed result whose verification fails remains pending, not successful.
- Success requires rereading the canonical item and HUMAN opening movement,
  matching the complete reviewed identity/count. The screen shows original
  opening versus current stock, movement reference and later-activity guidance.
  The audit is persisted atomically and independently checked in PostgreSQL;
  no unsupported audit-detail API or fake audit reference is presented in the UI.
- Inventory preserves SKU/low-stock navigation context and distinguishes genuine
  initial empty, filtered no-match, loading and API-error states.

## Historical Phase 4 assessment (superseded by the implementation above)

Status: **LAUNCH-CRITICAL MISSING UI HANDOFF** (`QA-P3-GAP-003`, historical P2
priority retained). This is an assessment/proposal, **not implemented or approved
production scope**. No marketplace write is required to open local stock.

## Exact existing boundary

- `/marketplaces/inventory` renders `UnifiedInventoryComponent` from
  `apps/web/src/app/marketplaces/unified-inventory.component.ts`. It loads canonical
  inventory, reconciliation summary, accounts and mappings. With no matching rows
  it says “Create a product stock record before mapping channel SKUs or accepting
  orders,” but offers only SKU filter/low-stock/Refresh, not a creation control or
  a link to a canonical stock-creation form. A filtered-empty list uses this same
  initial-empty wording; that is a separate usability concern.
- Row actions already support HUMAN adjustment (delta, reason, expected version),
  append-only ledger inspection and explicit account/SKU mapping. These require an
  existing inventory item. Adjusting Product master stock is not a substitute.
- `POST /api/v1/inventory/items` in
  `apps/api/vayujit_api/commerce/inventory_router.py` already creates the canonical
  item and its HUMAN `opening_balance` movement, and records
  `inventory.opening_balance_created` audit evidence in the same transaction.
- The API verifies the authenticated owner’s Product. An optional Catalog variant
  must belong to that same Product and owner. Item lookup/ledger/adjustment are
  owner-scoped; single-owner installation and `ck_users_single_owner` remain.
- SKU+location uniqueness is explicit. Existing opening replay uses item/key;
  semantic conflict/concurrency behavior of **opening creation** must be tested
  before a new UI claims identical retry protection. Passing adjustment replay
  tests are not proof of this different creation contract.

Source controls/schema are verified above; actual Phase 4 filtered-empty browser
and mapping-cancel evidence is in `phase-4-report.json`. A filtered-empty fixture
is not falsely described as a genuine new installation.

## Minimal proposed seller workflow

1. Inventory header and genuine empty state offer **Add opening stock**.
2. Choose an owned physical Product; link to existing Product creation only when
   none exists. Select an owned matching variant if applicable.
3. Show/enter internal SKU, location, unit, counted opening quantity and optional
   low-stock threshold. Explain on-hand versus reserved/damaged/available.
4. Show explicit HUMAN confirmation: this records a local opening balance, does
   not buy stock, publish channel quantity, reserve an order or certify its cost.
5. Submit through existing canonical API; retain a stable request key for retries.
   On success show item, balance, movement/audit reference and **View ledger** / 
   **Map channel SKU** next actions. Do not auto-map or call a marketplace.
6. Cancel leaves state unchanged. Handle API validation/conflict/unknown outcome;
   do not retry a materially changed request under the same key. After success,
   corrections use the existing reasoned/versioned adjustment authority, not a
   rewrite of the opening movement.

## Actual required inputs and validation

`InventoryItemCreate` in `commerce/schemas.py` currently defines:

| Input | Actual contract |
| --- | --- |
| `product_id` | Required UUID; existing authenticated owner’s Product |
| `variant_id` | Optional UUID; must belong to same Product/owner |
| `internal_sku` | Required, 1–100 characters; trimmed on storage |
| `location_code` | Defaults `default`, 1–80 characters; trimmed |
| `unit` | Defaults `each`, 1–24 characters; trimmed |
| `opening_quantity` | Integer 0–2,000,000,000; defaults 0; zero is a deliberate counted balance, not UNKNOWN |
| `low_stock_threshold` | Integer 0–2,000,000,000; defaults 0 |
| `idempotency_key` | Required 1–220 characters; stable identity for same request |

The current backend does **not** require supplier, cost, marketplace account or
listing to record stock. Do not invent these prerequisites or silently insert
missing commercial values. Whitespace-only text, digital/service products,
cross-product variants and conflicting opening replays require explicit contract
tests/decisions before UI launch; client validation cannot replace backend checks.

## Expected states

- Loading: owned Product/variant options; no enabled submit until prerequisites.
- Empty: explain Product prerequisite and offer existing Product creation route.
- Invalid: field-specific readable error; preserve inputs and focus first error.
- Saving: prevent double submit; retain key through an ambiguous network failure.
- Conflict: explain SKU/location existing or replay mismatch; offer review existing
  item, never silently change its opening quantity.
- Error: actionable retry for the identical request; never claim a balance exists
  until canonical persistence is read back.
- Success: explicit stock balance and ledger reference; refresh/back/deep link
  reconstruct the same persisted item; keyboard focus moves to confirmation.
- Cancel: no item, ledger movement or audit creation.

## Security and financial implications

No new approval system, multi-tenancy, direct DB writes or marketplace authority.
Preserve owner scoping, authenticated canonical HUMAN attribution, append-only
movements, versioned adjustments, audit events and fail-closed error behavior.
Recording quantity establishes neither acquisition price nor verified supplier
evidence. Cost remains separate; missing cost must not become zero or READY profit.
Do not auto-create fake account/orders or mark synthetic fixtures as real.

## Acceptance criteria and regression plan (proposed, not passed)

1. Genuine new disposable owner → brand/Product → initial Inventory empty state
   → opening form → explicit HUMAN save → item/ledger/audit → reload persists.
2. Empty search on a populated installation says **no matching items**, not **no
   canonical inventory yet**; genuine empty state offers the creation handoff.
3. Positive zero and positive stock, variant/no-variant, default/custom location,
   boundary quantities and low-stock threshold work exactly as canonical rules.
4. Missing Product, foreign/nonexistent Product/variant, negative/noninteger or
   oversized quantities, blank/whitespace SKU/location/unit fail truthfully.
5. Identical double submit/concurrent retry produces one item/opening movement;
   changed quantity/Product/variant/SKU/location under reused identity cannot be
   misacknowledged. Duplicate SKU/location and two simultaneous creators are safe.
6. Interrupted committed response reconstructs canonical result; no duplicated
   movement. Cancel/escape/history do not submit. Stale later adjustment rejects.
7. No supplier/cost/account prerequisite invented. Financial UNKNOWN stays UNKNOWN;
   no provider call, channel publication, procurement or order side effect.
8. Anonymous/expired sessions denied; single-owner and canonical attribution
   preserved; independent fresh process reads same item, movement and audit.
9. Desktop/mobile keyboard, accessible labels, field errors, focus restoration,
   full axe scans and table reading are verified without rule suppression.

Approve this bounded production workflow separately before implementation. Phase 4
does not turn these criteria into invented successful tests.
