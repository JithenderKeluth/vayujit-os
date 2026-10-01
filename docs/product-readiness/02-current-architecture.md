# Current architecture map

## Runtime entry points

- API: `apps/api/vayujit_api/main.py`, started by `scripts/start-api.ps1` with Uvicorn on `127.0.0.1:8000`.
- Web: `apps/web`, Angular workspace served by `npm run start --workspace @vayujit/web`.
- Desktop: `apps/desktop/src/main.ts`, an Electron shell that builds/loads the web app.
- Local database: `infrastructure/docker-compose.yml` PostgreSQL 17-alpine bound to `127.0.0.1:5432`.
- Developer orchestration: `scripts/start-dev.ps1` runs database startup, migrations, and the three runtimes.

## Domain layers

FastAPI routers delegate to domain services and SQLAlchemy models. `apps/api/vayujit_api/intelligence` contains Business Agent, product/review/trend/competitor intelligence, external research, website fetch/evidence, supplier discovery, due diligence, sourcing economics, scenarios, and resilience. Workers and schedulers process durable jobs. Angular lazy routes cover seller, research, sourcing, commerce, growth, and operations surfaces. Shared package code lives in `packages/shared`.

## Control boundaries

Authentication/owner scoping, safety middleware, OriginProtection, CORS, ApprovedWebFetcher, provider runtime modes, kill switches, evidence/provenance, and the destructive test-database guard are existing architectural controls. These are foundations to preserve.
