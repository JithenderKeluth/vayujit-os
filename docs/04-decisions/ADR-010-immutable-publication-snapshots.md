# ADR-010: Immutable Publication Snapshots

**Status:** Accepted

Publishing executions persist schema-versioned content and request snapshots before dispatch.
Attempts and retries reuse those snapshots rather than mutable Product, Artifact, or Destination
data. This provides historical accuracy and prevents silent content changes during retry. Future
snapshot versions require additive readers or an explicit offline migration; stored snapshots are
never rewritten during ordinary execution.
