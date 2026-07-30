# ADR-013: Explicit Approval Pause and Continuation

**Status:** Accepted

## Decision

Generation commits the Artifact and a durable `waiting_for_approval` workflow state. Artifact
approval/rejection remains owned by the AI Artifact service. A separate Workflow continuation
command re-reads that authoritative decision before advancing.

Approved Artifacts publish once using a stable workflow-derived idempotency key. Pending Artifacts
cannot advance. Rejected Artifacts produce the terminal, non-retryable `artifact_rejected`
failure. Cancellation is allowed only before a step is running and never after completion.

## Consequences

Refresh and application restart cannot bypass or lose the human gate. Approval history remains in
its source domain, while orchestration stores only related identifiers and step outcomes.

