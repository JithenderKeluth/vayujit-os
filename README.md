# VAYUJIT OS

Production-hardening operator guidance is in
`docs/00-governance/production-readiness.md`. Start with `npm.cmd run system:doctor`,
`npm.cmd run security:check`, and the authenticated `/operations` area.

VAYUJIT OS is a local-first, AI-powered business operating system for
entrepreneurs and small businesses managing commerce, content, automation, and
analytics.

## Sprint 0 documentation

### Product

- [Product Vision](docs/01-product/product-vision.md)
- [Product Requirements Document](docs/01-product/product-requirements-document.md)
- [Initial MVP Scope](docs/01-product/mvp-scope.md)
- [Software Requirements Specification](docs/02-requirements/software-requirements-specification.md)
- [Media Library](docs/03-architecture/media-library.md)
- [WordPress Publishing](docs/03-architecture/wordpress-publishing.md)
- [Publishing preview](docs/03-architecture/publishing-preview.md)
- [Remote drift and reconciliation](docs/03-architecture/remote-drift-reconciliation.md)

### Governance

- [Sprint 0 plan](docs/00-governance/sprint-0.md)
- [PRD-to-Jira mapping](docs/00-governance/prd-jira-mapping.md)

### Architecture

- [System Context](docs/03-architecture/system-context.md)
- [Container Architecture](docs/03-architecture/container-architecture.md)
- [Domain Boundaries](docs/03-architecture/domain-boundaries.md)
- [Core Data Model](docs/03-architecture/core-data-model.md)
- [Workflow State Model](docs/03-architecture/workflow-state-model.md)
- [Security Architecture](docs/03-architecture/security-architecture.md)
- [Mermaid diagrams](docs/03-architecture/diagrams)

### Decisions and planning

- [Architecture Decision Records](docs/04-decisions)
- [Sprint 1 Backlog](docs/05-planning/sprint-1-backlog.md)

The Product Vision defines the intended users, value proposition, principles,
MVP boundaries, and long-term direction. The Product Requirements Document
turns that vision into scoped capabilities, testable requirements, acceptance
criteria, and release priorities.

## Sprint 1 walking skeleton

The initial monorepo contains:

- `apps/web`: strict Angular application shell and placeholder routes
- `apps/api`: Python 3.12 FastAPI modular-monolith foundation
- `apps/desktop`: secure Electron development shell
- `packages/shared`: frontend/desktop TypeScript contracts
- `infrastructure`: PostgreSQL-only Docker Compose configuration
- `scripts`: Windows setup, migration, validation, and development commands

No authentication, business features, AI providers, workflows, or connectors are
implemented yet.

### Prerequisites

- Node.js 22 LTS (preferred; `.nvmrc`/`.node-version`) or Node.js 24, and npm
- Python 3.12 with the `py` Windows launcher
- Docker Desktop with Docker Compose

If Python 3.12 is missing, install it and open a new terminal:

```powershell
winget install --exact --id Python.Python.3.12
py -3.12 --version
```

### Local setup

```powershell
Copy-Item .env.example .env
npm install
npm run api:install
npm run db:up
npm run db:migrate
npm run dev
```

The Angular UI is served at `http://127.0.0.1:4200`; FastAPI is served at
`http://127.0.0.1:8000`. The Electron development process waits for Angular and
then loads that local origin. `scripts/start-dev.ps1` combines database startup,
migration, and development startup after dependencies are installed.

### Validation

```powershell
npm run build
npm run lint
npm test
npm run format:check
git diff --check
```

API-only commands use executables from `apps/api/.venv`. Stop PostgreSQL with
`npm run db:down`.

### Local owner authentication

After migrations and services start, open `http://127.0.0.1:4200`. A clean database
redirects to `/setup`; later launches restore the HttpOnly cookie session or redirect
to `/login`.

Authentication endpoints are under `/api/v1/auth`: `setup-status`, `setup-owner`,
`login`, `logout`, and `me`. Sessions are opaque, server-managed PostgreSQL records;
the browser never stores tokens in localStorage.

Unsafe API requests require an exact configured Origin. Development allows
`http://127.0.0.1:4200`; packaged Electron uses `app://vayujit`.
`VAYUJIT_ALLOW_MISSING_ORIGIN` must remain false outside isolated same-process tests.
Expired sessions are removed when a new session is created; revoked sessions are
retained for the configured diagnostic window (24 hours by default).

Automated PostgreSQL tests use only the marked `vayujit_test` database. The guarded test command
creates it when absent, refuses existing unmarked databases, validates the connected database,
and never falls back to `vayujit`. See the
[testing strategy](docs/00-governance/testing-strategy.md).

Electron 43.2.0 is launched through `scripts/start-desktop.ps1`. The launcher removes an inherited
`ELECTRON_RUN_AS_NODE` value from the Electron child so the main file cannot accidentally execute
as ordinary Node. Validate BrowserWindow creation and renderer readiness with
`npm.cmd run test:desktop:smoke`.

To reset authentication in development, stop the application and remove only the
development Compose volume:

```powershell
npm.cmd run db:down
docker volume rm infrastructure_vayujit_postgres_data
npm.cmd run db:up
npm.cmd run db:migrate
```

This destroys the entire local development database. Never use this procedure for
production or a database containing data that must be retained.

### Brand Management

Authenticated owners can create, search, view, edit, archive, restore, and activate brands from
`/brands`. Brand names are whitespace-normalized and case-folded before applying per-owner
uniqueness. Slugs are lowercase, URL-safe, and unique per owner.

The first brand becomes the active context automatically. Activating another brand atomically
clears the previous selection. Archiving the active brand clears the context; restoring it does
not reactivate it. Active context is stored in PostgreSQL and restored in the application shell
after refresh or restart.

The list defaults to non-archived brands and supports search, status, archive inclusion, and
pagination. All changes write sanitized append-only audit events. See the
[Brand API reference](docs/02-requirements/brand-api.md) and
[local development guide](docs/00-governance/local-development.md).

### Product Management

Products belong to exactly one owned brand and default to the active brand when created. The
`/products` area supports draft, active, and archived lifecycles; brand, status, type, category,
featured and search filters; stable sorting; and pagination.

Money crosses the API as decimal strings such as `"19.99"` and is stored as PostgreSQL
`NUMERIC(12,2)`. Product activation is an explicit validated transition. Archive is a soft delete,
and restoration always returns a product to draft. See the
[Product API reference](docs/02-requirements/product-api.md) and
[decimal money ADR](docs/04-decisions/ADR-008-decimal-money-json-strings.md).

### AI Content Generation

The authenticated `/ai` area generates schema-validated product content with either the offline
deterministic mock or one explicitly configured OpenAI-compatible endpoint. Provider credentials
are backend-only and AES-256-GCM encrypted when stored in PostgreSQL. The real-provider path has
bounded timeouts/retries, model discovery, strict structured output, one repair attempt, explicit
mock fallback, attempt/usage persistence, and local cancellation intent. Human approval remains
mandatory and no real publishing connector is included. See the
[AI architecture](docs/03-architecture/ai-architecture.md),
[provider guide](docs/00-governance/ai-provider-integration-guide.md), and
[credential guide](docs/00-governance/ai-credential-management.md).

### Mock Publishing and Execution History

The protected `/publishing` area manages local mock destinations and publishes only approved AI
artifacts. Each synchronous execution stores immutable content/request snapshots, deterministic
safe connector output, owner-scoped idempotency, immutable attempts, retry classification, and
audit evidence. No remote platform, OAuth, secret, webhook, scheduler, worker, or Redis is used.
See the [Publishing API](docs/02-requirements/publishing-api.md).

The user-facing journey is: activate a Brand, create and activate a Product, generate and approve
AI content, create an active mock destination, select the approved version from **Publishing**,
review the text-only preview, confirm publication, and inspect the execution timeline. Development
builds expose deliberate failure simulation inside a collapsed **Development testing** section.
Mock `.invalid` URLs are non-routable examples and remain display-only.

### Workflow Orchestration

The `/workflows` area runs the constrained Product Content Publish template: AI generation,
durable human-approval pause, and idempotent mock publishing. State and immutable step attempts
survive refresh/restart. See the [Workflow API](docs/02-requirements/workflow-api.md).

### Operational UI

Dashboard, Approvals, unified Execution History, and typed Settings are available as authenticated
operational views. Metrics are computed server-side, history exposes only a normalized safe audit
read model, CSV neutralizes spreadsheet formulas, and preferences persist in PostgreSQL. See the
[Operational UI reference](docs/02-requirements/operational-ui.md).
