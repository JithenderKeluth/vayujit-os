# VAYUJIT QA Agent — Phases 1–3

Read [architecture, seller journeys and Windows instructions](../docs/qa/architecture.md).

```powershell
npm.cmd run qa:audit
npm.cmd run qa:unit
# Set QA_DATABASE_ADMIN_URL in this shell to an approved local postgres admin URL.
npm.cmd run qa:smoke
npm.cmd run qa:smoke -- --retest
npm.cmd run qa:phase2
npm.cmd run qa:phase3
```

Only freshly created, token-marked `vayujit_qa<token>_test` databases are used.
The runner never targets the normal or golden database, never starts/stops Docker,
and cannot execute marketplace/provider mutations. No `.env` edits are required.

Outputs: [executed report](../docs/qa/initial-report.md),
[source coverage matrix](../docs/qa/coverage-matrix.md),
[registered API inventory](../docs/qa/runtime-api-inventory.json),
[finding schema](finding.schema.json).

An exit code of 1 is intentional when a scenario fails. Do not delete an assertion
or disable an axe rule to turn a known application finding into a pass. Production
fixes require separate authorization; full application coverage is not claimed.

Use `--retest` for Phase 1 to preserve its original baseline. Phase 3 adds
operational order/inventory/financial/Action Center cases, original mobile axe
review, read-only PostgreSQL parity and an authenticated restart of its owned API
process only. It does not start a publishing worker or operate Docker.

See [Phase 3 audited contracts](../docs/qa/phase-3-architecture.md),
[actual validation and commands](../docs/qa/phase-3-validation.md), and
[reviewed findings](../docs/qa/phase-3-reviewed-findings.json).
