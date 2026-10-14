# PR-SOS-09 residual risk register

| Risk | State | Required owner action |
| --- | --- | --- |
| HTTPS host, certificate renewal, and firewall | OPEN | Provision and independently verify the VPS/reverse proxy. |
| Secret manager and key rotation | OPEN | Supply production session/encryption keys and rotation policy. |
| Durable object storage | OPEN | Select private storage and test media backup/restore. |
| Encrypted off-host backup and witnessed restore | OPEN | Provide an approved destination, recipient, retention, RPO/RTO, and witness. |
| Marketplace OAuth/provider certification | OPEN | Approve credentials, scopes, contracts, and read-only certification. |
| Live marketplace writes/publication | DENIED | Separate HUMAN authorization after readiness evidence. |
| External monitoring/alert delivery | OPEN | Configure alert destination and on-call ownership. |
| Angular bundle advisory | WARN | Reduce initial bundle or approve the measured warning; budget was not inflated. |
| Two pre-existing Angular lifecycle lint warnings | WARN | Add `OnInit` interfaces in a follow-up cleanup. |
| Strict mypy `commerce/schemas.py:259` | OPEN / pre-existing | Triage the existing Pydantic `Field(ne=...)` error without broad refactoring. |
