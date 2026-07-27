# ADR-009: Synchronous AI Generation for the Initial Slice

**Status:** Accepted

## Context

Sprint 1 needs a complete, restart-durable generation and review slice without introducing
Redis, workers, remote providers, or workflow orchestration.

## Decision

Run the deterministic local provider inside the API request while persisting explicit pending,
running, completed, and failed states. Validate structured output before creating an artifact.

## Consequences

The slice is simple to run, deterministic, and observable in PostgreSQL. A future slow provider
must move execution behind a durable worker without changing the provider or artifact contracts.
The current implementation is not suitable for long-running or concurrent production inference.
