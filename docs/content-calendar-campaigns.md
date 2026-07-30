# Content Calendar and Campaign Orchestration

## Architecture

Campaigns are an orchestration aggregate over existing Brands, Products, immutable Artifact
versions, destinations, Publishing schedules, jobs, executions, and Audit events. They do not
replace connector mappings, connector credentials, remote reconciliation, worker claiming, retry
handling, or Artifact approval.

The backend is separated into Campaign metadata/lifecycle, activity/dependency, readiness,
conflict, scheduling/projection, and calendar/progress services. All persisted records are
owner-scoped. API writes continue to use authenticated sessions, exact-Origin middleware,
maintenance-mode middleware, correlation IDs, and append-only Audit events.

## Campaign lifecycle

The central transition map permits:

`draft → planning → ready → scheduled → running → completed → archived`

Pause, partial-completion, failure, and cancellation branches are explicit. Arbitrary status
updates are not accepted. Cancellation requires a reason and preserves schedules, jobs,
executions, and remote entities. Archiving is the terminal historical operation.

## Activities and dependencies

Publishing activities bind one exact approved Artifact version to one compatible WordPress or
Shopify destination and a bounded action. Review and approval checkpoints do not publish.
WordPress and Shopify default to draft creation in the editor.

Dependencies are normalized directed edges supporting finish-to-start, success-required,
completion-required, and manual-release semantics. Edges must remain inside one owner and
Campaign. Duplicate edges, self-edges, and deterministic graph cycles are rejected. Campaigns are
bounded to 500 activities and 1,000 dependency edges by default.

## Readiness and approval

Readiness checks Campaign state, exact Artifact identity/version/approval, owner and Brand/Product
compatibility, destination status and connector compatibility, Campaign time window,
dependencies, enabled state, maintenance mode, and quotas. Results use typed states and safe
resolution guidance.

Remote Publishing always requires the exact selected Artifact to remain approved. A superseded,
rejected, revoked, missing, or version-mismatched Artifact blocks scheduling or execution. The
system never silently selects a newer version.

## Conflict detection

The bounded conflict analyzer detects duplicate destination actions, overlapping Product activity,
outside-window activity, dependency timing inversions, and destination rate-pressure warnings.
It never moves activity times automatically. Security, ownership, approval, connector
compatibility, and dependency-cycle violations are not overridable.

## Scheduling and idempotency

Campaign scheduling calls the existing `PublishingSchedule` service. Each activity has a stable
Campaign identity and a normalized activity-to-schedule link. Repeated scheduling returns the
existing link. Bulk scheduling is limited to 100 activities and defaults to `require_all_ready`;
`schedule_ready_only` preserves an explicit result for every blocked activity.

One-time schedules retain the exact Artifact and destination snapshots. Existing PostgreSQL
workers materialize jobs, claim with `SKIP LOCKED`, renew leases, retry with bounded backoff,
reconcile uncertain results, and prevent duplicate connector publication.

## Time and calendar

Campaign and activity input uses local date/time plus an IANA timezone. Execution instants are
stored in UTC using the scheduler's DST-aware conversion. Nonexistent local times are rejected;
ambiguous folds require explicit scheduler semantics.

Global and Campaign calendar APIs return projections, not raw records, and reject non-positive or
greater-than-90-day ranges. The Angular Content Calendar provides month, week, and agenda modes,
connector filtering, keyboard-focusable events, conflict indicators, and safe Campaign links.

## Pause, resume, cancellation, and recovery

Pause prevents new scheduling, pauses future schedules, and pauses unclaimed jobs. It does not
claim to pause an already-running remote request. Resume requires one of `skip_missed`, `run_next`,
`one_catch_up`, or `reschedule_manually`; missed activities are never all published implicitly.

Cancellation blocks future work, pauses future schedules/jobs, requests cancellation for locally
running activity projections, and retains completed history. It never deletes WordPress posts or
Shopify Products. Late remote success remains subject to existing reconciliation.

Campaign activity state is projected from scheduler jobs rather than copied blindly. Jobs and
Publishing executions remain directly navigable. Campaign health reports active, upcoming,
blocked, and overdue counts without credentials or raw connector failures.

## UI and accessibility

Authenticated routes cover Campaign list, creation, detail/progress/readiness/conflicts, activity
creation, and the unified calendar. Controls have labels, error regions, keyboard-accessible
events, non-color status text, responsive layouts, and reduced-motion behavior.

Electron uses the same Angular routes. The renderer retains sandboxing, context isolation,
disabled Node integration, denied permissions, navigation restrictions, and external HTTPS
opening in the main process. No connector call or credential handling occurs in the renderer.

## CLI and operations

Read-only commands:

```powershell
npm.cmd run campaigns:list
npm.cmd run campaigns:status
npm.cmd run campaigns:activities
npm.cmd run campaigns:readiness
npm.cmd run campaigns:conflicts
npm.cmd run campaigns:upcoming
```

Campaign validation requires both an explicit Campaign ID and `--confirm` when invoking the Python
CLI directly. `system:doctor` includes Campaign migration and aggregate diagnostics alongside
scheduler, worker, WordPress, and Shopify readiness.

## Testing and incident response

Use only the guarded PostgreSQL database. The migration test performs clean upgrade, downgrade to
0017, and re-upgrade to 0018. Unit tests cover bounded actions, lifecycle transitions, cycle
detection, duplicates, and time-window conflicts. Integration tests exercise persisted lifecycle,
dependencies, readiness, scheduling checkpoints, progress, calendar projections, and data counts.

For an incident: enable maintenance mode, inspect Campaign health and activity state, open the
linked job/execution, reconcile uncertain connector outcomes, replace revoked content through a
new explicitly approved activity, and resume with an explicit missed-activity policy. Never force
success, mutate arbitrary job state, expose credentials, or delete remote content.

## Known limitations

Campaign templates and drag-and-drop rescheduling are intentionally deferred. The current editor
uses explicit identifiers for Product, Artifact, and destination selection; richer searchable
pickers can be layered on the same safe APIs. Workflow Campaign actions and Campaign-specific
Recovery Center action cards require a subsequent hardening slice; existing durable
schedule/publishing Recovery remains available through linked jobs and executions.
