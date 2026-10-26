# VAYUJIT OS production activation plan

Status: preparation only. This package does not provision infrastructure,
create credentials, contact a marketplace, publish a listing, or promote
synthetic data. PR-SOS-09 local certification remains the evidence baseline;
this document records the HUMAN-controlled steps required before a real first
seller can be activated.

For immediate zero-hosting-cost private use on the owner's Windows PC, use the
separate PC-first operation, security, backup/recovery, and migration guides
linked below. This VPS plan remains the future remote-access path; it is not a
prerequisite to activating a loopback-only PC installation.

## Operating boundary

- One seller, one isolated installation, and one PostgreSQL database.
- Preserve `ck_users_single_owner`; do not introduce SaaS tenancy.
- Keep `VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP=true` and every live
  marketplace/provider mutation switch disabled until separately approved.
- Canonical owner, catalog, inventory, financial, marketplace, backup,
  readiness, and HUMAN-approval authorities remain the only authorities.
- Unknown values stay `UNKNOWN`; a completed form is not evidence of a legal,
  tax, supplier, or marketplace approval.

## Readiness classification

| Area | Current state | Exit evidence | HUMAN owner decision |
| --- | --- | --- | --- |
| PR-SOS-09 application and readiness projection | LOCALLY CERTIFIED | Existing PR-SOS-09 report and warning matrix | Acknowledge local-only scope |
| Linux host, domain, TLS, firewall | EXTERNALLY PENDING | Hardened host and witnessed HTTPS health checks | Choose host, domain, operator |
| PostgreSQL and durable media | EXTERNALLY PENDING | Private role, encrypted storage, restore witness | Managed versus self-hosted choice |
| Secret manager and rotation | BLOCKED | Secret references, rotation owner, recovery procedure | Approve secret custody |
| Encrypted off-server backup | EXTERNALLY PENDING | `age` recipient, off-server object, checksum and restore witness | Approve destination/RPO/RTO |
| Business identity and catalog | HUMAN INPUT REQUIRED | Owner-scoped records with evidence | Supply truthful business/product data |
| Amazon India account and API | UNVERIFIED - HUMAN FOLLOW-UP REQUIRED | Official account, developer/profile approval, authorized token, read-only test | Approve Amazon path |
| Flipkart account and API | UNVERIFIED - HUMAN FOLLOW-UP REQUIRED | Official seller account, Developer Access app, token, read-only test | Approve Flipkart path |
| External writes/publication | DENIED | Separate, auditable HUMAN authorization after all gates | Explicit go-live approval |

## Infrastructure preparation

### Sizing basis

The checked-in Compose limits are the only observed capacity evidence available
before real seller workload exists. They declare API 2 vCPU/2 GiB, worker 1
vCPU/1 GiB, web 0.5 vCPU/256 MiB, proxy 0.5 vCPU/256 MiB, and PostgreSQL at
least 1 vCPU/1 GiB as a starting envelope. They are not an SLO or a benchmark.

Use a provider-neutral starting host of **at least 6 vCPU, 12 GiB RAM, and
100 GiB encrypted SSD**, with expansion headroom. Do not purchase or provision
it from this repository. Before accepting the size, capture a representative
load window with `docker stats --no-stream`, PostgreSQL database size and
connection counts, media size, backup duration, disk utilisation, request
latency, and worker queue latency. Record peak and 95th percentile values and
increase the host if memory headroom is below 30%, disk headroom below 40%, or
the backup/restore target is missed.

The only live local observation available during preparation was an idle
PostgreSQL container snapshot on 2026-10-14: approximately 0.69% CPU, 1.359
GiB of 7.382 GiB available to that container, and 8.41 GiB block I/O. This is
not a seller workload or a production benchmark and must not be used as proof
of capacity. API, worker, web, media, backup, and peak-traffic measurements
remain HUMAN follow-up items before choosing a paid VPS size.

### PostgreSQL decision

Managed PostgreSQL is preferred when it provides private networking, a
dedicated least-privilege role, encryption, point-in-time or scheduled backup,
retention controls, and a witnessed restore. Self-hosted PostgreSQL is
acceptable only when VAYUJIT owns patching, WAL/storage monitoring,
replication or backup rotation, alerting, and restore operations. Do not expose
port 5432 publicly in either model.

### Domain and HTTPS

1. Select a VAYUJIT-owned domain and DNS operator; create only the required
   A/AAAA record to the approved proxy address.
2. Obtain a publicly trusted certificate through the chosen certificate
   authority or managed edge. Store `fullchain.pem` and `privkey.pem` outside
   the repository with mode `600` and mount them read-only at
   `VAYUJIT_TLS_CERT_DIRECTORY`.
3. Set `VAYUJIT_PUBLIC_WEB_DOMAIN`, `VAYUJIT_PUBLIC_WEB_URL`,
   `VAYUJIT_PUBLIC_API_URL`, and `VAYUJIT_ALLOWED_ORIGINS` to HTTPS values
   for the same approved origin.
4. Verify HTTP redirects to HTTPS, TLS renewal, HSTS, certificate hostname,
   `/health/live`, `/health/ready`, login, logout, and protected deep links.

### SSH, firewall, and database access

- Disable password SSH login and root SSH login; use individual keys, a named
  operator account, MFA/bastion or private access where available, and tested
  break-glass recovery.
- Allow inbound TCP 22 only from the approved operator network and TCP 443
  from the intended users. Keep 80 only for HTTP-to-HTTPS redirect if needed.
- Deny public PostgreSQL, worker, API, and web ports. Compose keeps these on
  the private internal network; only nginx is edge-facing.
- Use a dedicated application PostgreSQL role, separate migration/admin role,
  TLS/private connectivity, encrypted volumes, and no default `postgres` or
  `vayujit` production role.

### Secrets, storage, and backup

Store all values in a secret manager, not `.env.production` in Git. Required
secret classes are the database URL/password, session secret (32+ characters),
credential-encryption key and key ID, TLS private key, private media bucket
credentials, and the `age` backup recipient. Rotate one secret class at a
time, record the owner and expiry, restart only the affected services, and
verify login, encrypted credentials, backup, and readiness after rotation.

Use private durable object storage (`VAYUJIT_STORAGE_PROVIDER=s3` and a private
bucket) for media. Use `scripts/backup-production.sh` with a secret-managed
`VAYUJIT_BACKUP_AGE_RECIPIENT`, write checksums, copy the encrypted artifact to
an approved off-server destination, and test restore into a disposable marked
database. Keep the emergency stop active throughout.

## Deployment sequence

1. Owner approves host, domain, database model, storage, backup destination,
   RPO/RTO, operator list, and maintenance window.
2. Operator provisions and hardens the Linux host outside this repository.
3. Operator creates the private database/role, secret references, TLS mount,
   media bucket, and backup destination; no marketplace credential is needed
   for first boot.
4. Copy the placeholder template to a secret-managed
   `infrastructure/.env.production` with mode `600`; never commit it.
5. Run `scripts/validate-production-config.ps1 -Environment production` and
   `scripts/validate-deployment-reference.ps1`.
6. Run `bash scripts/deploy-reference.sh validate`; inspect the rendered
   Compose configuration and image digests.
7. Take and verify a pre-migration encrypted backup. Apply the API image's
   normal Alembic migration entrypoint, then run health/readiness and login
   checks while the proxy remains restricted.
8. Populate only truthful owner/business/catalog records through canonical
   authenticated workspaces. Keep unknowns explicit and do not import demo
   marketplace orders, inventory, or accounts.
9. Obtain separate marketplace approvals, perform only approved read-only
   certification, and review readiness. Do not enable writes yet.
10. Record the HUMAN go-live decision. `scripts/deploy-reference.sh apply`
    must not be run until `VAYUJIT_HUMAN_DEPLOY_APPROVED=YES` is explicitly
    supplied by the authorized owner.

## Monitoring and rollback

Monitor host CPU/memory/disk, PostgreSQL connections and storage, API 5xx and
latency, nginx TLS/renewal, worker heartbeat/queue latency, backup age,
checksum failures, media errors, and readiness blockers. Alert an explicitly
named operator; do not send telemetry or provider payloads to an unapproved
destination.

For an update, enable maintenance mode, verify a fresh encrypted backup, deploy
immutable image references, check migrations and health, then review readiness.
For rollback, keep the previous image/configuration, stop external mutations,
restore application images first, and never downgrade a partially applied
database migration. Restore data only into a marked disposable environment
until the owner witnesses the result.

## Owner information and approvals required

The VAYUJIT owner must provide or approve: legal business name and address,
owner/admin identity, verified email and phone, timezone, INR accounting
policy, GST/tax status and documents where applicable, bank/settlement details,
product/category/SKU data, truthful cost/price/stock/image evidence, supplier
evidence, return/shipping assumptions, host/domain choice, database/storage
choice, secret-manager owner, TLS renewal owner, backup destination and
retention, RPO/RTO, operator SSH keys, monitoring/on-call contact, marketplace
registration status, provider/API approvals, read-only certification, and the
separate external-write/go-live decision.

## PC-first local operational activation

The Windows package uses the production Angular build, API, worker, PostgreSQL,
and nginx reverse proxy. It publishes only `127.0.0.1:8443`, uses a separate
named PostgreSQL/media volume, and creates no demo data. The persistent PC
database remains inactive until the owner types the exact activation phrase.
Daily encrypted backups require owner registration of a current-user scheduled
task and a physically separate encrypted disk. Local HTTP is loopback-only,
not public HTTPS; containers intentionally have no runtime internet egress.
Live marketplace/provider connectivity remains unavailable until separate
review and authorization. See
[`pc-first-live-operation-guide.md`](pc-first-live-operation-guide.md),
[`pc-first-security-checklist.md`](pc-first-security-checklist.md),
[`pc-first-backup-recovery.md`](pc-first-backup-recovery.md), and
[`pc-to-vps-migration-guide.md`](pc-to-vps-migration-guide.md).
