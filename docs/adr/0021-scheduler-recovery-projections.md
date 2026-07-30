# ADR 0021: Scheduler Recovery projections

Status: Accepted

Recovery Center derives scheduler rows from durable job, schedule, execution, lease, and recovery
state. Capabilities are calculated from state; there is no force-success, arbitrary transition,
remote deletion, or silent Artifact replacement action.
