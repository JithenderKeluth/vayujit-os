# Live provider readiness matrix

All rows below remain outside local certification. Local fake adapters are deterministic and network-free; live credentials are not configured.

| Provider | Domain | Local fake | Live implementation | Credentials | Sandbox | Encryption | Rate/timeout/retry | Reconciliation/webhook | Status/blocker |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| OpenAI-compatible AI | AI | Yes | Adapter boundary | No | Not configured | Ready | Modeled | N/A | Not validated |
| Image provider | Image | Yes | Adapter boundary | No | Not configured | Ready | Modeled | N/A | Not validated |
| Video provider | Video | Yes | Adapter boundary | No | Not configured | Ready | Modeled | N/A | Not validated |
| YouTube | Social | Yes | No live call | No | No | Ready | Contract | Required before live | Not validated |
| Instagram | Social | Yes | No live call | No | No | Ready | Contract | Required before live | Not validated |
| Facebook | Social | Yes | No live call | No | No | Ready | Contract | Required before live | Not validated |
| Amazon Marketplace | Commerce | Yes | No live mutation | No | No | Ready | Contract | Required before live | Not validated |
| Flipkart | Commerce | Yes | No live mutation | No | No | Ready | Contract | Required before live | Not validated |
| Meesho | Commerce | Not supported | No | No | No | Ready | N/A | N/A | Capability unavailable |
| Meta Ads | Ads | Yes | No live spend | No | No | Ready | Contract | Required before live | Spend disabled |
| Google Ads | Ads | Yes | No live spend | No | No | Ready | Contract | Required before live | Spend disabled |
| Amazon Ads | Ads | Yes | No live spend | No | No | Ready | Contract | Required before live | Spend disabled |
| Flipkart Ads | Ads | Yes | No live spend | No | No | Ready | Contract | Required before live | Spend disabled |

Enablement order recommendation: OpenAI-compatible AI read-only validation, one Social sandbox, one Marketplace sandbox, Ads read-only/sandbox, then one controlled mutation. The sequence minimizes irreversible risk and maximizes reuse of the existing timeout, retry, idempotency, reconciliation, and recovery contracts.