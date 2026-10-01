# Live data and provider audit

| Capability | Current state | Credential/configuration | Evidence |
|---|---|---|---|
| Brave search | Live-capable; validated search | Brave key and switches required | 3 LIVE_READ_ONLY searches executed; canonical results persisted. |
| ApprovedWebFetcher | Live-capable, fail-closed | LIVE_READ_ONLY, web-fetch switch, approved source policy | 1C.7 stopped before HTTP with source-approval error. |
| Product identity | Not live validated | Depends on successful fetch/classification | No candidate/ProductOpportunity in observed run. |
| Website intelligence | Local/fixture plus live boundary | Approved HTTPS domains and fetch controls | Architecture exists; real evidence blocked in run. |
| Supplier marketplaces | Mostly local fixture/provider-neutral | Provider credentials and live mode per source | Live readiness pending. |
| AI providers | Deterministic fallback by default | Provider credentials/mode | Do not treat generated output as observed fact. |
| FX/freight/duties/commerce/social/ads | Provider-gated | External credentials and operational infrastructure | Not production/live certified. |

Configuration exists in `core/config.py`; configured is not the same as reachable or live validated.
