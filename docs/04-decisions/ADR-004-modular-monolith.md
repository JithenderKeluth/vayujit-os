# ADR-004: Modular Monolith

**Status:** Accepted

## Context
One developer must deliver multiple business capabilities without distributed-system overhead while preserving clear boundaries.

## Decision
Build one FastAPI deployable divided into Identity, Brands, Products, AI, Workflows, Approvals, Publishing, Audit, and Settings modules. Modules communicate through public application interfaces and identifiers.

## Alternatives Considered
Layered monolith without domain boundaries (simpler initially but high coupling); microservices (operationally excessive); plugin-first architecture (premature).

## Consequences
Deployment and transactions remain simple while boundaries support testing and later extraction. Boundary discipline must be enforced in code and review.

## Risks
Shared-database shortcuts and cyclic imports can erode modularity.

## Follow-up Actions
Define package rules, architecture tests, module APIs, migration ownership, and cross-module orchestration conventions.
