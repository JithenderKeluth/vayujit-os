# VAYUJIT OS

VAYUJIT OS is a local-first, AI-powered business operating system for
entrepreneurs and small businesses managing commerce, content, automation, and
analytics.

## Sprint 0 documentation

### Product

- [Product Vision](docs/01-product/product-vision.md)
- [Product Requirements Document](docs/01-product/product-requirements-document.md)
- [Initial MVP Scope](docs/01-product/mvp-scope.md)
- [Software Requirements Specification](docs/02-requirements/software-requirements-specification.md)

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

- Node.js 22.22.3 or newer and npm
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
