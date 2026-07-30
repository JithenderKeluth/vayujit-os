# ADR-015: Use Typed Owner Preferences

**Status:** Accepted

Durable owner preferences use one constrained PostgreSQL row per owner with explicit columns,
foreign keys, enums/check constraints, and bounded page sizes. A generic key-value settings table
is rejected because it weakens validation, migration review, and safe UI behavior.

