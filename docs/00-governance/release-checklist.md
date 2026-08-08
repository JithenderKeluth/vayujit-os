# Release Checklist

- Run security audit, license visibility, system doctor, builds, lint, tests, and Electron smoke.
- Validate the current migration head `20260812_0022`, downgrade to `20260811_0021`, and re-upgrade.
- Verify provider credentials are masked, fake-provider tests pass, and no paid provider is called.
- Record development database counts before and after guarded validation.
- Create and verify a backup; rehearse restore only on a marked disposable database.
- Confirm maintenance on/off and cleanup dry-run.
- Inspect rendered browser and Electron UI when those control surfaces are available.
# WordPress Publishing UX

- [ ] Migration 0012 clean upgrade, downgrade to 0011, and re-upgrade passes.
- [ ] Media storage is writable and free-space threshold is met.
- [ ] Media, taxonomy, preview, drift, recovery, Angular, and Electron tests pass.
- [ ] Development business-data counts are unchanged.
- [ ] No path, credential, raw bytes, authorization header, or unsafe HTML is rendered.
- [ ] Optional real-site validation used only a non-production operator-controlled site.
- [ ] Migration 0013 clean upgrade, downgrade to 0012, and re-upgrade passes.
- [ ] Shopify token is absent from API responses, logs, audit, exports, and Electron storage.
- [ ] Draft creation, explicit activation, update, throttling, cancellation, and reconciliation pass.
# Campaign release checks

- Verify Campaign migration history through `20260812_0022`, including downgrade to `20260811_0021`
  and re-upgrade.
- Run Campaign unit/integration tests plus scheduler, worker, WordPress, Shopify, Workflow,
  Recovery, Health, Angular, and Electron regressions.
- Confirm development Campaign/activity/dependency/link counts remain unchanged by tests.
- Verify exact Artifact approval, owner isolation, exact-Origin, maintenance, bounded calendar and
  dependency-cycle rejection.
- Record browser and Electron manual acceptance honestly.

## Public Windows release gate

- [PASS] Internal/local Windows RC gate is GO.
- [FAIL] Approved Windows code-signing certificate or approved signing-service configuration is available.
- [FAIL] Signed installer signature, trusted chain, and timestamp are verified.
- [PASS] Unsigned package checksum and forbidden-content scan pass; regenerate the checksum after signing.
- [PASS] Production dependency audit reports zero vulnerabilities; license visibility warnings remain documented.
- [PASS] Electron unit tests, packaged smoke, migration, backup/upgrade, and regression suites pass.
- [FAIL] Signed-installer acceptance, trusted publisher display, and no-unsigned-publisher-warning validation.
- [WARN] SmartScreen reputation is separate from signature validity and may require post-release reputation building.
- [NO-GO] Public distribution until signing, timestamp, publisher identity, and signed-installer acceptance pass.

## Required signing evidence

Use electron-builder's external signing inputs through a secure CI or release workstation. Do not commit
certificate files, private keys, passwords, or signing-service tokens. Supported examples are
`CSC_LINK` and `CSC_KEY_PASSWORD`; inject them only for the packaging process and remove them afterward.
The signing provider must apply a trusted timestamp. Verify the installer and packaged executable with
`Get-AuthenticodeSignature` and, where available, `signtool verify /pa /v`; public release requires
`Status = Valid`, a trusted chain, and a valid timestamp.