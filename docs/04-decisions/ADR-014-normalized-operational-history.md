# ADR-014: Normalize Operational History from Safe Audit Events

**Status:** Accepted

Operational History is a read model over owner-scoped append-only audit events. The API maps
allow-listed fields into category, event, safe summary, status, and stored related identifiers.
It never returns unrestricted audit metadata, prompts, content snapshots, connector payloads, or
exceptions. This avoids unbounded frontend fan-out while leaving domain records authoritative.

