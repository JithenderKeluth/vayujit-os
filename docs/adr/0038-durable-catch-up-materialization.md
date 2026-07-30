# ADR 0038: Durable catch-up materialization

One-catch-up creates one replacement Activity, an append-only resolution, and an existing durable
scheduler occurrence. Unique missed-resolution and Activity identities make repeated requests
idempotent while preserving the original Activity history.
