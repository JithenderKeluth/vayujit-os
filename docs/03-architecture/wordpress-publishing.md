# WordPress publishing connector

WordPress is the first remote publishing connector. The deterministic mock remains the default
offline connector and workflow compatibility path.

Credentials use this precedence: encrypted owner configuration, deployment environment variables,
then unconfigured. Responses, logs, audits, snapshots, and diagnostics never expose application
passwords. A credential-encryption key is required to store a password in PostgreSQL.

The connector supports validation, taxonomy discovery, draft creation, publication, updates,
remote-state reconciliation, media upload, and moving posts back to draft. It deliberately does
not delete remote content. Destination records store content mapping preferences, not credentials.

Remote calls use a fixed WordPress REST route allowlist, bounded timeouts and response sizes,
redirect blocking, safe error classes, and URL validation. Production configuration requires
HTTPS and rejects local, private, reserved, link-local, and loopback destinations. Tests use an
in-process fake transport and never contact a real WordPress site.

Each transport attempt is persisted separately. A timed-out create is treated as ambiguous and
requires reconciliation instead of blind retry, preventing likely duplicate posts. The local
idempotency key remains authoritative for repeated client submissions.

Operator commands:

```powershell
npm.cmd run publishing:status
npm.cmd run publishing:validate
npm.cmd run publishing:destinations
npm.cmd run publishing:executions
```

Configure through `/settings/publishing/connectors/wordpress`, validate, then enable the connector.
Use WordPress application passwords with the minimum permissions needed to manage posts and media.
