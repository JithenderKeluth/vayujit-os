# Supplier Security and Privacy

Supplier data is owner-scoped and untrusted. URLs, metadata, quotations, certification references, notes, and descriptions are not rendered as executable HTML. Credentials, tokens, cookies, DSNs, filesystem paths, payment data, and unrelated customer or buyer PII are rejected or omitted.

The subsystem does not scrape arbitrary sites, contact suppliers, create purchase orders, or claim live IndiaMART/Alibaba/TradeIndia/Global Sources access. Fraud signals are deterministic warnings phrased as `REQUIRES REVIEW`, not accusations.
`n## Final security evidence`n`nThe dedicated parameterized suite executes 70 cases, including unsafe URL targets, private/link-local/metadata IPs, embedded credentials, cross-owner boundaries, XSS payloads, historical overwrite attempts, currency/quantity bounds, duplicate identities, and response-secret leakage checks.
