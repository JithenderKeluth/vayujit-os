# Testing Strategy

Real-provider tests never contact a paid external service. Unit coverage uses
HTTP mock transports; guarded integration coverage uses a deterministic local
fake OpenAI-compatible server and marked PostgreSQL test database. Migration
validation cycles from a clean database through `0010`, down to `0009`, and
back to `0010`.

## Database separation

`vayujit` is the manual development database. Automated tests never select or reset it.
`vayujit_test` is dedicated to API integration tests. `vayujit_migration_test` exists only during
the Alembic upgrade/downgrade cycle and is removed afterward.

Destructive test operations require all of the following:

- `VAYUJIT_ENV` is exactly `test`;
- the URL came from explicit `VAYUJIT_TEST_DATABASE_URL`;
- the database name matches `^vayujit(?:_[a-z0-9]+)*_test$`;
- the name is not `vayujit`, `postgres`, or a PostgreSQL template database;
- the configured and connected database names match;
- `test_database_marker` contains `vayujit-os-disposable-test-database-v1`.

Errors display only host/database and never credentials. An existing unmarked database is refused,
not adopted. All schema resets use the centralized `reset_test_schema` helper. The migration
script repeats the marker check immediately before removing its disposable database.

The local Docker role is not a superuser and can access databases it owns. For stronger local
separation, create a dedicated non-superuser test role with privileges only on `vayujit_test` and
`vayujit_migration_test`; do not grant it access to `vayujit`.

## Commands

```powershell
npm.cmd run test:api
npm.cmd run test:api:integration
npm.cmd run test:api:migrations
npm.cmd run test:workflow
npm.cmd run test:web
npm.cmd run test:desktop
npm.cmd run test:desktop:smoke
npm.cmd test
```

Operational integration coverage exercises owner-scoped Dashboard counts, Approval queues,
normalized history/CSV, typed preferences, password verification, session summaries, and redacted
system status through the same marked disposable database.

The integration command fails if the explicit configuration or marker is absent. Ordinary
integration fixtures currently perform guarded schema resets for isolation. Moving each test to
transaction/savepoint rollback remains a performance hardening opportunity.
Operational UI regression includes safe Artifact field/array diff tests, owner-preference
validation and invalidation, default-flow preselection, guarded database integration, Electron
launcher smoke, and rendered browser/Electron inspection when those interactive surfaces are
available. Automated smoke results must not be described as visual validation.
Production-hardening tests cover correlation validation, redaction, maintenance enforcement,
backup traversal/checksum failure, health, release, recovery, audit filtering, guarded migration,
and non-destructive commands. Restore validation is allowed only against an explicitly marked
disposable restore-test database.
