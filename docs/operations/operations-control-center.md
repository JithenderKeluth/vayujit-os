# Operations Control Center

The Operations Control Center is the owner-scoped operational surface at
`/operations`. It composes the existing System Doctor, publishing scheduler,
durable jobs, Recovery, provider registry, backups, audit, and staging
configuration services. The API is authoritative; the Angular page is a
projection and never contains provider credentials or private filesystem
paths.

## Local run

Start PostgreSQL with `npm.cmd run db:up`, apply migrations with
`npm.cmd run db:migrate`, then start the API and web workspaces with
`npm.cmd run dev:api` and `npm.cmd run dev:web`. Open
`http://127.0.0.1:4200/operations` after signing in as the local owner.

The desktop development shell is started with `npm.cmd run dev:desktop` after
the web and API are available.

## API surface

All routes require the existing authenticated owner session and the existing
allowed Origin. Read projections are available under `/api/v1/operations`:

- `overview`, `health`, `workers`, `scheduler`, `jobs`, `providers`
- `configuration`, `security`, `storage`, `alerts`, `release-readiness`
- `backups/overview`, `backups`, `restore/readiness`, `cleanup/preview`, `audit`, `history`, `trace/{correlation_id}`, and `metrics`
- `system-doctor`, `drain`, `recovery`, `recovery/history`, `mutation-control`, `emergency-stop`, `ads/safety`, `migrations`, `security/events`, `staging-readiness`, and `production-readiness`

Guarded actions are explicit and idempotency-aware where applicable:

- scheduler due-work materialization requires `confirm: true`;
- job retry/cancel/inspect/review requires confirmation and owner scope;
- backup creation uses the existing backup service and writes an audit event;
- worker pause/resume, provider switching, and emergency stop remain
  deployment-controlled and return a safe conflict response.

No endpoint enables Shopify, Amazon, Social, marketplace, or Ads live
mutations. Shopify sandbox certification remains deferred and no external
credentials are required for this surface.

## Safety and release interpretation

Environment and provider modes are shown in the overview banner. Secrets,
tokens, DSNs, database URLs, private paths, and raw provider payloads are
redacted. Error responses use stable human-readable messages. The release
readiness projection is conditional for local development until deployment
configuration, monitoring, signing, and live-provider sign-off are complete;
that does not enable any live mutation.

## Hardening and local certification evidence

The focused hardening suite is apps/api/tests/test_operations_hardening.py. It
covers:

- sequential idempotency for cleanup, alert acknowledgement, and bounded
  scheduler execution;
- PostgreSQL transaction-scoped concurrent alert acknowledgement, proving one
  logical audit event and one reused response;
- a disposable PostgreSQL storage ledger before/after assertion; and
- three-sample median/p95 timing for the 18 safe read projections plus safe
  confirmation/action validation.

The control-center action handlers use transaction-scoped PostgreSQL advisory
locks keyed by owner and idempotency key. Repeated requests return a safe
reused result and the original audit identifier. Inspect/review Job actions
are read-only and do not create mutation audit events. Cleanup is intentionally
a no-action operation: approved media and current lineage are never removed.

The storage projection reports a bounded process-local baseline with current,
previous, delta, and observed_at for media/file counts, bytes, temporary files,
and checkpoint files. It retains at most 1,024 owner baselines; it is
diagnostic evidence, not a durable time-series. A process restart resets the
previous sample, which is an explicit operational limitation.

Worker coverage is truthful: publishing has full heartbeat/job detail; AI
content/image, AI video, bulk video, social, marketplace, campaign, Ads, and
marketing-plan domains are summary-only through shared durable-job/recovery
projections. No fake per-domain worker state is emitted.

The measured local run (three samples per read) classified every endpoint PASS
under the 10,000 ms p95 threshold. The overview cold-start outlier was
1,700.92 ms; subsequent overview samples were below 100 ms. Read medians/p95s
included health 39.86/56.18 ms, jobs 38.57/46.04 ms, storage 37.71/38.63 ms,
recovery 117.43/142.51 ms, and alert acknowledgement validation 121.30 ms.
No live provider, Shopify, marketplace, or Ads request was made.

## Certification boundary

Local owner authentication, owner scoping, safe projections, scheduler
bounded-run controls, job state projections, Recovery projections, provider
registry, emergency-stop contract, Ads-spend safety, backup/cleanup safety,
storage ledger/integrity checks, audit/correlation views, configuration,
System Doctor, security/privacy responses, Angular tests, Electron smoke,
migrations, lint/format/build, and dependency audits remain locally
certifiable.

AXE and automated viewport testing are not configured in this repository;
accessibility and responsive behavior are covered by static/component tests and
source review at 390 px, 768 px, and 1280 px+. The aggregate API integration
suite is environment-timeout-bound and should be reported as
TIMEOUT DUE TO TOTAL RUNTIME; bounded constituent suites are the authority.
Shopify sandbox, live providers, monitoring vendor, signing, external secrets,
and production deployment remain deferred/no-go. Real Ads spend remains
disabled.

Final closure evidence

The final local hardening run exercises concurrent manual-backup request
deduplication and confirms that the Operations Recovery endpoint delegates to
the authoritative domain Recovery API without emitting a duplicate Operations
audit event. The existing alert acknowledgement concurrency case remains
PostgreSQL advisory-lock protected.

Operations mutation inventory:

- MUTATING: backup trigger, alert acknowledgement, bounded scheduler run,
  Job retry, Job cancel, cleanup confirmation.
- DELEGATED_TO_DOMAIN: Recovery actions.
- DEPLOYMENT_CONTROLLED: worker pause/resume, provider switch, emergency
  stop, mutation-control, drain, and migration requests.
- READ_ONLY: all GET projections, Job inspect/review, and audit/history/trace
  views.

Read-only, deployment-controlled, and delegated requests do not create false
Operations mutation audits. Mutation requests carry an owner-scoped
idempotency key and one audit event; concurrent backup and alert requests
return one original result plus one safe reuse result. AXE and viewport
automation remain unconfigured; aggregate API integration remains
TIMEOUT DUE TO TOTAL RUNTIME.
Concurrent Job retry and cancel requests are covered with PostgreSQL-backed
failed/retry-wait jobs. Each pair produces one state transition and one
audit identifier; cancelled jobs remain unclaimable by a later worker.
