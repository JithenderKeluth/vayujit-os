# VAYUJIT OS — Software Requirements Specification

**Document ID:** VOS-SRS-001  
**Status:** Sprint 0 baseline  
**Scope:** Initial vertical-slice MVP

## Purpose and User

VAYUJIT OS is a local desktop system that lets one local owner create product data, generate structured content, approve it, publish through a mock adapter, and inspect durable history. The only MVP role is `owner`.

## Functional Requirements

| ID | Requirement |
|---|---|
| SRS-FR-001 | On first run, the system shall allow creation of exactly one owner account and shall reject creation of a second user. |
| SRS-FR-002 | The system shall authenticate the owner by password and shall return a generic error for invalid credentials. |
| SRS-FR-003 | Protected API routes shall reject missing, expired, or invalid sessions with HTTP 401. |
| SRS-FR-004 | The owner shall be able to sign out, immediately invalidating the session. |
| SRS-FR-005 | The owner shall create and view brands with a required unique name and optional guidelines. |
| SRS-FR-006 | The owner shall create, view, edit, activate, draft, archive, and restore products belonging to an owned brand; normalized name/slug shall be unique per brand and supplied SKU/barcode unique per owner. |
| SRS-FR-007 | Product assets shall be stored under the managed local asset root and linked to one product. |
| SRS-FR-008 | The owner shall start the versioned `product_content_v1` workflow for an existing product. |
| SRS-FR-009 | Each workflow and step transition shall be persisted with timestamps before the next step begins. |
| SRS-FR-010 | The mock AI adapter shall return the same valid JSON for the same normalized input and configured scenario. |
| SRS-FR-011 | Generated output shall contain non-empty `product_description`, `social_caption`, and `hashtags`; invalid output shall not create an approval request. |
| SRS-FR-012 | Valid output shall be stored as a generated artifact and shall pause the workflow in `waiting_for_approval`. |
| SRS-FR-013 | Only the authenticated owner shall approve or reject a pending approval request, with an optional comment. |
| SRS-FR-014 | Rejection shall transition the workflow to `rejected` and shall never invoke publishing. |
| SRS-FR-015 | Approval shall transition through `approved` and `publishing`, then invoke the configured mock publishing adapter. |
| SRS-FR-016 | The mock publisher shall accept an idempotency key and return a deterministic external ID, URL, timestamp, and status. |
| SRS-FR-017 | Repeating an accepted publish request with the same idempotency key shall return the stored result without a second side effect. |
| SRS-FR-018 | The owner shall view ordered workflow and step history, approval decision, artifact, publishing result, and sanitized errors. |
| SRS-FR-019 | The system shall audit login, logout, brand/product creation, workflow start, state changes, approval decisions, publish attempts, and settings changes. |
| SRS-FR-020 | The system shall expose health status for the API, database, asset storage, and configured adapters without exposing secrets. |
| SRS-FR-021 | Validation failures shall identify safe field-level errors; unexpected failures shall expose a correlation ID. |
| SRS-FR-022 | A failed retryable step shall be retryable by the owner; completed publishing shall not be repeated. |
| SRS-FR-023 | On restart, the system shall load durable executions and mark interrupted non-side-effect steps retryable; uncertain publishing shall require owner review. |
| SRS-FR-024 | The owner shall create a local backup containing database data, managed assets, manifest, schema version, and checksums. |
| SRS-FR-025 | Restore shall validate manifest version and checksums and require confirmation before replacing current data. |
| SRS-FR-026 | The mock vertical slice shall operate without internet access. Ollama unavailability shall not prevent use of the mock provider. |

## Non-Functional and Security Requirements

| ID | Requirement |
|---|---|
| SRS-NFR-001 | Passwords shall be hashed with Argon2id using parameters recorded in configuration; plaintext passwords shall never be stored or logged. |
| SRS-NFR-002 | Sessions shall use cryptographically random tokens, an idle timeout, an absolute lifetime, revocation, and secure storage in the desktop client. |
| SRS-NFR-003 | FastAPI shall bind to loopback only, choose/configure a non-public port, require authentication, restrict CORS to the packaged UI origin, and reject untrusted Host/Origin values. |
| SRS-NFR-004 | Electron shall enable context isolation and sandboxing, disable Node integration in renderers, use a narrow preload API, and deny unexpected navigation/window creation. |
| SRS-NFR-005 | Secrets shall be encrypted with an OS-protected key and redacted from UI, logs, errors, audit metadata, and exports. |
| SRS-NFR-006 | API bodies and AI/connector outputs shall be schema validated with bounded lengths; database operations shall use parameterized ORM access. |
| SRS-NFR-007 | Asset paths shall use generated names, remain beneath the asset root, reject traversal, and enforce allow-listed types and configured size limits. |
| SRS-NFR-008 | Common local API requests excluding AI shall complete within one second at the documented test-data volume. |
| SRS-NFR-009 | Execution and approval state shall survive a forced application restart without an invalid transition or duplicate publish. |
| SRS-NFR-010 | Audit events shall be append-only through application interfaces and retained for the life of the local data set unless the owner performs a documented full-data deletion. |
| SRS-NFR-011 | Business records shall use soft deletion where referenced by execution history; generated artifacts and audit relationships shall remain traceable. |
| SRS-NFR-012 | Backups shall not contain plaintext secrets, shall be integrity checked, and shall document whether encrypted secrets are portable to another Windows account. |
| SRS-NFR-013 | Core domain logic shall have unit tests; persistence/adapters shall have integration tests; the primary journey shall have an automated end-to-end test. |
| SRS-NFR-014 | Logs shall be structured and include correlation and execution IDs while excluding credentials, session tokens, and full sensitive prompts. |
| SRS-NFR-015 | Provider and connector adapters shall receive only explicitly scoped data and capabilities; the MVP shall not permit arbitrary tools or network calls. |
| SRS-NFR-016 | Prompt inputs shall be delimited as untrusted data; generated output shall never authorize tools, approval, or publishing. |

## Error and Recovery Rules

Validation errors are non-retryable until input changes. Transient adapter/database errors are retryable with bounded attempts. Unknown publishing outcomes are never automatically retried. Cancellation is allowed only before publishing begins. Errors shown to users are sanitized; diagnostic detail remains local and correlated.

## Testable System Acceptance

Acceptance tests shall cover: first-owner creation; duplicate-owner rejection; session expiry/revocation; brand and product validation; deterministic valid and invalid mock AI scenarios; approval and rejection branches; idempotent mock publishing; forced restart at each workflow state; unauthorized API access; path traversal rejection; secret redaction; offline execution; backup integrity failure; successful backup/restore; and chronological audit/history display.

The Sprint 1 standalone publishing implementation satisfies SRS-FR-016, SRS-FR-017, and the
publishing portion of SRS-FR-018/SRS-FR-022 using a deterministic offline connector, durable
owner-scoped idempotency, immutable attempts/snapshots, filtered execution history, and explicit
retryable failure classification. Workflow orchestration and restart recovery remain S1-10 scope.
