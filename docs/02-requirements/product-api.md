# Product Management API

All routes require the owner session. Unsafe methods require an exact allowed `Origin`.

| Method | Route | Behavior |
|---|---|---|
| GET | `/api/v1/products` | Owner-scoped filtering, sorting, and pagination |
| POST | `/api/v1/products` | Create a draft product for an explicit or active brand |
| GET | `/api/v1/products/{product_id}` | Details and recent audit summary |
| PATCH | `/api/v1/products/{product_id}` | Update allow-listed fields or move owned brand |
| POST | `/api/v1/products/{product_id}/activate` | Validate readiness and activate |
| POST | `/api/v1/products/{product_id}/move-to-draft` | Idempotently return active to draft |
| POST | `/api/v1/products/{product_id}/archive` | Idempotent soft archive |
| POST | `/api/v1/products/{product_id}/restore` | Restore to draft when brand is usable |

## Ownership and lifecycle

Every product belongs to one non-deleted Brand owned by the authenticated owner. Create defaults
to the active brand when `brand_id` is absent. Moving between owned, non-archived brands is
supported and re-applies destination name/slug uniqueness.

New products are draft. Physical, digital, and affiliate products require a description, price,
and currency before activation; services require a description. Archived products cannot be
activated or drafted until restored. Restore always produces draft.

## List query

Without `brand_id` or `all_brands=true`, the list uses the active brand. No active brand produces
an empty list. Supported parameters include:

- `brand_id`, `all_brands`, `include_archived`
- `search` for normalized name or SKU; dedicated `sku`
- `category`, `product_type`, `status`, `featured`
- `sort_by`: `name`, `created_at`, `updated_at`, `price`, `inventory_quantity`
- `sort_direction`, `page`, and `page_size` (maximum 100)

## Money and validation

Money request and response values are JSON strings. Accepted syntax is non-negative base-10 with
up to ten integer digits and two fractional digits. Values are stored as `NUMERIC(12,2)` without
application rounding; over-precision is rejected. The maximum is `9999999999.99`. Currency is
three ASCII letters and normalized to uppercase. Currency conversion is not performed.

Compare-at price requires sale price and cannot be lower. Cost, inventory, thresholds, and weight
cannot be negative. Weight accepts up to three fractional digits and requires `g`, `kg`, `oz`, or
`lb`. Tags contain at most 20 unique normalized values of at most 50 characters.

Normalized name and slug are unique per brand. Non-empty SKU and barcode are unique per owner.

## Audit

Mutations record `product.created`, `product.updated`, `product.brand_changed`,
`product.activated`, `product.moved_to_draft`, `product.archived`, and `product.restored`.
Metadata contains allow-listed identifiers, changed field names, statuses, product type, and SKU
presence—never full descriptions or request bodies.
