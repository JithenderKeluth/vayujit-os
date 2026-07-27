# Security Architecture

## Controls

- **Authentication:** exactly one local owner; Argon2id password hashing; generic login failures; rate limiting and short backoff.
- **Sessions:** random bearer token, idle and absolute expiry, explicit revocation, held by Electron outside renderer-accessible storage.
- **Local API:** loopback bind only, authenticated routes, restricted credentialed CORS, and exact Origin validation on all unsafe methods. Missing or opaque origins are denied by default.
- **Secrets:** values encrypted using a key protected by Windows DPAPI; database stores references/ciphertext only. Secrets are never returned after entry.
- **Electron:** context isolation and sandbox enabled; Node integration, remote module, arbitrary navigation, permission requests, and unexpected windows disabled; Content Security Policy enforced.
- **Electron origin:** development uses `http://127.0.0.1:4200`; packaged content uses the secure standard `app://vayujit` scheme so API Origin checks remain explicit.
- **Validation/files:** typed request/output schemas, length limits, generated storage names, MIME/extension allow list, checksum and size limits, canonical-path containment.
- **AI:** product text is untrusted delimited input; fixed system instructions and versioned output schema; generated text cannot call tools, approve itself, or select connector permissions.
- **Connectors:** capability-specific interfaces, minimum payload, no arbitrary network/tool access, idempotency required, publishing gated by a durable approval.
- **Audit/redaction:** append-only security and business events with correlation IDs; tokens, passwords, secret values, and sensitive prompt content are redacted before logging.
- **Backups:** integrity manifest and schema version; no plaintext secrets; restore requires authentication, validation, confirmation, and a pre-restore safety backup.

## Threat Model

| Threat | Principal mitigation |
|---|---|
| Malicious renderer/XSS | CSP, isolated sandbox, no Node, narrow preload, authenticated API |
| Local process calls API | loopback plus session/bootstrap authentication, Host/Origin checks |
| Database/backup theft | password hashing, DPAPI-protected secret encryption, backup policy |
| Path traversal or hostile asset | canonical containment, allow lists, generated names, limits |
| Prompt injection | untrusted-data delimiting, structured schema, no model authority |
| Secret leakage | centralized redaction, opaque secret references, negative tests |
| Unauthorized/duplicate publishing | explicit approval, scoped adapter, idempotency, audit |
| Crash/state corruption | transactions, persisted transitions, restart recovery |
| Dependency compromise | lockfiles, vulnerability scanning, minimal dependencies |

## Residual Risks and Follow-up

A logged-in Windows user may access local business data unless whole-disk/OS account protection is enabled. DPAPI portability affects restore to another account and must be documented. Before production connectors, add connector-specific OAuth, egress, permission, revocation, and threat reviews.
