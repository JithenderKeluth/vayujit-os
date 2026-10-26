# First-seller deployment runbook

This runbook is for one approved VAYUJIT installation on a Linux VPS. It is a
procedure for an authorized operator; it does not provision a host, issue
credentials, call a marketplace, or publish anything.

## Preconditions and no-go checks

- The owner has approved the host, domain, database, storage, backup, operator,
  maintenance window, and RPO/RTO.
- SSH/firewall hardening is complete and only nginx is edge-facing.
- A private PostgreSQL role/database and private durable media bucket exist.
- Secret-manager values are injected at runtime; the repository contains no
  filled `.env.production`.
- `VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP=true`, all live provider switches
  are false, email delivery is disabled, and no synthetic records will be
  promoted.
- A pre-migration encrypted backup and restore target are available.

Stop immediately if any prerequisite is UNKNOWN, if HTTPS is unavailable, if
the database is loopback/public, if media is filesystem-only in production, or
if a live credential/write switch is unexpectedly enabled.

## Prepare the host

Install a supported Linux distribution, Docker Engine/Compose plugin, `age`,
PostgreSQL client tools, a time-sync service, and host monitoring through the
approved OS repository. Create the operator account and SSH restrictions
outside this repository. Do not install provider CLIs or store provider
secrets unless separately approved.

## Prepare configuration

1. Copy `infrastructure/production.env.example` to a secret-managed path
   outside Git and set mode `600`.
2. Replace every placeholder with values from the secret manager. Use a
   dedicated PostgreSQL role, HTTPS public URLs, private bucket, backup
   directory, and mounted TLS directory.
3. Keep the following fail-closed values during activation:

   ```text
   VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP=true
   VAYUJIT_LIVE_MARKETPLACE_MUTATIONS_ENABLED=false
   VAYUJIT_LIVE_ADS_MUTATIONS_ENABLED=false
   VAYUJIT_LIVE_EMAIL_DELIVERY_ENABLED=false
   VAYUJIT_LIVE_AI_ENABLED=false
   ```

4. Confirm the TLS mount contains `fullchain.pem` and `privkey.pem` with
   operator-only permissions.

## Validate without starting services

From the repository root:

```bash
pwsh scripts/validate-production-config.ps1 -Environment production
pwsh scripts/validate-deployment-reference.ps1
bash scripts/deploy-reference.sh validate
docker compose --env-file infrastructure/.env.production \
  -f infrastructure/docker-compose.production.yml config --quiet
```

The first two commands may use the repository's placeholder-only validation
path; a real production run must use the secret-managed environment and pass
the production security validator. Review the rendered networks, volumes,
ports, image digests, and environment before any apply.

## Backup before migration

Keep maintenance mode and the emergency stop active. Export a PostgreSQL custom
format dump and encrypt it with `scripts/backup-production.sh`, verify its
checksum, copy it to the approved off-server destination, and record the
retention metadata. Restore a copy into a disposable marked database and
compare the Alembic revision, owner constraint, representative counts, media
checksums, and health/readiness before proceeding.

## First start and migration

The API image's checked-in entrypoint runs `alembic upgrade head` before the
API process. Start only after the backup and configuration checks pass. Keep
the proxy restricted while the migration completes. Verify:

```bash
docker compose --env-file infrastructure/.env.production \
  -f infrastructure/docker-compose.production.yml ps
curl --fail https://APPROVED_DOMAIN/health/live
curl --fail https://APPROVED_DOMAIN/health/ready
```

Check API, worker, proxy, and PostgreSQL logs for errors without exposing
tokens, credentials, buyer PII, or raw provider payloads. Authenticate as the
single owner and verify a protected deep link, logout, and owner-scoped
catalog/readiness view.

## Controlled update

1. Announce maintenance and confirm a fresh encrypted backup.
2. Set the emergency stop and keep all provider writes disabled.
3. Pin and verify image digests; do not deploy an unreviewed floating tag.
4. Run `deploy-reference.sh validate`, then apply only after HUMAN approval:

   ```bash
   VAYUJIT_HUMAN_DEPLOY_APPROVED=YES \
     bash scripts/deploy-reference.sh apply
   ```

5. Verify health, migration revision, login, readiness, media, backup, and
   Action Center state. Review errors and warnings before reopening users.

## Rollback and recovery

Do not downgrade a database migration. Stop writes, keep maintenance mode and
the emergency stop active, and restore the previous application image/config
first. If data restoration is required, restore only into a marked disposable
database, validate owner isolation and HUMAN controls, and obtain a separate
HUMAN decision before replacing the active database. Rotate any credential that
may have been exposed and record the incident.

## Post-deployment acceptance

The owner and operator jointly record the health URLs, certificate expiry,
database revision, backup checksum/location, restore witness, media bucket,
monitoring alerts, active warnings, and the explicit decision to remain
read-only or to authorize a later marketplace milestone. No marketplace
publication is part of this runbook.

