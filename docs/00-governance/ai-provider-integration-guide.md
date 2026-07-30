# AI provider integration guide

VAYUJIT OS registers the deterministic mock and one `openai_compatible`
implementation. Angular never contacts a provider. Configure the real provider
at `/settings/ai/providers/openai-compatible`, validate it, then select the
provider and model explicitly during generation.

Database credentials take precedence over `VAYUJIT_OPENAI_API_KEY`; otherwise
the provider is unconfigured. Model discovery is cached for 15 minutes.
Development permits loopback HTTP for the deterministic fake server. Outside
development, URLs require HTTPS and resolved private, loopback, link-local,
reserved, multicast, and unspecified addresses are rejected. Redirects are
disabled and responses are bounded.

Fallback to `deterministic_mock_v1` is opt-in and limited to retryable provider
unavailability. It never masks credentials, authorization, model, policy, or
configuration failures. Real-provider compatibility is claimed only for the
request surface tested by VAYUJIT OS.
