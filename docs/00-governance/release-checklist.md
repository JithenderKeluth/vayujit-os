# Release Checklist

- Run security audit, license visibility, system doctor, builds, lint, tests, and Electron smoke.
- Validate migration `20260730_0010` upgrade, downgrade to `20260729_0009`, and re-upgrade.
- Verify provider credentials are masked, fake-provider tests pass, and no paid provider is called.
- Record development database counts before and after guarded validation.
- Create and verify a backup; rehearse restore only on a marked disposable database.
- Confirm maintenance on/off and cleanup dry-run.
- Inspect rendered browser and Electron UI when those control surfaces are available.
