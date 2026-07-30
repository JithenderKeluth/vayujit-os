# AI operations and incident response

Use `npm.cmd run ai:provider:status` for a secret-free configuration summary,
`ai:provider:validate` for an explicit live low-cost model-list check, and
`ai:usage:summary` for persisted usage. The standard doctor never prints a key.
Ordinary automated tests use the mock or local fake server.

For provider incidents, record correlation ID, provider, model, safe error code,
attempt count, latency, and validation state. Disable the provider for suspected
credential compromise, rotate externally, remove the stored key, install the
replacement, and validate. Enable mock fallback only when deterministic content
is operationally acceptable. Liveness never depends on AI. Provider failure is
degraded with fallback; deployments may require real AI through
`VAYUJIT_AI_REAL_PROVIDER_REQUIRED`.

Token counts are recorded only when returned. Cost remains unavailable unless
an operator-maintained pricing row matches; estimates are not billing records.
Cancellation is local intent only and does not claim remote cancellation.
