# ADR-003: Exclude Redis from the Initial MVP

**Status:** Accepted

## Context
The vertical slice needs durable execution and recovery but not distributed workers, high-throughput queues, or shared cache.

## Decision
Do not use Redis. Persist workflow state in PostgreSQL and execute the constrained workflow within the FastAPI process.

## Alternatives Considered
Redis-backed queue from day one; embedded queue; PostgreSQL job table. The last may be added only when background execution requires it.

## Consequences
Local setup and failure modes are simpler. Long-running work and horizontal scaling remain deliberately limited.

## Risks
API-process execution may complicate shutdown or future scheduling.

## Follow-up Actions
Measure task duration; define graceful shutdown/recovery; write a new ADR before adding any queue or Redis dependency.
