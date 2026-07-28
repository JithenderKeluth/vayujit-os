# Workflow State Model

## States and Transitions

| From | Allowed next state | Cause |
|---|---|---|
| `pending` | `running`, `cancelled` | start or owner cancellation |
| `running` | `waiting_for_approval`, `failed`, `cancelled` | valid generation, error, or cancellation |
| `waiting_for_approval` | `approved`, `rejected`, `cancelled` | owner decision/cancellation |
| `approved` | `publishing`, `failed` | publish dispatch or pre-dispatch failure |
| `publishing` | `completed`, `failed` | stored connector outcome |
| `failed` | `running`, `publishing`, `cancelled` | safe retry or cancellation |
| `rejected`, `completed`, `cancelled` | none | terminal |

`approved` is durable evidence of the decision, not a terminal state. Every transition is validated and committed with an audit event. A step attempt is immutable; retry creates a new attempt.

## Retry, Idempotency, and Recovery

- Validation and authorization failures require changed input and are not automatically retried.
- Retryable generation failures resume at generation without recreating completed steps.
- Publishing uses a stable unique idempotency key. A known failure before dispatch may retry; a known adapter response is reused.
- If a crash occurs during publishing and the outcome is unknown, recovery sets the execution to `failed` with an uncertain-outcome code and requires owner review.
- At startup, the recovery service scans nonterminal executions. Interrupted pure steps become safely retryable; durable approval decisions are preserved.
- Cancellation is rejected after publishing dispatch begins.

See [workflow-state.mmd](diagrams/workflow-state.mmd).

Until the general workflow engine exists, publishing uses the same persisted
`pending -> running -> succeeded|failed` discipline in a standalone execution. Retry locks one
failed retryable execution and appends an attempt using its original snapshot.

The UI communicates `succeeded`, retryable `failed`, and permanent `failed` distinctly. Repeated
submission is disabled in-flight and uses the same key; retry is confirmed and disabled in-flight
or after success.

## Implemented Product Content Publish Workflow

The MVP now persists `draft -> running -> waiting_for_approval -> running -> completed`, with
`failed` and `cancelled` branches. Its fixed versioned template contains generation, approval
wait, and publishing steps. Each retry appends a step attempt. Artifact decisions and Publishing
executions remain authoritative in their owning modules; the Workflow stores related IDs only.
See ADR-012 and ADR-013.
