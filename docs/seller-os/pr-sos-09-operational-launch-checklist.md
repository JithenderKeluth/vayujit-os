# Operational launch checklist

- [ ] `/health/live` and `/health/ready` are green through the reverse proxy.
- [ ] Current migration equals the deployment-pinned expected revision.
- [ ] API, web, worker, proxy, PostgreSQL, storage, and backup logs are
      collected without secrets, tokens, raw provider payloads, or buyer PII.
- [ ] Worker heartbeat, queue leases, restart recovery, and graceful shutdown
      are observed.
- [ ] Action Center contains no unreviewed critical launch blocker.
- [ ] Catalog, SKU, inventory, financial, marketplace, and backup evidence are
      linked from Launch readiness.
- [ ] Owner isolation and secure-session checks pass on the deployed origin.
- [ ] Emergency stop is tested and external mutations remain denied.
- [ ] HUMAN go-live decision, incident owner, rollback image, and recovery
      operator are recorded.
