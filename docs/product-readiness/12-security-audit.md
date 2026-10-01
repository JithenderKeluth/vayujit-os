# Security audit

Existing controls include authentication/owner scoping, OriginProtection, safety and operational middleware, security headers, CORS, secure provider modes, kill switches, ApprovedWebFetcher SSRF/domain/redirect/TLS/MIME/byte controls, inert extraction, and fail-closed external writes.

The disposable test database guard is a critical safety boundary. `.env` files and credentials are ignored; tracked configuration is limited to examples. No obvious committed provider token was found in the audit scan.

Before production: provision secret management, HTTPS/secure cookies, production session/encryption keys, rate limits, webhook/file-upload review, structured PII-safe logging, backup encryption and deployment-specific CORS. Do not print secrets in diagnostics or reports.
