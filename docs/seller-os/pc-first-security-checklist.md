# PC-first security checklist

This checklist describes the local Windows profile and its limits. Passing it
does not make loopback HTTP equivalent to production HTTPS.

## Host and network

- [ ] Windows login is unique to the VAYUJIT owner, protected by a strong
  password and device sign-in protection; screen lock is enabled.
- [ ] BitLocker/device encryption is enabled for the Windows system/data disk.
- [ ] Docker Desktop uses WSL 2 Linux containers and is kept updated.
- [ ] Windows Firewall remains enabled. Do not add inbound rules, router port
  forwarding, tunnels, LAN binding, public DNS, or public reverse proxy.
- [ ] The only published application port is `127.0.0.1:8443`; PostgreSQL,
  API, worker, and web are not host-published.
- [ ] Compose's internal network has no external egress; live provider,
  marketplace, SMTP, supplier, and payment operations remain disabled.
- [ ] `VAYUJIT_ENVIRONMENT=pc_local`, `DEBUG=false`, exact Origin checking,
  emergency stop enabled, and live mutation/email switches false are retained.
- [ ] The generated database URL targets the private `postgres` service and
  dedicated `vayujit_business` database/`vayujit_app` role. Do not change it to
  localhost, the development DB, or a test DB.

## Secrets and account

- [ ] Generated `app.env`, `compose.env`, `pc-install.json`, and
  `backup.agekey` are outside the repository and ACL-restricted to the current
  Windows user and SYSTEM.
- [ ] No secret is copied into source control, screenshots, chat, command
  history, cloud-synced folders, or a support ticket.
- [ ] The age identity has a separately secured offline recovery copy. Test
  recovery custody before relying on the backup.
- [ ] The first application owner is created through the normal first-owner
  flow with unique credentials; no `ownerExists` environment variable is
  required or supported.
- [ ] The owner can log in, log out, and confirm protected routes require
  authentication.

## Business and external action controls

- [ ] `ck_users_single_owner` remains unchanged; this installation is not
  shared with another seller or user.
- [ ] No synthetic products, suppliers, marketplace accounts, orders, stock,
  financial events, or approvals were imported.
- [ ] Unknown product, tax, cost, inventory, supplier, and authorization facts
  remain explicitly unknown.
- [ ] No marketplace/provider credential is entered until its purpose and
  secure storage have been separately reviewed.
- [ ] Supplier outreach, RFQ/email, procurement, payment, publication, and
  marketplace mutations remain disabled and require their existing canonical
  HUMAN workflows and distinct approvals.
- [ ] No real external action is inferred from local readiness or a successful
  browser/API health response.

## Backup and recovery

- [ ] Backup path is a different physical disk, verified by
  `Get-Partition`; it is encrypted and physically secured.
- [ ] Daily Task Scheduler registration is explicitly approved and runs under
  the owner's interactive Windows account while logged in and Docker Desktop
  is running.
- [ ] A first encrypted DB + media backup succeeds and is verified; the
  age-key recovery copy is tested.
- [ ] The owner reviews `last-backup-status.json` and Task Scheduler history
  after the first run and periodically thereafter.
- [ ] A restore is rehearsed only to a distinct marked disposable target; never
  overwrite the business database during a drill.

## Unmet production requirements

The local profile has no public HTTPS, remote access, centralized secret
manager, offsite monitoring, automated alert delivery, or marketplace
connectivity. A second physical disk in the same room is not disaster recovery.
Any of those needs requires the separate Linux/VPS plan, owner approvals, and
security/restore certification before data or access is moved.

## Local certification record (2026-10-15)

The disposable deployment passed its 17 runtime, security, and persistence
checks and 25 authenticated Chrome checks. The proxy was bound only to loopback,
app and data networks were internal, the proxy's egress probe to TEST-NET was
blocked, and only the proxy had a published port. The worker was attached only
to the private data network. Disposable owner/catalog/cost/stock/media records
were authenticated, persisted through Compose stop/start, and removed with the
uniquely named test volumes. `infrastructure-postgres-1` remained running and
was not used by the test.

The permanent PC profile has **not** been initialized or activated. Encrypted
backup and independent restore gates remain blocked until approved
`age`/`age-keygen` Windows binaries are available and the owner attaches an
encrypted second physical disk. Docker Desktop itself was not restarted, so
Windows reboot/daemon recovery remains unverified. Disposable runtime checks
alone do not authorize real-data activation.
