# ADR-024: AI usage and estimated cost

## Status

Accepted

## Decision

Provider-returned token usage is stored per attempt and aggregated per request.
Costs are calculated only from operator-maintained effective pricing rows and
are always labelled estimated. No public prices are embedded or scraped.
