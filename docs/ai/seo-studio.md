# SEO Studio

SEO Studio is an owner-scoped, deterministic advisory service over Product facts and approved AI Artifacts. It evaluates title/meta completeness, keyword coverage, readability, factual consistency, and channel compliance without changing the source Artifact.

## Inputs and safety

Keyword Sets are normalized case-insensitively, deduplicated, and scoped to the owner/Product or Brand. Analysis is tied to the requested Artifact/version or current Product context. If the source version is stale, the caller must refresh before relying on the result. Search-volume and competition values are never invented: live search data is unavailable in the local provider and is returned as `null`/unavailable rather than guessed.

SEO results are advisory. Human approval remains required before listing or Campaign handoff. No SEO request calls a marketplace connector or publishes content.

## Durable operation

SEO analysis runs through the same API persistence and audit boundaries as Studio work. Generated content remains immutable; edits, rejection, regeneration, localization, and translation create new versions with explicit source lineage. Exact Artifact/version references are required for downstream handoffs, preventing stale or cross-locale substitutions.

## Security and privacy

Product, Brand, Keyword, Artifact, usage, and audit records are owner-scoped. Generated text is rendered with Angular-safe bindings. Prompt-injection-like text is treated as data. Safe responses omit credentials, API keys, tokens, cookies, database URLs, local paths, environment values, SQL, raw provider payloads, and tracebacks.

## Certification status

- LOCAL DETERMINISTIC SEO ANALYSIS — CERTIFIED
- NO-FAKE-SEARCH-DATA GUARANTEE — CERTIFIED LOCALLY
- REMOTE SEARCH/SEO PROVIDER — NOT VALIDATED
- HUMAN APPROVAL AND EXACT-VERSION HANDOFF — CERTIFIED LOCALLY
