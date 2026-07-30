# Brand Management API

All routes require the `vayujit_session` cookie. Unsafe methods also require an allowed exact
`Origin`. Requests and responses use JSON.

| Method | Route | Behavior |
|---|---|---|
| GET | `/api/v1/brands` | Stable name/ID ordering with search, status, archive, and pagination filters |
| POST | `/api/v1/brands` | Create a brand; the first brand becomes active |
| GET | `/api/v1/brands/active` | Return the active brand or `null` |
| GET | `/api/v1/brands/{brand_id}` | Return owner-scoped details and recent audit summary |
| PATCH | `/api/v1/brands/{brand_id}` | Partially update allow-listed identity fields |
| POST | `/api/v1/brands/{brand_id}/archive` | Idempotently archive and clear active context |
| POST | `/api/v1/brands/{brand_id}/restore` | Idempotently restore without activation |
| POST | `/api/v1/brands/{brand_id}/activate` | Atomically select a non-archived brand |

## List parameters

- `include_archived=false`: archived rows are excluded unless enabled.
- `search`: case-insensitive normalized-name substring.
- `status`: `active` or `archived`.
- `page`: one-based page number.
- `page_size`: 1–100, default 20.

The response contains `items`, `page`, `page_size`, `total`, and `pages`.

Names are required, trimmed, and limited to 120 characters. Slugs must match
`^[a-z0-9]+(?:-[a-z0-9]+)*$`. Website URLs must use HTTP or HTTPS. Colors use six-digit hex
notation. Duplicate normalized names or slugs return HTTP 409. Unknown or cross-owner UUIDs
return the same HTTP 404 response.

Logo upload and direct asset-path assignment are intentionally not exposed in this slice.

The application records `brand.created`, `brand.updated`, `brand.archived`, `brand.restored`, and
`brand.active_changed` in the same transaction as each mutation. Metadata is allow-listed and
does not contain full request bodies.
