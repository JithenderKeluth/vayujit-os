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

PostgreSQL integration tests require an isolated database:

```powershell
$env:VAYUJIT_TEST_DATABASE_URL =
  'postgresql+psycopg://vayujit:vayujit_dev@127.0.0.1:5432/vayujit_test'
npm.cmd test
```

The tests reset that database. Never use the development database as the test database.

After signing in, select an active brand before creating a product. Product creation defaults to
that brand, while the product list can explicitly select another owned brand or all brands.

Open **AI Content** to generate content for a non-archived product. The current provider is local
and deterministic; it does not contact Ollama or any cloud service. Review drafts can be
approved, rejected with a reason, regenerated, and inspected after restart.
