# Approved live web fetch (Slice 6C)

Approved live fetch is a fail-closed, read-only HTTPS boundary. It is disabled by default and requires `LIVE_READ_ONLY`, the global Intelligence and external-research switches, the approved-fetch switch, and a non-empty approved-domain allowlist. Blocked and review-required domains always win. No wildcard internet access is supported.

## Certified domains

The certification fixture uses `example.org` as the deterministic public documentation domain. A staging operator may select one to three public documentation/manufacturer domains, record the rationale, and add them to `VAYUJIT_INTELLIGENCE_EXTERNAL_APPROVED_DOMAINS`. Domains requiring manual review belong in `VAYUJIT_INTELLIGENCE_EXTERNAL_REVIEW_REQUIRED_DOMAINS` and fail closed until an owner-scoped source profile records approved robots and terms classifications.

## Transport boundary

Only HTTPS on ports 443 (or the default HTTPS port) is accepted. Hostnames are resolved before every request and every redirect; private, loopback, link-local, reserved, unspecified, and metadata targets are rejected. Redirects are followed one hop at a time with a bounded maximum and each target is revalidated. TLS verification remains enabled.

Only `text/html`, `text/plain`, and `application/json` are accepted. Responses are streamed and stop at the configured byte limit. HTML is parsed into inert title, description, canonical URL, publication timestamp, and bounded text; scripts, frames, forms, styles, SVG, event handlers, and executable URLs are never trusted. Raw HTML and private response headers are not persisted or returned. All content is classified `UNTRUSTED_EXTERNAL_DATA`.

## Provenance and freshness

Fetch rows persist requested/final URL, domain, status, HTTP status, MIME, byte count, SHA-256 hash, redirect count, profile, mode, correlation ID, freshness state, and safe extracted metadata. Refresh is append-only when the hash changes and reuses the existing observation when unchanged. Mission fetches pass through the existing verifier before evidence and claim projection; search snippets and raw HTML cannot create claims.

## Operations and recovery

`GET /api/v1/intelligence/external/fetch/preflight` reports readiness without network traffic. Fetch history and execution checkpoints expose status, latency, bytes, freshness, verification, failure, and recovery without secrets. Bounded retries apply only to timeout, network, selected 5xx, and 429 failures. Unsafe URL, blocked redirect, unsupported MIME, oversize, disabled domain, and policy failures are terminal and advertise review/skip/cancel recovery.

No provider mutation, purchasing, supplier outreach, browser automation, or unrestricted scraping is implemented. Live certification requires explicit credentials and operator approval; absent those, the truthful status is `BLOCKED_BY_EXTERNAL_CONFIGURATION`.
