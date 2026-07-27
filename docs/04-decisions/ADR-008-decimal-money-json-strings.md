# ADR-008: Decimal Money as JSON Strings

**Status:** Accepted  
**Date:** 2026-07-27

## Context

JavaScript numbers and binary floating point cannot exactly represent many decimal commerce
values. Product prices must round-trip between Angular, FastAPI, and PostgreSQL without silently
changing value.

## Decision

Money crosses HTTP JSON boundaries as base-10 strings such as `"19.99"`. FastAPI parses validated
strings into Python `Decimal`, and PostgreSQL stores values as `NUMERIC(12,2)`. The application
rejects more than two fractional digits instead of rounding. Currency is an uppercase
three-letter code. Weight uses the same string approach with `NUMERIC(12,3)`.

The frontend treats money as strings for editing and display and performs no authoritative
floating-point calculations.

## Consequences

- Decimal values round-trip exactly.
- API clients must not send JSON numbers for money.
- Arithmetic introduced later must use decimal libraries or the backend.
- Currency conversion and locale-dependent parsing are outside this decision.
