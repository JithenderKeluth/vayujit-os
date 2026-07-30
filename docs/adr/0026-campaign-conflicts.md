# ADR 0026: Campaign conflict detection

Conflict analysis is bounded and deterministic. It reports duplicate, overlap, ordering, window,
and pressure conditions but never moves activities. Approval, ownership, capability, and cycle
failures cannot be overridden.
