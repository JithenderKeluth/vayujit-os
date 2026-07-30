# ADR-030: Non-destructive WordPress recovery

Status: Accepted

VAYUJIT OS may move a remote WordPress post to draft but does not delete it. Cancellation is local
and cannot guarantee remote cancellation once an HTTP request has been sent. Late responses are
discarded locally and flagged for reconciliation.
