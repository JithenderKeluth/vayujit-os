# Production environment checklist

- [ ] Dedicated installation and database; `ck_users_single_owner` preserved.
- [ ] Patched Linux host, private network, firewall, and SSH/operator controls.
- [ ] HTTPS certificate and renewal process mounted outside the repository.
- [ ] `VAYUJIT_PUBLIC_API_URL`/`VAYUJIT_PUBLIC_WEB_URL` are HTTPS URLs.
- [ ] CORS allowlist contains only the seller web origin; no wildcard/loopback.
- [ ] Secure session cookie, same-site policy, and trusted proxy are reviewed.
- [ ] Secret-managed session and credential-encryption keys are strong and rotated.
- [ ] Dedicated non-default PostgreSQL role; database is not publicly exposed.
- [ ] Durable private media/object storage configured and tested.
- [ ] Encrypted backup recipient, retention, monitoring, and restore destination approved.
- [ ] Emergency stop and all live provider/write switches remain deny-by-default.
- [ ] Expected Alembic revision is pinned to the built image.
- [ ] Worker/scheduler resources, logs, restart policy, and graceful shutdown verified.
- [ ] HUMAN approval recorded for any provider OAuth or external execution.
