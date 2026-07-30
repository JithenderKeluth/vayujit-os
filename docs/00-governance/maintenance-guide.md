# Maintenance and Retention

```powershell
npm.cmd run maintenance:status
npm.cmd run maintenance:on -- --confirm
npm.cmd run maintenance:off -- --confirm
npm.cmd run maintenance:cleanup -- --dry-run
npm.cmd run sessions:cleanup -- --dry-run
```

Maintenance uses a canonical local marker outside web-served files. Business writes return
`503 maintenance_mode`; health, backups, reads, and logout remain available. Cleanup is dry-run
capable and never deletes core business records or immutable audit events.
