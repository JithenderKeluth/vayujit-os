# Slice 6B: live read-only search provider

The certified adapter is **Brave Web Search API**. It uses the official read-only HTTPS `GET /res/v1/web/search` endpoint with the `X-Subscription-Token` header. The adapter exposes only `search` and `preflight`; it has no write, publish, contact, supplier, or purchase operation.

## Configuration

Set these deployment-controlled values (never commit the token):

- `VAYUJIT_INTELLIGENCE_EXTERNAL_PROVIDER_MODE=LIVE_READ_ONLY`
- `VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER=brave`
- `VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER_BASE_URL=https://api.search.brave.com/res/v1/web/search`
- `VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER_API_KEY=<Brave subscription token>`
- `VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER_COUNTRY=US`
- `VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER_LANGUAGE=en`
- `VAYUJIT_INTELLIGENCE_ENABLED=true`
- `VAYUJIT_INTELLIGENCE_EXTERNAL_RESEARCH_ENABLED=true`
- `VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER_ENABLED=true`

Approved domains, quotas, timeout, retry limits, and both kill switches remain explicit configuration. Missing credentials or disabled switches fail closed.

## Preflight and status

`GET /api/v1/intelligence/external/preflight` performs a bounded read-only check only when all live switches and credentials are present. Without credentials it returns `BLOCKED_BY_EXTERNAL_CREDENTIALS` with `credential_status=NOT_CONFIGURED`; it does not fabricate a success or make an outbound request. Credential status is one of `CONFIGURED`, `NOT_CONFIGURED`, `INVALID`, or `UNKNOWN`. Tokens are never returned, logged, audited, or included in exceptions.

## Search and provenance

The provider-neutral request is normalized to Brave's `q`, `count`, `country`, `search_lang`, and strict safe-search parameters. Results are normalized to title, URL, domain, snippet, retrieval time, provider result ID, rank, metadata, and `SEARCH_DISCOVERY_RESULT`. Unsafe/private URLs are discarded and the existing service canonicalizes and deduplicates URLs. Raw provider payloads are not persisted.

Authentication failures, 429 responses (including bounded `Retry-After`), timeouts, network errors, 5xx responses, and malformed payloads map to safe failure codes and the existing bounded retry/Recovery model. Local request quotas are consumed before outbound work and kill switches are rechecked immediately before the request.

## Certification boundary

The local adapter, transport safety, 40-case fail-closed security matrix, and existing Slice 6A regression are locally testable. Real Brave preflight/search, live latency, and live search-to-approved-fetch evidence remain **BLOCKED_BY_EXTERNAL_CREDENTIALS** until a disposable staging token and approved domain are supplied. No external AI, scraping, supplier outreach, purchasing, or mutation is enabled by this slice.