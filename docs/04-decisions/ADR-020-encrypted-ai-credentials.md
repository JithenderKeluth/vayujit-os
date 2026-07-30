# ADR-020: Encrypted AI provider credentials

## Status

Accepted

## Decision

Owner provider credentials are encrypted with AES-256-GCM using a deployment
key. Database credentials precede deployment environment credentials. APIs
return only masked source summaries.

## Consequences

Credential persistence fails closed without the deployment key. Rotation of the
encryption key itself remains an operator procedure.
