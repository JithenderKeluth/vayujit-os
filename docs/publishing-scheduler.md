# Scheduled publishing and worker operations

Scheduled publishing is durable in PostgreSQL and runs outside the API process.

## Local startup

1. Start PostgreSQL: `npm.cmd run db:up`
2. Apply migrations: `npm.cmd run db:migrate`
3. Start API and web normally: `npm.cmd run dev`
4. In another terminal start the worker: `npm.cmd run dev:worker`

Use `npm.cmd run publishing:worker:once` for one poll cycle,
`npm.cmd run publishing:schedules:materialize` to generate jobs up to the configured horizon,
and `npm.cmd run publishing:jobs:recover` to recover expired leases.

The worker stops claiming work while the existing maintenance marker is present. Ctrl+C switches
it to draining: already claimed tasks finish, a final heartbeat is written, then the process exits.
The API exposes schedules under `/api/v1/publishing/schedules`, jobs under
`/api/v1/publishing/jobs`, workers under `/api/v1/publishing/workers`, and a scheduler summary
under `/api/v1/publishing/scheduler/summary`.

## Delivery and recovery

Delivery is at least once. Schedule occurrence keys prevent duplicate job rows, and job-derived
connector idempotency keys prevent repeated remote creation. Claims are short transactions using
row locks with `SKIP LOCKED`; connector calls occur after the claim commit. Running workers renew
leases. Expired leases are recorded as `lease_lost`, then retry with capped exponential backoff or
move to `dead_letter` after the attempt limit.

Worker configuration uses `VAYUJIT_PUBLISHING_*` variables documented in `.env.example`.
Connector secrets remain in the existing encrypted connector configuration and are never copied
into jobs, attempts, logs, or heartbeats.

## Lifecycle and missed occurrences

Schedules are active, paused, disabled, or archived. Recurrence is limited to daily, selected
weekdays/weekly, and monthly rules with a maximum of 1,000 occurrences. Future occurrences retain
the selected local wall time and IANA timezone. DST gaps are rejected and overlaps use the explicit
fold value. Monthly dates clamp to the target month's final day.

Resume always requires one policy: `skip_missed` advances without publishing missed work,
`next_occurrence` advances to the next future occurrence, and `one_catch_up` creates exactly one
immediately eligible catch-up job before advancing. Running jobs are unaffected.

Jobs progress through scheduled/pending, claimed, running, retry-wait, and a terminal state.
Attempts preserve worker, timing, bounded delay, safe error, connector execution, and correlation
references. No API supports force-success or arbitrary state mutation.

## Crash recovery and Workflow waits

Recovery locks expired jobs, checks the owning worker heartbeat, then locates the existing
Publishing execution through the stable `job:<uuid>` idempotency key. A succeeded connector
execution marks the job successful without another remote call. A running connector execution is
ambiguous and requires operator reconciliation. A retryable non-success schedules bounded backoff;
attempt exhaustion becomes dead letter. Each decision has a durable recovery record and safe audit
event.

Workflow schedule steps persist an exact approved Artifact version, schedule, job reference, and
correlation ID. The persisted wait completes only after the job reaches its expected terminal
state, so API and worker restarts do not lose the relationship.

## Recovery, Health, and UI

Campaign Activity rescheduling is a Recovery action backed by the same PostgreSQL scheduler. A
preview is read-only; confirmation archives the superseded schedule and cancels its pending job,
then materializes a replacement occurrence with stable idempotency. Schedule and job detail pages
mark superseded records while retaining attempts/history and links from the Campaign Activity.

Catch-up Activities use the same occurrence identity and materialization path. Recovery creates no
Publishing execution and makes no connector call; the worker later claims the single durable job.

Recovery Center projects retry-wait, failed, dead-letter, cancellation, expired-lease, and
ambiguous jobs with state-aware actions. Operations Health exposes bounded counts and safe worker
summaries. It never returns credentials, database URLs, host environment, local paths, Artifact
bodies, or connector payloads.

Angular routes cover schedule creation and preview, schedule details, job filters and attempt
timeline, workers, Recovery, and Health. Electron loads the same routes with context isolation,
sandboxing, no Node integration, no preload bridge, denied permissions, and external HTTPS links
opened through the main process.

## Tests and incident response

`npm.cmd run test:scheduler:integration` uses only the guarded PostgreSQL test database. It proves
competing claims, ordering, excluded states, crash-after-remote-success recovery, connector
idempotency, fake WordPress scheduled Workflow publishing, fake Shopify scheduled publishing, and
durable Workflow wait resumption. No production connector is contacted.

For an incident: enable maintenance mode, inspect `publishing:jobs`,
`publishing:jobs:dead-letter`, and `publishing:workers`, reconcile ambiguous remote state, then run
`publishing:jobs:recover` only with its explicit confirmation. Never force success or delete the
remote object. Preserve correlation IDs and recovery records for audit.
