# Release Checklist

- Run security audit, license visibility, system doctor, builds, lint, tests, and Electron smoke.
- Validate migration `20260729_0009` upgrade/downgrade/re-upgrade.
- Record development database counts before and after guarded validation.
- Create and verify a backup; rehearse restore only on a marked disposable database.
- Confirm maintenance on/off and cleanup dry-run.
- Inspect rendered browser and Electron UI when those control surfaces are available.
