# ADR-005: Provider-Neutral AI Interface

**Status:** Accepted

## Context
Business workflows must not depend on one AI vendor and must be testable offline and deterministically.

## Decision
Expose a typed generation interface with provider configuration, normalized request, structured response, usage metadata, and error categories. Implement a deterministic mock first and an Ollama-compatible local adapter second.

## Alternatives Considered
Direct Ollama calls in workflow code; cloud-provider SDK as the abstraction; adopting a broad orchestration framework immediately.

## Consequences
Tests are repeatable and providers replaceable, at the cost of maintaining a deliberately small common contract.

## Risks
Lowest-common-denominator design, provider-specific leakage, and invalid model output.

## Follow-up Actions
Version request/output schemas; define timeout/error mapping; add contract tests; evaluate orchestration libraries only after the slice works.
