# PR-SOS-09.1 — Production-Like Deployment, Backup/Restore & First-Seller Certification

## A. Final decision

**PR-SOS-09 — IMPLEMENTED / LOCAL CERTIFICATION PENDING.**

The implementation and production-like disposable validation are complete. The
stronger “fully validated” classification is intentionally withheld because a
fresh isolated Chrome profile was unavailable, the required warning-specific
browser states (scenarios 12–20) were not populated in the final empty-state
run, and the repository-wide strict mypy baseline remains failing. This is not a
public deployment or production go-live certification.

**VAYUJIT PRODUCTION GO-LIVE — NOT YET CERTIFIED.**

## B. Scope and safety boundary

One owner, one installation, one PostgreSQL database. `ck_users_single_owner`
was preserved. No golden database, supplier, provider, marketplace, OAuth,
RFQ, procurement, payment, inventory publication, or external write was used.
No PR-SOS-10 work was started.

## C. Canonical implementation

The authenticated `/operations/launch-readiness` page remains a projection of
the existing system health, Catalog, Marketplace, Financial, Operations,
Action Center, approval, and audit authorities. No duplicate launch authority
or approval store was introduced.

Production-like assets now include API/worker and web images, private Compose
networking, loopback-selectable TLS proxy bindings, health/restart/resource
controls, a fail-closed configuration preflight, and the encrypted
`pg_dump | age` backup helper. The worker entrypoint was corrected to invoke
Python directly, and its healthcheck now verifies the durable worker heartbeat
instead of probing a nonexistent HTTP port. Migration readiness now compares
against the configured expected revision (`20261203_0146`).

## D. Disposable production-like startup

`docker compose -p prsos091 -f infrastructure/docker-compose.production.yml up
-d` was executed with temporary local-only secrets/TLS and loopback bindings.
API, web, proxy, Postgres, and worker started; API, web, Postgres, and worker
reported healthy. `/api/v1/system/health` returned `healthy`; migration
`20261203_0146` matched the configured expected revision. The authenticated
production-readiness projection reported configured database, encryption,
storage, backup directory, secure cookie/HTTPS, emergency stop, and all live
mutation switches disabled. Release readiness correctly remained conditional
on configuration and live-provider signoff.

## E. Seeded canonical records

Using the authenticated app APIs in the disposable database, the witness
created one owner, one brand, one active catalog product, one opening inventory
balance, one sandbox marketplace-account record, one seller-entered financial
event, one product-cost evidence row, and one local draft/listing record. These
are local validation records only; no remote marketplace transport was called.

## F. Backup artifact

The repository helper `scripts/backup-production.sh` produced:

| Evidence | Result |
|---|---|
| Encrypted artifact | `tmp/pr-sos-091/backup/vayujit-20261013T185012Z.dump.age` |
| Size | 2,281,620 bytes |
| Header | `age-encryption` prefix (`6167652d...`) |
| Plaintext marker scan | none (`CREATE TABLE`, `users`, `inventory_items`) |
| Checksum sidecar | produced by helper; checksum validation performed |
| Backup/restore timing | helper/restore completed in the disposable run; exact timing is tool-run dependent |

The age recipient/private key was generated inside the disposable tool
container and was not persisted to the repository.

## G. Restore and reconstruction

The encrypted artifact was decrypted into a separate disposable database with
`pg_restore`. Reconstructed evidence:

| Check | Result |
|---|---|
| users | 1 |
| products | 1 |
| inventory_items | 1 |
| financial_events | 1 |
| audit_events | 6 |
| marker | `PR-SOS-09.1-disposable` |
| Alembic revision | `20261203_0146` |
| `ck_users_single_owner` | present (1 constraint) |
| Decimal product price/cost | `1299.00` / `650.00` preserved |
| inventory quantity | 24 preserved |
| owner identity | `prsos091@example.com` preserved |
| fresh API-container Python process | read owner=1, product name, inventory=24 |

The separate restore database was dropped after verification. Wrong-age-key and
tampered-artifact decryptions both exited non-zero. No plaintext backup was
retained.

## H. Browser certification

The direct CDP harness `scripts/pr-sos-09-browser-smoke.mjs` has 36 checks and
saved 36 production-like screenshots under
`tmp/pr-sos-091/browser-production/` (the earlier witnessed run passed 36/36),
covering authenticated launch readiness, navigation/deep links, protected
routes, logout/reauthentication, responsive widths 360/390/768/1024/1440,
history assertions, and launch-state axe. The adjacent PR-SOS-08.2 harness
passed 35/35 with 12 axe states and zero violations.

Required warning-specific scenarios 12–20 were **NOT EXECUTED** in the final
fresh marker database because no warning/approval fixture was promoted into
that browser run. A fresh isolated Chrome profile launch also failed in this
environment; the successful CDP run used the existing isolated CDP surface.
These are explicit certification gaps, not inferred passes.

## I. Accessibility and responsive evidence

The launch-state axe scan passed with 0 violations and 0 incomplete checks.
Responsive checks passed at 360, 390, 768, 1024, and 1440 px. The adjacent
marketplace harness covered 12 axe states and keyboard traversal. A full
12-state axe matrix for every launch-warning/approval state and a dedicated
manual keyboard audit for every new state remain pending.

## J. Security and owner isolation

HTTPS/secure-cookie settings, trusted-origin checks, private Postgres
networking, deny-by-default external mutation switches, emergency stop, and
HUMAN deployment acknowledgement remain enabled. No secrets were written to
logs or documentation. Single-owner enforcement and owner-scoped APIs were
verified in the adjacent PostgreSQL regressions.

## K. Regression and quality results

| Check | Result |
|---|---|
| Focused PR-SOS-09 deployment tests | 4 passed, 3 expected warnings |
| PR-SOS-07 + PR-SOS-08 + PR-SOS-09 PostgreSQL matrix | 16 passed, 13 expected warnings |
| Full Angular suite | 64 files / 226 tests passed |
| Production Angular build | passed; 514.37 kB initial bundle, 14.37 kB advisory over budget |
| Angular lint | 0 errors, 2 pre-existing campaign-dialog warnings |
| Ruff / Black / compileall / `git diff --check` | passed |
| Migration cycle | passed through head `20261203_0146` |
| Full strict mypy | 222 pre-existing errors in 28 files; bounded config CLI check passed |
| Compose/reference validator | passed with temporary placeholders |

## L. Required gate ledger

| Gate family | Status |
|---|---|
| Production-like Compose startup/restart/readiness | PASS |
| API/web/Postgres/worker health | PASS |
| Configured migration readiness | PASS |
| Marker-protected disposable DB and single owner | PASS |
| Catalog/inventory/financial/audit evidence | PASS |
| Encrypted backup + plaintext rejection | PASS |
| Separate restore + row/identity/Decimal reconstruction | PASS |
| Wrong-key/corruption rejection | PASS |
| 30+ authenticated browser checks | PASS (36/36 witnessed) |
| Required warning-state browser scenarios 12–20 | NOT EXECUTED |
| Full 12-state launch axe matrix | NOT EXECUTED |
| Fresh isolated Chrome profile | BLOCKED by local CDP launch environment |
| Full strict mypy | BLOCKED by pre-existing repository debt |
| Real marketplace/provider/public deployment | OUT OF SCOPE / NOT AUTHORIZED |

## M. Documentation and changed files

The implementation changes are in the earlier PR-SOS-09 slice plus the bounded
09.1 corrections: `infrastructure/docker-compose.production.yml`,
`apps/api/vayujit_api/operations/hardening.py`,
`apps/api/vayujit_api/settings/router.py`,
`apps/api/tests/test_pr_sos_09_deployment.py`, and
`scripts/pr-sos-09-browser-smoke.mjs`. This report supplements
`docs/seller-os/pr-sos-09-validation.md`; roadmap and capability-matrix entries
now reference the production-like witness and its remaining gates.

## N. Cleanup

Temporary production env, session cookie, TLS files, restore database, and
private age key material were removed. The disposable Compose containers may
be removed with the exact project name `prsos091`; no persistent/golden data is
affected.

## O. Final classification

**PR-SOS-09 — IMPLEMENTED / CERTIFICATION PENDING.**

The remaining blockers are bounded browser-state coverage (warning/approval
scenarios and full launch axe matrix), fresh-profile CDP availability, and the
repository-wide strict-mypy baseline. Production go-live remains separately
uncertified.
