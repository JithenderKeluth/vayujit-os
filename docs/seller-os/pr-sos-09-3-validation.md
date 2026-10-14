# PR-SOS-09.3 - Final Certification Recovery and Production Launch Gate

Date: 2026-10-14  
Scope: local, production-like, read-only certification recovery.  
Final classification: **PR-SOS-09 - IMPLEMENTED / LOCAL CERTIFICATION PENDING**.

## A. Decision summary

The production-like stack now starts with a reachable nginx edge proxy, the
authenticated browser witness can use that proxy, and the changed auth
bootstrap path is regression-tested. The local launch gate is not closed:
the required independently reproducible warning-fixture matrix was not
implemented and witnessed for every warning dimension, and a fresh Chromium
CDP profile could not be started in this Windows environment. No production
go-live claim is made.

## B. Preserved evidence

The following earlier evidence remains valid and was not invalidated by the
bounded PR-SOS-09.3 changes:

- encrypted backup and separate restore/reconstruction witness from PR-SOS-09.1;
- 227/227 Angular tests;
- 29/29 authenticated browser assertions;
- 12 axe states with zero violations and zero incomplete results;
- relevant PR-SOS-07/08/09 PostgreSQL regressions;
- one-seller/one-installation architecture and `ck_users_single_owner`.

## C. Changes made

1. `infrastructure/docker-compose.production.yml` keeps Postgres, API,
   worker, and web on an `internal: true` `private` network. Only nginx is
   dual-homed on `private` and `edge` and publishes host ports. This fixes
   the original Docker host-port failure caused by publishing from an
   internal-only network.
2. `apps/api/vayujit_api/core/observability.py` separates idempotent GET
   `/api/v1/auth/setup-status` and `/api/v1/auth/me` bootstrap reads from the
   credential/session-mutation rate-limit bucket. Normal deep-link refreshes
   therefore do not consume the login/logout budget; mutation routes remain
   subject to the strict auth limit.
3. `apps/api/tests/test_auth_integration.py` adds a regression that performs
   12 setup-status/me refresh pairs and verifies logout remains available.

No canonical business authority, approval boundary, marketplace adapter,
golden database, or external provider was changed.

## D. Disposable stack and environment

The unique Compose project was `prsos093`. It used disposable database
`prsos093`, marker-protected local credentials, a self-signed certificate,
and host ports 18081 (HTTP) and 18444 (HTTPS). Temporary files were
`infrastructure/.env.production` and `infrastructure/tls/*`; they are not
production secrets and are removed during teardown.

Commands used:

```powershell
$env:POSTGRES_DB='prsos093'
$env:POSTGRES_USER='app_role'
$env:POSTGRES_PASSWORD='prsos093-db-secret'
$env:VAYUJIT_PUBLIC_WEB_DOMAIN='127.0.0.1.nip.io'
$env:VAYUJIT_HTTP_BIND='18081'
$env:VAYUJIT_HTTPS_BIND='18444'
$env:VAYUJIT_TLS_CERT_DIRECTORY=(Resolve-Path infrastructure/tls).Path
docker compose -p prsos093 -f infrastructure/docker-compose.production.yml up -d
docker compose -p prsos093 -f infrastructure/docker-compose.production.yml config --quiet
docker compose -p prsos093 -f infrastructure/docker-compose.production.yml ps
```

All five services became healthy. `docker port` returned mappings only for
`proxy`; Postgres/API/worker/web had no host-published ports. Postgres was
reachable only on `private` and the proxy was the only edge entry point.

## E. Reverse-proxy HTTP evidence

Through `https://127.0.0.1.nip.io:18444` (using curl `--resolve` and `-k` for
the disposable certificate):

| Route | Result |
|---|---|
| `/health/live` | HTTP 200 |
| `/health/ready` | HTTP 200 |
| `/api/v1/system/health` without auth | HTTP 401 |
| `/dashboard` | HTTP 200 Angular shell |
| HTTP port 18081 with the correct Host | HTTPS redirect |

The response included CSP, HSTS, X-Frame-Options DENY, X-Content-Type-
Options nosniff, Referrer-Policy, and Permissions-Policy. nginx forwards
Host, X-Real-IP, X-Forwarded-For, and X-Forwarded-Proto to the API.

## F. Browser witness

Command:

```powershell
node scripts/pr-sos-09-2-browser-certification.mjs
```

The runner used direct Chrome/CDP against the proxy origin and a dedicated
local profile. The final summary is
[`tmp/pr-sos-093/proxy-browser-final/summary.json`](../../tmp/pr-sos-093/proxy-browser-final/summary.json)
and contains 29/29 passes:

- AUTH-01..03: setup/login, logout, protected deep-link rejection;
- WARN-01..04: warning section, evidence/action links, same-origin routes,
  no production-ready claim;
- AXE: 12 states, all `violations: []` and `incomplete: []`;
- RESP: 320, 360, 390, 768, 1024, and 1440 pixels with no horizontal
  overflow;
- KEY-01..02: visible keyboard focus and usable warning page;
- NAV-01..02: back and forward restore the expected routes.

Screenshots for each assertion are retained under
`tmp/pr-sos-093/proxy-browser-final/`.

## G. Auth/deep-link rate-limit defect

The first proxy run passed 28/29 because repeated authenticated page reads
consumed the same bucket as logout and caused a 429. The smallest generic
repair was to classify only the two safe GET bootstrap endpoints separately;
credential/session mutations still use the existing auth limit. After the
repair the same run passed AUTH-03 and all 29 checks.

## H. Warning fixture matrix

The canonical UI projection and browser witness cover warning shape,
severity/evidence/action rendering, source navigation, refresh, and the
HUMAN boundary. The required independent marker-protected fixture matrix is
not yet closed:

| Dimension | Projection/browser evidence | Independent fixture + negative resolution |
|---|---|---|
| business profile | existing readiness projection/axe state | NOT EXECUTED |
| product cost | existing Angular/readiness warning coverage | NOT EXECUTED |
| product image | existing Angular/readiness warning coverage | NOT EXECUTED |
| listing/mapping | existing projection/axe state | NOT EXECUTED |
| stock/inventory | existing projection/browser source link | NOT EXECUTED |
| finance | existing projection/browser source link | NOT EXECUTED |
| marketplace account | existing projection/browser source link | NOT EXECUTED |
| unverified/provider state | existing projection/HUMAN boundary | NOT EXECUTED |
| approval/action-center state | existing projection/browser source link | NOT EXECUTED |
| external mutation kill switch | existing projection/browser no-write claim | NOT EXECUTED |

This is a local certification blocker, not a reason to weaken the readiness
authority or fabricate business data. The smallest follow-up is a
marker-protected disposable fixture builder using canonical APIs, one case
per row, followed by the same CDP assertions and a legitimate resolution
case for each row.

## I. Fresh Chromium isolation

A fresh non-privileged profile was attempted on a second CDP port with an
empty `tmp/pr-sos-093/fresh-profile` directory. Chrome exited before opening
the debugging endpoint (`127.0.0.1:9224` refused connection), so a fresh-
profile claim is not made. The 29/29 witness used the existing dedicated
isolated CDP profile on port 9223; this is equivalent session isolation
evidence but not a fresh-profile pass.

## J. Python quality tooling

A disposable project virtual environment was created by the supported API
editable install (`apps/api[dev]`). Results:

| Check | Result |
|---|---|
| Ruff, changed files | PASS |
| Black, changed files | PASS |
| strict mypy, changed middleware | PASS |
| `python -m compileall -q vayujit_api` | PASS |
| repository Ruff | FAIL, one historical `I001` in `vayujit_api/main.py` |
| repository Black | FAIL, one historical `vayujit_api/core/test_database.py` |
| repository `mypy --strict vayujit_api` | FAIL, 234 historical errors in 30 files |

No global suppression or broad typing refactor was introduced. The changed
files are clean; repository-wide diagnostics remain a separate quality
milestone.

## K. Backend and frontend regressions

Executed results:

| Command/suite | Result |
|---|---|
| `pytest tests/test_auth_integration.py -q` | 5 passed |
| operations control center | 40 passed |
| readiness/security/fixture matrix | 96 passed |
| earlier combined matrix including operations control | 95 passed, 1 schema-state failure before DB restoration |
| exact schema dependency rerun after migration restore | 1 passed |
| Angular `npm.cmd run test:web` | 227 passed across 64 files |
| Angular lint | PASS; 2 pre-existing warnings |
| Angular production build | PASS; 14.47 kB advisory initial-bundle budget warning |
| `git diff --check` | PASS |

The one matrix failure was caused by a disposable `vayujit_test` database
whose migration-created supplier-assessment foreign key had been removed by
prior metadata reset. The marker was validated, the disposable database was
recreated, migrations were applied to head, and the exact test then passed.
No golden or production database was touched.

## L. Migration and schema safety

The proxy stack migrated to revision `20261203_0146`. The disposable
regression database was rebuilt through Alembic before the final matrix. The
schema-reset dependency check passed after rebuild. The canonical
single-owner constraint and all existing foreign-key authorities remain
unchanged.

## M. Accessibility and manual interaction

The direct-CDP axe scan had 12 visible states with zero violations and zero
incomplete results. Tab traversal and visible focus passed at browser level;
back/forward, refresh, logout, and protected deep-link behavior passed. A
full WCAG conformance claim is not made: Escape/focus restoration for every
possible overlay and screen-reader semantics still need a dedicated manual
witness.

## N. Security and external-write boundary

No Amazon, Flipkart, supplier, RFQ, payment, procurement, marketplace, or
other external write was attempted. Provider mutation kill switches remain
enabled, the page remains HUMAN-review-only, and no credentials or secrets
are rendered. No golden database was modified.

## O. Launch decision

### A. Locally certified

- production-like API/worker/web/Postgres Compose startup;
- nginx edge routing, TLS termination, health/readiness, Angular deep-link
  serving, secure auth through the proxy;
- 29/29 browser checks, 12-state axe scan, six responsive widths;
- Angular 227/227, focused backend regressions, changed-file static checks;
- private internal services and fail-closed external mutation controls.

### B. Requires external infrastructure

Public DNS/HTTPS certificate, secret manager, durable off-server backups,
external restore witness, monitoring/alerting, and a production host remain
unprovided. The disposable self-signed local stack is not production.

### C. Requires business/provider authorization

Verified business identity, seller accounts, official marketplace OAuth/API
contracts, real read-only imports, and HUMAN authorization for any external
write remain unapproved and untested.

## P. Remaining blockers

1. **High - warning fixture matrix:** independent marker-protected fixtures,
   browser assertions, refresh persistence, HUMAN boundary, and negative
   resolution have not been run for every canonical warning dimension.
2. **Medium - fresh profile:** Chrome failed to expose the second CDP port;
   rerun on a supported host/profile with process logs retained.
3. **Medium - repository quality baseline:** one Ruff error, one Black
   formatting error, and 234 strict-mypy errors in legacy files remain.
4. **External launch approvals:** infrastructure and provider/business gates
   in sections O.B and O.C remain outside local code certification.

## Q. Final classification and stop boundary

**PR-SOS-09 - IMPLEMENTED / LOCAL CERTIFICATION PENDING**  
**VAYUJIT PRODUCTION GO-LIVE - NOT YET CERTIFIED**

PR-SOS-09.3 stops here. No PR-SOS-10 work, deployment, provider call,
supplier contact, procurement, payment, marketplace mutation, commit, or push
was performed.
