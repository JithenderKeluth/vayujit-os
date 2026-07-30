# ADR-012: Persist Workflow Orchestration State

**Status:** Accepted

## Decision

Persist templates, workflow instances, and immutable step attempts in PostgreSQL. The initial
engine accepts only the versioned `product-content-publish` system template and its three known
step types. Orchestration calls the existing AI and Publishing application services.

## Consequences

State survives web, API, and Electron restarts; history and retries remain inspectable. Database
row locks serialize state-changing commands. This is deliberately not a general workflow designer,
worker queue, scheduler, or arbitrary-code engine.

