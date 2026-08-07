# Sprint 1 Backlog — Vertical Slice

**Goal:** Deliver the smallest locally runnable product-to-approved-mock-publish journey. Sizes are relative: XS (hours), S (about one day), M (several days), L (must be split before commitment).

Real AI provider hardening adds the provider abstraction, encrypted owner
configuration, model discovery, structured generation, usage, explicit mock
fallback, diagnostics, and provider settings UI without adding real publishing.

| ID / Jira-style title | Description | Acceptance criteria | Dependencies | Priority | Size | Component | Labels |
|---|---|---|---|---|---|---|---|
| S1-01 Establish repository foundation | Add workspace conventions, ignore rules, environment templates, formatting, linting, and test commands. | Documented commands run; secrets/build outputs ignored; checks have one entry point. | None | P0 | S | Engineering | `sprint-1`, `foundation` |
| S1-02 Scaffold FastAPI modular monolith | Create API entry point, configuration, module packages, correlation middleware, and health route. | API starts locally; health response is typed; boundary layout matches ADR-004. | S1-01 | P0 | M | Backend | `sprint-1`, `fastapi` |
| S1-03 Scaffold Angular application | Create routed shell, API client, error handling, and initial accessible layout. | UI starts, calls health endpoint, and displays unavailable state safely. | S1-01, S1-02 | P0 | M | Frontend | `sprint-1`, `angular` |
| S1-04 Scaffold secure Electron shell | Package Angular window and manage FastAPI lifecycle with secure Electron defaults. | One command launches UI/API; shutdown cleans child process; security assertions pass. | S1-02, S1-03 | P0 | M | Desktop | `sprint-1`, `electron`, `security` |
| S1-05 Configure PostgreSQL and Alembic | Add least-privilege local configuration, SQLAlchemy session handling, baseline migration, and DB health. | Fresh DB migrates up/down; API transacts; setup is documented. | S1-02 | P0 | M | Data | `sprint-1`, `postgresql`, `alembic` |
| S1-06 Implement local owner authentication | **Complete:** owner setup, Argon2id login, PostgreSQL cookie sessions, Origin protection, logout, restoration, cleanup, and protected routes are implemented and validated. | Auth requirements SRS-FR-001–004 and negative tests pass. | S1-05 | P0 | M | Identity | `sprint-1`, `identity`, `security` |
| S1-07 Implement brand module | **Complete:** PostgreSQL model, migration, authenticated lifecycle API, active context, audit trail, and Angular list/create/details/edit UI. | Normalized uniqueness, archive/restore, activation, pagination, ownership, security, and integration tests pass. | S1-05, S1-06 | P0 | M | Brands | `sprint-1`, `brands` |
| S1-08 Implement product module | **Complete:** PostgreSQL product/commerce model, explicit lifecycle API, brand movement, audit trail, filters, decimal money, and Angular list/create/details/edit UI. | Ownership, uniqueness, activation, archive/restore, money, inventory, filtering, and integration tests pass. | S1-07 | P0 | M | Products | `sprint-1`, `products` |
| S1-09 Define AI contract and deterministic mock | **Complete:** typed provider boundary, prompt/request/artifact persistence, deterministic valid/invalid mock scenarios, owner review UI, history, audit, and contract/integration tests. | Same input yields the same schema-valid output; invalid output is rejected safely; versions and decisions persist. | S1-05, S1-08 | P0 | M | AI | `sprint-1`, `ai`, `mock` |
| S1-10 Implement workflow engine subset | Persist definition/execution/steps and allowed transitions; start, fail, cancel, retry, and restart recovery. | State-model transition, retry, and forced-restart tests pass. | S1-05, S1-09 | P0 | L | Workflows | `sprint-1`, `workflow` |
| S1-11 Implement approval API and UI | **Complete:** central paginated review queue, Artifact details/version navigation, existing approve/reject/regenerate lifecycle, and Workflow-aware continuation. | Only pending requests change once; rejection never publishes; decision is durable. | S1-06, S1-10 | P0 | M | Approvals | `sprint-1`, `approval` |
| S1-12 Implement mock publishing connector | **Complete:** scoped deterministic connector, destinations, immutable snapshots/attempts, owner idempotency, safe retry, history UI/API, and audit. | Approved artifact publishes once; duplicate key returns stored result; ineligible artifacts cannot invoke it. | S1-11 | P0 | M | Publishing | `sprint-1`, `publishing`, `mock` |
| S1-13 Build execution history | **Complete:** normalized owner-safe audit history, filters, list/timeline modes, related links, and formula-safe bounded CSV plus existing domain details. | Owner can trace AI, approval, Workflow, publication, and retry activity. | S1-10, S1-12 | P0 | M | Workflows | `sprint-1`, `history` |
| S1-14 Add append-only audit logging | Centralize audit writer and queries for required security/business events. | Required events include actor/correlation/time; secret-redaction tests pass. | S1-06, S1-10 | P0 | M | Audit | `sprint-1`, `audit`, `security` |
| S1-15 Add automated vertical-slice tests | Add unit, DB/adapter integration, API security, and packaged happy/reject/recovery E2E tests. | CI demonstrates SRS acceptance matrix; offline run passes; no duplicate publishing. | S1-04–S1-14 | P0 | L | Quality | `sprint-1`, `testing` |
| S1-16 Document local development and recovery | Document prerequisites, setup, migrations, run/test commands, troubleshooting, logs, backup expectations, and known limitations. | A clean supported Windows setup can run tests and demo without undocumented steps. | S1-01–S1-15 | P0 | M | Documentation | `sprint-1`, `docs` |
| S1-17 Implement backup/restore proof | Produce integrity manifest/checksums and confirmed restore for DB and managed assets. | Corrupt backup rejected; valid backup restores slice data; secrets policy documented. | S1-05, S1-08, S1-14 | P1 | M | Data | `sprint-1`, `backup`, `security` |
| S1-18 Add Ollama-compatible adapter | Implement local HTTP adapter behind the AI contract without changing workflow code. | Capability/health, timeout, invalid-output, and contract tests pass; mock remains default. | S1-09, S1-15 | P1 | M | AI | `sprint-1`, `ai`, `ollama` |

## Suggested Delivery Order

Production-hardening follow-up adds structured observability, operational health, recovery,
verified local backups, guarded restore planning, maintenance and retention commands, audit
correlation, release diagnostics, and dependency governance. Real providers, connectors, workers,
scheduling, billing, and organization features remain out of scope.

Commit only S1-01 through S1-04 first as a walking skeleton, then data/auth/business objects, then AI/workflow/approval/publishing, and finally history, audit, acceptance tests, and documentation. S1-10 and S1-15 are sized L and should be split into state/persistence/recovery and test-suite subtasks during Jira refinement.
# WordPress Publishing UX acceptance slice

- Media Library and secure upload
- Featured-image policy and remote mapping
- Cached searchable category, tag, and author selectors
- Shared Publishing preview and sanitization comparison
- Field-level drift and explicit reconciliation decisions
- Recovery, health, audit, accessibility, Electron, and guarded migration acceptance
# Shopify Publishing vertical slice

- Shopify configuration, validation, discovery, destination, draft, update, activation, execution,
  reconciliation, recovery, health, audit, diagnostics, tests, and documentation.
# Content Calendar and Campaign follow-up

## Durable Activity rescheduling follow-up

**Complete:** server-authoritative preview/confirmation, DST fold/gap handling, durable
schedule/job supersession, idempotent confirmation, Recovery action exposure, Campaign Activity
history, Operations links, responsive Angular flow, shared contracts, and guarded acceptance tests.

The Campaign core includes normalized persistence, lifecycle, checkpoints, readiness, conflict
analysis, durable schedule links, calendar projections, Angular routes, recovery/health
projections, diagnostics, and guarded tests. Searchable Product/Artifact/destination pickers,
Campaign-aware Workflow templates/waits, richer Recovery actions, and full fake-connector Campaign
E2E remain explicit follow-up work.

## Durable one-catch-up Recovery action

Implemented the final Recovery action with fingerprinted preview/confirmation, additive missed
Activity persistence, scheduler idempotency, and Operations history integration.
