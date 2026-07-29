# Media security

- Maximum size defaults to 10 MiB and maximum dimension to 10,000 pixels.
- Declared MIME type, extension, file signature, structure, dimensions, and filename must agree.
- Storage keys are generated from an owner prefix and checksum; clients cannot submit paths.
- Preview responses are authenticated, owner-scoped, `nosniff`, private-cache responses.
- Writes retain exact-Origin and maintenance-mode enforcement.
- Logs and audit events contain bounded metadata, never bytes or paths.
- Operators monitor write permission and the configured free-space threshold through health.
