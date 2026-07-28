# Mock Publishing API

All `/api/v1/publishing` routes require the owner session; writes require an exact allowed Origin.
The API exposes connector capability discovery, destination CRUD/lifecycle, synchronous execution
creation, filtered history, details, and retry.

Only approved artifacts for non-archived products and brands may publish. Active Brand-scoped
destinations accept only matching products. Configuration is a strict mock schema, never arbitrary
JSON or secrets.

Idempotency keys are unique per owner and retained with execution history. Repeating equivalent
input returns the existing execution; different input conflicts. Every attempt uses the original
schema-versioned content and destination request snapshots. Retry requires a failed, retryable
execution and an enabled destination, locks the execution row, and never rereads mutable artifact
content.

The deterministic connector makes no network request. URLs use `example.invalid`, are display-only,
and results/errors are bounded safe JSON.

The Angular flow lists only approved artifacts attached to non-archived Products and active
Brands, then filters active destinations for compatible Brand scope. One generated idempotency
key is retained throughout one intentional submission. The preview and result screens interpolate
generated data as text, collapse long content, and never turn mock URLs into links.
# Preferred destination

The owner may choose an active destination as a preference. Publication preselects it only when
it is global or scoped to the selected Brand. Disabled, inaccessible, and Brand-incompatible
destinations are not selected or re-enabled automatically.
