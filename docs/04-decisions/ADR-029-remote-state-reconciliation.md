# ADR-029: Remote publishing reconciliation

Status: Accepted

Successful executions retain the remote post identifier, URL, status, and slug. Reconciliation
compares the current WordPress representation and records in-sync, remote-change, missing, or
failure state. Recovery exposes reconciliation separately from retry.
