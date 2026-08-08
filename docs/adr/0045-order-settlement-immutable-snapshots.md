# ADR 0045: Orders and settlements are immutable snapshots

Status: Accepted

Imported order and settlement records preserve the remote reference, normalized
status, buyer-safe data, money totals, and period values needed for audit and
profitability. Corrections arrive as new snapshots or explicit adjustments.

