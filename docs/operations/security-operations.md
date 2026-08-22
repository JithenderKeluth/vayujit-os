# Security operations

Credentials are encrypted with AES-GCM and versioned ciphertext. `rotate_credential` decrypts with the current key and re-encrypts using a new key ID; retain the previous key only for the documented migration window. Missing or corrupt keys fail closed and never fall back to plaintext.

Rotate session secrets by deploying a new secret and revoking active sessions. Revoke provider tokens at the provider, disable the corresponding `VAYUJIT_LIVE_*` switch, and inspect correlation IDs in audit history. Never include credentials, cookies, DSNs, prompts, PII, or raw provider payloads in logs or responses.

Report suspected leaks immediately, preserve redacted evidence, rotate affected secrets, and run the production security matrix before re-enabling any provider.