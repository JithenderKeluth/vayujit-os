# Engineering Incident: Development Database Reset

**Date:** 2026-07-28  
**Status:** Recovered schema; prior records unrecoverable without an independent backup

During Workflow validation, `VAYUJIT_TEST_DATABASE_URL` was mistakenly set to the normal local
development database. Integration fixtures accepted any PostgreSQL URL and independently ran
SQLAlchemy `drop_all`, clearing domain tables. The Alembic revision table remained, which initially
made the damaged database appear migrated.

The schema was rebuilt to migration head. Previous development records were not recoverable
because no independent backup was available.

The root cause was insufficient technical separation: tests silently skipped without a test URL,
database names and environment were not validated, no ownership marker existed, and destructive
logic was duplicated across test modules.

Safeguards introduced:

- distinct unit, integration, Workflow, and migration commands;
- exact test environment and explicit test URL requirements;
- strict disposable-name and deny-list checks;
- durable project marker and connected-database verification;
- centralized guarded schema reset;
- isolated, marker-checked migration database lifecycle;
- password-redaction and rejection tests;
- documentation that automated tests never reset development data.

