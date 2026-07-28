# Testing Strategy

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

The integration command fails if the explicit configuration or marker is absent. Ordinary
integration fixtures currently perform guarded schema resets for isolation. Moving each test to
transaction/savepoint rollback remains a performance hardening opportunity.

