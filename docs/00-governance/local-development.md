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
