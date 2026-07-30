# ADR 0017: Scheduling time semantics

Status: Accepted

The schedule stores the user's naive wall time, IANA timezone name, resolved UTC instant, and
recurrence rule. UTC drives queue ordering. Wall time plus timezone drives future recurrence so
daylight-saving changes do not shift the user's intended local hour.

Nonexistent DST times are rejected at creation. Ambiguous times accept an explicit `fold` value
(zero for the earlier instant, one for the later instant). Monthly dates beyond the target month
are clamped to that month's final day. Artifact approval and destination configuration are
snapshotted when the schedule is created, while actual publishing still uses the existing
Publishing domain service.
