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
