# Staging readiness checklist

- [ ] Production-shaped mode and HTTPS origins configured
- [ ] Secrets loaded from a secret manager; no `.env` secrets committed
- [ ] PostgreSQL backup and restore drill completed
- [ ] Media backup and checksum restore completed
- [ ] Migrations verified before API startup
- [ ] API, workers, scheduler, liveness, and readiness healthy
- [ ] Monitoring hooks and alert thresholds configured
- [ ] Live switches OFF initially; Ads spend OFF
- [ ] Security, configuration, observability, and backup matrices green
- [ ] Smoke tests, rollback plan, and incident owner recorded

Staging is ready for controlled configuration only, not production traffic.