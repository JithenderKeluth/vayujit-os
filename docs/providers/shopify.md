# Shopify provider certification

This document is the operating contract for Shopify in VAYUJIT OS. The current
checkout has a production-shaped Shopify connector and deterministic loopback
coverage, but no Shopify test-store credentials. Therefore the current external
classification is **SHOPIFY SANDBOX — BLOCKED BY EXTERNAL CREDENTIALS**.

## Connector inventory

- `apps/api/vayujit_api/publishing/shopify_connector.py` owns the predefined
  Admin GraphQL operations, domain/API-version validation, timeout and network
  classification, throttle metadata, product/variant/media/collection/publication
  mapping, reconciliation, and safe remote URLs.
- `publishing/shopify.py` resolves encrypted persisted credentials or deployment
  secrets and selects the connector. `publishing/service.py` owns durable jobs,
  attempts, retry/recovery, idempotency, audit, and owner scoping.
- The API version is quarterly and defaults to `2026-07`; it must be changed only
  to a supported quarterly version.
- Supported read operations are account validation, collections, publications,
  product status, and media status. Supported writes are draft/create/update,
  variants/options, media upload/create, collection/publication assignment,
  publish/unpublish, and archive through the existing connector flow. Delete is
  not a supported connector capability.
- No Shopify webhook callback route is currently implemented. The provider-neutral
  HMAC freshness/replay helper is tested, but it is not evidence of a subscribed
  Shopify webhook.

## Configuration and secret handling

Use deployment secrets, never committed files:

```text
VAYUJIT_SHOPIFY_MODE=fake|sandbox|live
VAYUJIT_SHOPIFY_SHOP_DOMAIN=store.myshopify.com
VAYUJIT_SHOPIFY_ADMIN_API_ACCESS_TOKEN=<secret>
VAYUJIT_SHOPIFY_CLIENT_ID=<optional>
VAYUJIT_SHOPIFY_CLIENT_SECRET=<optional secret>
VAYUJIT_SHOPIFY_API_VERSION=2026-07
VAYUJIT_SHOPIFY_TIMEOUT=45
VAYUJIT_SHOPIFY_LIVE_MUTATION_ENABLED=false
VAYUJIT_LIVE_MARKETPLACE_MUTATIONS_ENABLED=false
```

`fake` is the safe local default. Staging validation requires `sandbox`, a
valid `*.myshopify.com` domain, a token, a quarterly API version, and HTTPS
staging. A Shopify write additionally requires the Shopify switch, the global
marketplace switch, a validated opted-in account, explicit confirmation, a
bounded idempotency key, and the global emergency stop to be off. `live` is
rejected by this staging-certification branch. Configuration errors contain no
secret values.

Persisted Shopify access tokens use the existing encrypted credential subsystem,
credential version/key-id metadata, and rotation path. Runtime-only deployment
secrets are never returned by API responses, diagnostics, logs, audit payloads,
or redacted provider payloads.

## Scopes and read-only validation

Request only scopes required by enabled operations and verify the exact grant in
the Shopify app before certification. Read-only validation needs the shop/account
metadata and product/catalog/publication reads used by the connector. Controlled
writes additionally need the product, variant, media, collection, and publication
mutation scopes that the selected workflow exercises. Webhook scopes are not
requested until a callback route and event inventory are implemented.

With credentials available, run validation against a Shopify development/test
store only: account metadata, API version/domain, granted scopes, and a basic
product capability probe. Do not call mutation operations during read-only
validation. Without credentials, this evidence is **BLOCKED BY EXTERNAL
CREDENTIALS**, not a fake PASS.

## Failure, recovery, and safety contract

The connector classifies authentication failures, 429/Retry-After and GraphQL
throttle metadata, timeouts, network failures, redirects, oversized/invalid
responses, and 5xx responses into bounded safe failures. Product create/update
timeouts are marked ambiguous so Recovery reconciles before replay. Sequential
and concurrent duplicate confirmation are deduplicated by the durable
idempotency key. A remote mutation must be previewed and confirmed with the
current fingerprint; a new VAYUJIT version never silently mutates an older remote
mapping.

The safe correction model is compensating update/archive or explicit removal of
managed collection/publication assignments. No unsupported remote delete or
unscoped rollback is claimed. Before any real test-store write, capture the
staging database/media backup, perform one disposable reversible mutation, record
remote identity/checkpoint/history, reconcile, and clean up only that test data.

The provider-neutral controls cover emergency stop, provider mode lineage, audit,
metrics, redaction, webhook HMAC/replay checks, and Recovery actions (retry,
reconcile, refresh credentials, review account, cancel local operation). Unknown
webhook topics must be acknowledged or rejected by a future provider callback
contract without mutation; no callback route is currently certified.

## Current decision

- Shopify connector foundation: **READY** for local/fake and loopback evidence.
- Shopify read-only connection: **CONDITIONAL GO**, blocked until test-store
  credentials and a staging deployment are supplied.
- Shopify sandbox mutation: **NO-GO / BLOCKED BY EXTERNAL PREREQUISITE** until
  scopes, credentials, backup, one reversible mutation, idempotency, recovery,
  reconciliation, and cleanup are evidenced.
- Shopify staging certification: **NOT CERTIFIED**.
- Shopify production: **NOT VALIDATED / NO-GO**.
- Amazon is the next provider only after Shopify sandbox evidence is complete;
  do not start Amazon implementation while Shopify access is blocked.

Required external prerequisites are a Shopify development/test store, a staging
URL and database, a least-privilege custom app/token, confirmed API version and
scopes, an operator-approved disposable product, backup storage, and an emergency
stop owner. No credentials belong in this repository.