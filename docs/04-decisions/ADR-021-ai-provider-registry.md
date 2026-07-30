# ADR-021: AI provider abstraction

## Status

Accepted

## Decision

Generation resolves stable provider identifiers through a backend abstraction.
The deterministic mock remains the offline default; `openai_compatible` is the
only remote implementation in this slice.
