# Backup and Restore Runbook

```powershell
npm.cmd run backup:create
npm.cmd run backup:list
npm.cmd run backup:verify -- --latest
npm.cmd run backup:restore-plan -- --latest
```

Backups use `pg_dump -Fc`, SHA-256, JSON sidecars, and `./var/backups`. They are not encrypted.
Automated destructive restore is unsupported. For a test restore, create and verify a fresh
pre-restore backup, enable maintenance, restore only into a clearly named disposable
`restore_test` database, validate migrations and health, then disable maintenance. Never validate
restore against development data.
