# WP0A — Isolated disposable QA PostgreSQL setup

Date: 2026-10-28. Scope: explicitly approved local QA infrastructure only.
WP0B and the seller-experience browser matrix have **not** been started.

## Verified instance

| Item | Actual value |
| --- | --- |
| Container / Compose project | `vayujit-qa-postgres` |
| Container ID | `a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23` |
| Instance UUID | `389b97d2-a4cd-4d9b-972e-6bb2bf5785eb` |
| Docker engine ID | `b82fa04a-7a17-4c56-b3eb-37bb601e6fa1` |
| PostgreSQL | `17.10`; application deployment templates use major 17 |
| Endpoint | `127.0.0.1:55432` → container `5432/tcp` |
| QA login / database owner | `vayujit_qa_admin` |
| Allowed test database | `^vayujit_qa[a-f0-9]{16}_test$`, exact token match required |
| Dedicated storage | `vayujit-qa-postgres-data` |
| Dedicated networks | `vayujit-qa-postgres-net` and `vayujit-qa-postgres-host` |
| Pinned image | `postgres@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193` |

Preflight found the proposed container, networks and storage absent, and the
loopback port free. The existing `infrastructure-postgres-1` on port 5432 and
nine other historical containers were inventoried, not reused or modified.
The pinned image was already cached; no image download was required.

The private network is internal. On this Docker Desktop engine, an internal-only
network did not actually publish the requested port, despite HostConfig listing
it. A second **QA-only** bridge was added to this newly created QA container;
no container, network or volume was removed. Its masquerading is disabled and
the actual published mapping is checked, not merely the Compose declaration.
Neither QA network has an unrelated container attached. This is not a claim of
host-wide firewall or absolute outbound-network isolation.

## Credentials and authority

Locally generated cryptographic random credentials and signing key are stored
under Git-ignored `tmp/qa-postgres-private/`. NTFS ACLs permit the current Windows
owner and SYSTEM only, with inheritance disabled on the private root and credential
files. Python and PowerShell entry points check these ACLs before credential use.
Reparse-point paths are rejected. No production `.env` was changed.

The QA role has LOGIN and CREATEDB, but **not** SUPERUSER, CREATEROLE, REPLICATION,
BYPASSRLS, or role memberships. It cannot CREATE in the maintenance database or
its public schema, or UPDATE/DELETE the bootstrap-owned instance identity.
The bootstrap `postgres` account is confined to initialization of this separate
server; the harness never uses its credential. No production data is mounted.

PostgreSQL CREATEDB cannot itself enforce a database-name pattern. The name/token
restriction is enforced by the approved harness, not misrepresented as a database
ACL. A trusted Windows/Docker administrator or someone given the QA credential can
bypass a client-side harness; do not distribute these credentials. Database-owner
privileges apply only inside this dedicated PostgreSQL instance. See the official
[PostgreSQL role privilege model](https://www.postgresql.org/docs/17/role-attributes.html).

## Guarded creation and deletion

`qa/postgres_instance.py` checks the Docker engine, exact container/image IDs,
instance labels, loopback binding (including effective mapping), network membership,
mount allowlist, server identity, login and privilege attributes. Signed instance
and lifecycle records prevent accidental target substitution.

Creation requires a fresh 16-hex suite token and exclusive lifecycle lock. It
records instance, container, exact database name, owner, token, PostgreSQL OID,
creation UUID and state. The database contains the canonical project marker plus
the matching token and creation UUID.

Deletion requires the matching signed ACTIVE lifecycle, current server identity,
database owner/OID and database marker. Active connections cause refusal. No
`DROP ... FORCE`, session termination, prefix cleanup, or Docker prune is used
for this instance. Missing or ambiguous state is retained for investigation,
never automatically adopted or deleted.

The existing fixture server and recovery cleanup now require this guard whenever
the dedicated QA role or manifest is selected. Historical test-environment paths
were not granted authorization by this task.

## Local commands

From the repository root, with Docker Desktop running:

```powershell
# Verify identity, ACLs, endpoint and PostgreSQL role.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\qa-postgres.ps1 -Action Status

# Stop only this attested QA container; retain its dedicated storage.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\qa-postgres.ps1 -Action Stop

# Restart the same container. Check Status once healthy.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\qa-postgres.ps1 -Action Start
```

Do **not** rerun `-Action Create` for this installation. Any resource/profile name
collision is a hard stop; there is no overwrite/reuse/removal fallback.
Do not run Compose `down -v`, Docker prune, or an unrelated stack command.

For future approved WP0B work, configure the **current PowerShell process** without
printing or pasting a database URL:

```powershell
& .\scripts\qa-postgres.ps1 -Action Environment
# Sets QA_DATABASE_ADMIN_URL, QA_POSTGRES_INSTANCE_MANIFEST and QA_PYTHON
# in this shell only. Do not echo them or save them in production .env.
```

Do not invoke Environment in a separate `powershell.exe -File` process and expect
its variables to persist in the parent shell. The URL alone is insufficient:
the manifest, private ACLs, instance checks and signed lifecycle remain required.

To repeat only WP0A's bounded validation (not browser journeys):

```powershell
& .\apps\api\.venv\Scripts\python.exe -m qa.validate_postgres_instance
& .\apps\api\.venv\Scripts\python.exe -m unittest discover -s qa/unit -p 'test_*.py'
```

No additional infrastructure approval is required for the validated instance
within this scope. **Stop here before WP0B.** Permanent business activation,
other database targets, resource removal and real providers remain unauthorized.
