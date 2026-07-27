# ADR-007: Server-Managed Cookie Sessions

**Status:** Accepted

## Context
The local Angular UI and Electron shell need restorable authentication without exposing tokens to renderer JavaScript or localStorage.

## Decision
Use opaque random session tokens in HttpOnly, SameSite=Strict cookies. Store only SHA-256 token hashes and expiry/revocation state in PostgreSQL. Development permits non-Secure loopback HTTP cookies; production sets Secure.

Every POST, PUT, PATCH, and DELETE request must carry an exact Origin from the configured allow-list. The defaults are the Angular development origin `http://127.0.0.1:4200` and packaged Electron origin `app://vayujit`. Missing, malformed, opaque `null`, and unlisted origins are rejected. Missing Origin is permitted only through the explicit `VAYUJIT_ALLOW_MISSING_ORIGIN` test/same-process override, which remains false by default.

Packaged Electron content uses the secure standard custom scheme `app://vayujit`, not `file://`, so cookie and Origin behavior is deterministic. Development Electron continues to load Angular’s loopback origin.

Expired sessions are deleted opportunistically when a new session is created. Revoked sessions are retained for 24 hours by default for local diagnosis, then deleted during the same cleanup operation.

## Alternatives Considered
Browser localStorage tokens (XSS exposure); JWT access/refresh tokens (unnecessary complexity and harder revocation); Electron-only secure storage (does not support browser development consistently).

## Consequences
Refresh restoration is automatic and logout is immediately revocable. PostgreSQL availability is required for authentication.

## Risks
Cookie misconfiguration, compromised allowed-origin content, stolen local database/session cookies, and cleanup occurring only when authentication is used.

## Follow-up Actions
Enable Secure cookies in packaged production, add explicit idle expiry if required, and document local TLS if introduced.
