# Production deployment runbook

1. Provision PostgreSQL and private media storage; do not place credentials in images.
2. Generate session and credential-encryption keys in the secret manager.
3. Set `VAYUJIT_ENVIRONMENT=production`, HTTPS origins, `VAYUJIT_REQUIRE_HTTPS=true`, secure cookies, and all live switches false.
4. Verify `apps/api/.venv/Scripts/alembic.exe -c apps/api/alembic.ini current`, take a backup, then run migrations with `scripts/migrate-api.ps1`.
5. Deploy API, worker, scheduler, and web; verify `/health/live`, `/health/ready`, and authenticated `/api/v1/system/production-readiness`.
6. Run the local smoke and security matrices before enabling any provider.
7. Roll back application binaries first; downgrade migrations only under an approved recovery plan and after a fresh backup.

This foundation does not deploy infrastructure or activate provider mutations.