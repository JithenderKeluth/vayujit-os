# Security Policy

Do not report vulnerabilities in a public issue. Contact the repository owner privately
with reproduction steps, impact, and affected versions.

Never commit credentials, tokens, production data, database dumps, or `.env` files.
The walking skeleton is for local development and is not production hardened. Its
loopback API, Electron security settings, CORS restriction, and secret-handling rules
must not be weakened without security review.

## Windows release signing

Public Windows artifacts require an approved certificate or trusted signing service with timestamping.
Self-signed and test certificates are not public-release credentials. Keep `CSC_LINK`,
`CSC_KEY_PASSWORD`, certificate-store configuration, private keys, and signing-service tokens in a
secure release environment only; never commit them, place them in `.env` files, or package them into
installer resources. Verify Authenticode status, certificate chain, publisher subject, timestamp, and
post-signing SHA-256 before distribution.
