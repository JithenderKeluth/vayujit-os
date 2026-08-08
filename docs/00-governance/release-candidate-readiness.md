# VAYUJIT OS Release-Candidate Readiness

Date: 2026-08-08  
Branch: `feature/KAN-release-candidate-readiness`  
Source milestone: `5434558 feat(KAN): add durable campaign catch-up recovery`

## Release scope

This readiness pass covers the local-owner MVP: authentication, brands, products, AI artifacts,
approvals, publishing destinations, mock/WordPress/Shopify connectors, media, durable workflows,
campaign orchestration, scheduler/workers, Recovery, durable rescheduling, durable one-catch-up,
Operations, backups, maintenance tooling, and the secure Electron shell.

No new connector, Redis, multi-user authorization, cloud deployment, inventory synchronization,
remote deletion, or marketplace functionality is in scope.

## Validated by repository inspection, runtime checks, and static checks

- Recovery registry contains 21 declared actions: 19 implemented and 2 explicitly unsupported,
  with no legacy dispatch path in the router.
- Catch-up persistence, preview/confirmation, exact Artifact/version checks, idempotency, and
  PostgreSQL integration tests are present.
- Rescheduling and catch-up preserve the original Activity identity and use durable schedules/jobs.
- Connector tests use controlled fakes and loopback transports; no real services are contacted.
- Origin protection, server-managed cookies, owner scoping, credential encryption/redaction, and
  safe audit metadata are covered by existing security tests and implementation paths.
- Ruff passes across the repository. Targeted Ruff formatting checks pass for changed backend code.
- `git diff --check` passes.
- Angular template accessibility rules and the existing keyboard file-picker test pass; no
  positive-tabindex or unsafe HTML patterns were found in the reviewed surfaces.

## Runtime validation status

Node 24.19.0/npm 11.17.0, Python 3.12.10, Docker Desktop 29.6.2, and PostgreSQL 17 are
available. The repository-local API virtual environment was recreated against Python 3.12 and
the disposable PostgreSQL test database was recreated with its safety marker.

## Test results

Runtime validation passed: 18 rescheduling tests, 8 catch-up tests plus 1 skip, 20 replacement
tests, 2 connector E2E tests, 5 workflow tests, 7 scheduler integration tests, 2 worker unit
tests, 111 backend unit tests, 87 backend integration tests plus 1 skip, and 1 release-candidate
journey test. Angular passed 62 tests across 18 files; Electron passed 4 unit tests.

## Migration and backup result

The migration chain reached `20260812_0022`; the disposable upgrade/downgrade/re-upgrade cycle
passed. Backup creation and checksum verification passed for backup
`20260807T220205Z-9fcfa55a`.

## Security and dependency result

The repository contains tests and implementation for Origin protection, HttpOnly/SameSite cookies,
Argon2id passwords, hashed session tokens, AES-GCM credential encryption, owner scoping, safe
errors, and redacted audit/log metadata. Production `npm audit` found 0 vulnerabilities. License
visibility returned WARN for unknown internal/runtime package licenses; no GPL/AGPL flags were
reported.

## Electron, accessibility, responsive, and performance result

Electron secure defaults are present, the 4-test unit suite passed, and the official
`npm.cmd run test:desktop:smoke` completed successfully. The smoke output verified
`sandbox=true`, `contextIsolation=true`, `nodeIntegration=false`, app-scheme loading, and a
`Renderer ready` checkpoint. Angular template accessibility lint passed with 0 errors, and the
existing keyboard file-picker test passed. A visual contrast/screen-reader review remains a
release-environment limitation rather than a known blocker.

The repeatable `npm.cmd run performance:baseline` harness uses a deterministic disposable
PostgreSQL database and five samples per operation. Results (median/p95) were: API app startup
2.3ms; Angular dev startup 21,335.9ms; Electron smoke startup 2,516.9ms; health 1.8/43.4ms;
dashboard 27.3/41.7ms; campaign list 10.3/12.6ms; campaign details 13.1/15.2ms; bounded
calendar 16.6/23.7ms; Recovery projection 13.0/15.5ms; execution history 18.6/21.5ms;
reschedule preview 29.2/35.6ms; catch-up preview 23.1/27.0ms; scheduler materialization
3.0/7.8ms; worker claim 3.7/7.9ms. No pathological latency was observed for this local MVP
dataset.

## Observability result

Correlation IDs, structured logging, health/readiness, maintenance, scheduler heartbeat, connector
health, AI-provider health, and backup diagnostics are implemented and covered by targeted tests;
runtime dashboard and log inspection remain **unverified**.

## Journey coverage to execute in a release environment

1. Owner setup/login, brand activation, product activation, AI generation, and artifact approval.
2. Campaign creation, Activity scheduling, worker claim, fake connector publish, and audit/history.
3. Durable Activity rescheduling and replacement-worker execution.
4. Missed Activity preview, explicit one-catch-up confirmation, catch-up worker execution, and
   campaign completion.
5. WordPress and Shopify fake connector journeys, including retries, reconciliation, media,
   taxonomy/collections/publications, and duplicate prevention.
6. Worker crash/lease recovery, maintenance mode, backup/restore, migration upgrade/downgrade, and
   Electron runtime smoke.

## Release blockers

None identified for the local MVP gate. Visual contrast and screen-reader review should still be
repeated in the target release environment.

## Deferred items

- Real external WordPress, Shopify, and AI provider calls remain intentionally out of scope for
  this local readiness pass.
- Off-host encrypted backup rotation and enterprise RPO/RTO guarantees remain outside the local MVP.

## Recommendation

**GO for the local MVP release-candidate gate.** Core runtime, database, migration, backup,
security, backend, frontend, Electron smoke, accessibility lint/keyboard checks, performance
baseline, and E2E checks pass locally. The visual accessibility limitation remains documented for
the target release environment.

## Required release commands

```powershell
npm.cmd install
npm.cmd run api:install
npm.cmd run db:up
npm.cmd run db:migrate
npm.cmd run test:all
npm.cmd run test:campaigns:rescheduling
npm.cmd run test:campaigns:catch-up
npm.cmd run test:release:candidate
npm.cmd run test:campaigns:recovery
npm.cmd run test:campaigns:e2e
npm.cmd run test:campaigns:workflow
npm.cmd run test:scheduler:integration
npm.cmd run test:workers
npm.cmd run test:api:migrations
npm.cmd run test:web
npm.cmd run test:desktop
npm.cmd run test:desktop:smoke
npm.cmd exec --workspace @vayujit/web -- eslint "src/**/*.html"
npm.cmd run performance:baseline
npm.cmd run lint
npm.cmd run build
npm.cmd run format:check
npm.cmd run system:doctor
npm.cmd run security:check
git diff --check
```

```powershell
cd apps\api
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\black.exe --check .
.\.venv\Scripts\mypy.exe vayujit_api
cd ..\..
```
