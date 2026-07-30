# ADR 0020: Missed-occurrence policies

Status: Accepted

Resuming a recurring schedule requires `skip_missed`, `next_occurrence`, or `one_catch_up`.
VAYUJIT OS never publishes every missed occurrence automatically. One catch-up creates at most one
immediate job and all policies preserve future wall-clock recurrence.
