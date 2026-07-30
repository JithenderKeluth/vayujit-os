# ADR-006: Mock Connectors Before Production APIs

**Status:** Accepted

## Context
Production marketplace and publishing APIs introduce access, OAuth, rate-limit, review, and availability risks before the core workflow is proven.

## Decision
Define capability-scoped connector interfaces and first implement deterministic mock marketplace and publishing connectors. Postpone production APIs until the vertical slice passes.

## Alternatives Considered
Build one production integration immediately; omit connectors; simulate publishing only in UI.

## Consequences
Workflow, approval, idempotency, and history can be tested offline. The mocks do not prove production authorization or API compatibility.

## Risks
Mocks may be unrealistically permissive or diverge from future API constraints.

## Follow-up Actions
Model latency/failure/unknown-outcome scenarios; add connector contract tests; select and threat-model the first production platform after MVP exit.
