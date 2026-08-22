# Production configuration

Configuration is loaded through `vayujit_api.core.config.Settings` with the `VAYUJIT_` prefix. Modes are `local`, `test`, `development`, `staging`, and `production`.

## Inventory

| Class | Variables | Classification |
|---|---|---|
| Runtime | `VAYUJIT_ENVIRONMENT`, `VAYUJIT_DEBUG`, `VAYUJIT_LOG_LEVEL`, build metadata | PUBLIC_CONFIG / LOCAL_ONLY |
| Database | `VAYUJIT_DATABASE_URL`, pool and statement-timeout settings | REQUIRED_PRODUCTION; DSN SECRET |
| Sessions | `VAYUJIT_SESSION_SECRET`, cookie name/lifetime/SameSite/Secure | REQUIRED_PRODUCTION; SECRET |
| Encryption | `VAYUJIT_CREDENTIAL_ENCRYPTION_KEY`, key ID, previous keys | REQUIRED_PRODUCTION; SECRET |
| Storage | `VAYUJIT_STORAGE_PROVIDER`, bucket, media path and limits | REQUIRED_PRODUCTION |
| Origins | `VAYUJIT_ALLOWED_ORIGINS`, web origin, HTTPS and proxy settings | REQUIRED_PRODUCTION / PUBLIC_CONFIG |
| Providers | OpenAI, WordPress, Shopify, connector credentials | OPTIONAL_PRODUCTION unless enabled; SECRET |
| Workers | publishing worker, leases, concurrency, scheduler limits | REQUIRED_PRODUCTION |
| Quotas | provider request/day, concurrency, tokens, video duration | OPTIONAL_PRODUCTION with bounded defaults |
| Live switches | `VAYUJIT_LIVE_*`, Ads spend switches/caps | REQUIRED_PRODUCTION safety controls; FALSE by default |
| Operations | backup directory, retention, maintenance marker, metrics | REQUIRED_PRODUCTION / OPTIONAL_PRODUCTION |
| Desktop | Electron/Angular versions, signing/update settings | PUBLIC_CONFIG; signing remains unconfigured |

Production settings fail fast when secure cookies, HTTPS, non-local trusted origins, session secret, encryption key, and storage configuration are missing. Local and test modes continue to use deterministic fake providers without live credentials. No deprecated variables are silently treated as live-provider enablement.