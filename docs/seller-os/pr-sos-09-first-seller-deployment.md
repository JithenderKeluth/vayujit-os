# PR-SOS-09 first-seller deployment guide

This is the portable, one-seller/one-installation/one-database reference for a
Linux VPS. It does not provision infrastructure or contact a provider.

## Topology

Use a private PostgreSQL service (managed PostgreSQL is preferred where it is
affordable), the FastAPI API and publishing worker as separate processes, the
Angular production bundle behind nginx, private durable object storage, and an
off-host encrypted backup destination. PostgreSQL and worker ports stay on the
private Docker network. Only nginx exposes 80/443.

`infrastructure/docker-compose.production.yml` is the reference topology;
`Dockerfile.api`, `Dockerfile.web`, and the nginx template are intentionally
vendor-neutral. Set `VAYUJIT_PUBLIC_WEB_DOMAIN` and mount a secret-managed TLS
certificate directory before use.

## First boot

1. Provision a patched Linux VPS and a private PostgreSQL database/role. Do not
   use the `postgres` or `vayujit` default role in production.
2. Copy `infrastructure/production.env.example` to a secret-managed
   `infrastructure/.env.production`, set mode `600`, and inject session,
   encryption, database, storage, and backup secrets from the secret manager.
3. Run `scripts/validate-production-config.ps1 -Environment production` (or
   the equivalent Python command on Linux). Missing HTTPS, durable storage,
   encryption, database, or session settings must fail closed.
4. Run `scripts/deploy-reference.sh validate`, create a verified pre-migration
   backup, then apply migrations with the API image. Re-run readiness and login
   checks before opening the proxy.
5. Keep `VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP=true` and all live provider
   switches false until the relevant HUMAN approvals and provider certification
   are recorded.

## Managed versus self-hosted PostgreSQL

Managed PostgreSQL reduces patching, failover, and storage work but requires a
private network path, role restrictions, provider backup evidence, and a
witnessed restore. Self-hosted PostgreSQL is portable and lower-cost at small
scale but requires patching, WAL/storage monitoring, replication/backup
rotation, and an operator-tested restore. Neither option is certified by this
local milestone.

## Resource sizing assumptions

The reference limits are a starting point, not an SLO: API 2 vCPU/2 GiB,
worker 1 vCPU/1 GiB, web/proxy 0.5 vCPU/256 MiB each, and PostgreSQL at least 1
vCPU/1 GiB plus durable storage. Measure actual catalog/media volume, worker
concurrency, database connections, and backup bandwidth before selecting a VPS.

## Safe deployment and rollback

Run `deploy-reference.sh validate` before `apply`. Keep the previous image and
configuration available. Roll back application images first; never downgrade a
partially applied database migration. Keep the maintenance marker and emergency
stop active during recovery, restore only into a marked disposable environment,
then verify owner isolation, HUMAN controls, health, and readiness.
