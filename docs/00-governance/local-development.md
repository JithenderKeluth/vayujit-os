# Local Development

## Start

```powershell
npm.cmd install
npm.cmd run api:install
npm.cmd run db:up
npm.cmd run db:migrate
npm.cmd run dev
```

Open `http://127.0.0.1:4200` or use Electron. Sign in, then open **Brands**.

## Brand migration

Revision `20260727_0003` creates `brands`, `audit_events`, uniqueness constraints, and the partial
active-context index.

Revision `20260727_0004` creates products, product indexes, ownership/uniqueness rules, decimal
commerce columns, and lifecycle/inventory database checks.

Revision `20260728_0005` creates prompt templates, AI generation requests, generated artifacts,
review constraints, and the default deterministic product-content template.

Revision `20260728_0006` creates publishing destinations, executions, immutable attempts,
owner-scoped idempotency, snapshots, lifecycle checks, and query indexes.

Revision `20260728_0007` creates constrained Workflow templates, instances, step attempts, and
the default Product Content Publish template.

Revision `20260728_0008` creates one typed owner-preference row with validated display,
pagination, AI, and Publishing defaults.

```powershell
cd apps\api
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe downgrade 20260727_0002
.\.venv\Scripts\alembic.exe upgrade head
cd ..\..
```

Downgrading removes all brand and audit data. Use only on a disposable database or after a
backup.

## Tests

Do not export a test URL manually into a general development shell. Use the guarded commands:

```powershell
npm.cmd run test:api
npm.cmd run test:api:integration
npm.cmd run test:api:migrations
```

The development database `vayujit` is intended for manual application data and is never
automatically reset. Integration tests use marked `vayujit_test`; migration validation creates
and removes marked `vayujit_migration_test`. See the [testing strategy](testing-strategy.md) and
the [2026-07-28 incident note](incident-2026-07-28-test-database.md).

## Electron runtime

Use Node 22 LTS (preferred) or Node 24 with Electron 43.2.0. `npm.cmd run dev:desktop` waits for
Angular and launches the compiled main process through Electron. The launcher clears
`ELECTRON_RUN_AS_NODE` only for that child; otherwise Electron behaves like plain Node and ESM
imports report that `BrowserWindow` is unavailable.

```powershell
npm.cmd run dev:web
npm.cmd run dev:desktop
npm.cmd run test:desktop:smoke
```

Startup logs confirm Electron readiness, secure BrowserWindow creation, and renderer readiness.

After signing in, select an active brand before creating a product. Product creation defaults to
that brand, while the product list can explicitly select another owned brand or all brands.

Open **AI Content** to generate content for a non-archived product. The current provider is local
and deterministic; it does not contact Ollama or any cloud service. Review drafts can be
approved, rejected with a reason, regenerated, and inspected after restart.

Open **Publishing** after approving an Artifact. Create a destination, select Brand → Product →
approved version → compatible destination, review the preview, and confirm. In development only,
expand **Development testing** on the destination form to simulate retryable or permanent failure.
Correct a retryable destination and use the execution-details retry action; the original immutable
snapshot is reused.

Browser validation: complete the journey, refresh execution details, then log out and confirm
`/publishing` redirects to login. Electron validation repeats login, destination selection,
publication, execution inspection, and restart/session restoration. Mock `.invalid` URLs are
display-only and should never be navigated.
Default Brand, prompt-template, and Publishing-destination choices are persisted by the API, not
only browser storage. Refresh Settings and the consuming AI or Publishing flow to validate
server persistence and compatibility fallback.
