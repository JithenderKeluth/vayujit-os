# ADR-002: PostgreSQL Local Data Store

**Status:** Accepted

## Context
The system needs transactional workflow state, relational integrity, migrations, and a path beyond a prototype.

## Decision
Use local PostgreSQL as the source of truth, accessed only by FastAPI through SQLAlchemy with Alembic migrations.

## Alternatives Considered
SQLite (simpler installation but different concurrency/operational behavior); embedded document store (weaker relational model); cloud database (violates local-first MVP).

## Consequences
Production-grade transactions and consistent tooling, with greater Windows setup, backup, and lifecycle complexity.

## Risks
Installation friction, port/service conflicts, credential handling, and upgrade failures.

## Follow-up Actions
Prototype clean-machine setup; define supported version, least-privilege database role, migration policy, health check, backup, and restore.
