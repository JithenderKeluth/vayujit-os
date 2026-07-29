# ADR-026: Encrypted WordPress credentials

Status: Accepted

WordPress application passwords are encrypted with the established AES-GCM credential facility.
Owner database configuration takes precedence over deployment environment configuration. Secrets
are accepted only on writes and are never returned, logged, audited, or copied into destinations.
