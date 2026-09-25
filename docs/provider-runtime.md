# Provider Runtime Foundation (14A)

VAYUJIT provider integrations use a provider-neutral registry and a shared
bounded runtime. The runtime is the authority for credential resolution,
redaction, timeouts, retry and `Retry-After`, rate limiting, request budgets,
correlation IDs, response validation, safe execution records, and provider
metrics. Adapters only construct requests, validate/normalize responses, and
map provider-specific details.

## Environments and safety

`LOCAL_FIXTURE` is deterministic and never contacts the network. It is not a
claim that a provider is connected or live-capable. The 14A runtime rejects
write capabilities and does not expose generic HTTP tools to the Business
Agent. Live provider calls remain explicit future-phase work.

Credentials are represented by `CredentialReference` objects. The current
resolver reads only named deployment environment variables; secrets are never
stored in provider metadata, returned by the API, or included in execution
records. Configuration values containing secret-shaped keys are rejected.

'## Persistence and existing runtimes

14A adds no provider tables or migrations: registry definitions are static and
execution records/counters are bounded operational memory. Durable domain
execution remains owned by existing Marketplace Runtime and provider-specific
workflows; 14A does not replace or alter those authorities.

'## Local validation

The deterministic fixture exercises successful and paginated reads, throttling,
`Retry-After`, transient 5xx retry, timeout, permanent authentication failure,
malformed responses, bounded pages/items, correlation, and redaction:

```powershell
$env:VAYUJIT_ENV = "test"
apps/api/.venv/Scripts/python.exe -m pytest -q apps/api/tests/test_provider_runtime.py
```

The authenticated registry is exposed at `/api/v1/providers`. The only
validation endpoint in 14A is `/api/v1/providers/local_fixture/validate`; it
uses the no-network fixture and reports `LOCAL_FIXTURE` explicitly.

## Adding a provider

1. Register stable provider metadata and explicit capabilities.
2. Declare non-secret configuration and credential requirements.
3. Implement a thin adapter using the provider-neutral contract.
4. Add deterministic fixture and provider contract tests.
5. Add explicit connection validation only when a provider-specific live read
   contract and credentials are available.

Do not rebuild retries, rate limiting, redaction, credential handling,
correlation, Operations, or System Doctor in an adapter. IndiaMART, Alibaba,
TradeIndia, and Global Sources remain LOCAL_FIXTURE-only in this phase; their
live authentication and endpoint contracts are deferred to 14B-14E.

