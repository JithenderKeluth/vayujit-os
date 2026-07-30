# ADR 0030: Durable Campaign Workflow waits

Campaign waits are normalized PostgreSQL records keyed uniquely to a Workflow step. Startup
restoration locks incomplete waits, recalculates Campaign state, and completes each Workflow step at
most once. Correlation and safe failure metadata are persisted; connector payloads are not.
