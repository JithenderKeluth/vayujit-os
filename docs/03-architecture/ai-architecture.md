# AI Content Generation Architecture

The AI module resolves stable provider identifiers behind a backend protocol.
`deterministic_mock_v1` remains offline and deterministic;
`openai_compatible` implements the tested model-list and chat-completions
surface. Product, artifact, approval, and workflow services do not contain
provider transport or credential logic.

Owner configuration and AES-GCM ciphertext persist separately from generation
requests. Each external or fallback invocation creates an attempt. Only strict
validated Product content creates a versioned pending-review artifact. Workflows
consume the final artifact without weakening approval.

The AI module owns prompt templates, generation requests, generated artifacts, provider
selection, structured-output validation, and artifact review state. It references owned brands
and products by identifier; it does not own or duplicate those records.

`AIProvider` is the provider-neutral boundary. The Sprint 1 implementation uses only
`DeterministicMockAIProvider`, which performs no network calls. A normalized input containing
brand, product, template version, and optional instructions produces repeatable structured
content and sanitized metadata.

Generation is synchronous for this MVP slice:

1. Persist a pending request and audit event.
2. Mark it running and call the provider.
3. Validate the response against `ProductContent`.
4. Persist a versioned `GeneratedArtifact` in `pending_review`, or mark the request failed with a
   safe error.
5. Allow the owner to approve, reject with a reason, or regenerate.

Only a new pending-review artifact supersedes an earlier pending-review version. Approved and
rejected versions remain immutable history. This review state is deliberately separate from the
future workflow approval engine and cannot publish content.

Raw template instructions, tracebacks, credentials, and arbitrary provider responses are never
returned to the UI. All access is owner-scoped and uses the existing cookie session and Origin
protection.
