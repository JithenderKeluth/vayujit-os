# Staging and live-provider sandbox certification

This document records the bounded staging boundary for VAYUJIT OS. It is not a
production deployment approval and it does not claim that a real provider has
been validated.

## Provider priority analysis

| Rank | Provider | Evidence | Risk decision |
|---:|---|---|---|
| 1 | Shopify | Real connector boundary, loopback fake server, idempotent draft flow, throttle/timeout/retry handling, campaign E2E coverage | First candidate |
| 2 | Amazon Marketplace | Typed SP-API boundary and deterministic transport with idempotency, throttling, reconciliation, and worker tests | Sandbox credentials unavailable |
| 3 | Flipkart | Typed connector, fake transport, throttling, ambiguity and worker tests | Sandbox credentials unavailable |
| 4 | WordPress | Real HTTP connector and credential validation, but no repository-owned sandbox | Reversible draft only after sandbox approval |
| 5 | OpenAI-compatible AI | Credential/configuration boundary exists; paid live calls have cost risk | Read-only validation first |
| 6 | Social providers | Local fake contracts only; no live call or callback certification | Not validated |
| 7 | Ads | Local fake/read-only contracts; spend switch and caps remain off | Never enable in this phase |

**Selected first provider:** Shopify. The repository-owned loopback fake is the
only provider boundary with a complete, network-free sandbox-shaped proof. A
real Shopify test-store credential is not present, so real sandbox mutation is
**NOT AVAILABLE**, not a fabricated PASS.

## Staging environment contract

Staging requires `VAYUJIT_ENVIRONMENT=staging`, HTTPS-only trusted origins,
secure cookies, a staging-only PostgreSQL URL, a staging credential-encryption
key, a 32-character session secret, isolated filesystem/S3-compatible media
storage, bounded worker/scheduler settings, and provider credentials loaded from
deployment secrets. `VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP=true` is the
operator kill switch. All live domain switches and Ads spend default to false.

Run `npm.cmd run staging:validate`. The validator rejects missing database,
encryption key, session secret, HTTPS/trusted origins, enabled-provider
credentials, and an Ads mutation switch without the spend gate.

## Storage and recovery

The existing owner-scoped filesystem storage is the staging-compatible
implementation. It records size, MIME, SHA-256, and Product/owner lineage and
is exported by the existing media backup archive. The disposable
`scripts/media-recovery-drill.py` verifies PostgreSQL plus image/video/thumbnail
lineage, checksums, sizes, MIME values, and orphan detection. Object storage is
not claimed until an S3-compatible implementation is configured.

## Safety and provider runtime

`operations/staging.py` centralizes provider mode (`fake`, `sandbox`, `live`),
status (`NOT_CONFIGURED`, `CONFIGURED`, `VALIDATING`, `VALID`, `INVALID`,
`DISABLED`), timeout/retry contracts, bounded idempotency, failure taxonomy,
HMAC webhook freshness/replay checks, safe payload redaction, and metrics.
`/api/v1/system/staging/providers`, `/metrics`, and `/contract` are authenticated
and return status/contract metadata only. The existing maintenance marker is a
second operator emergency stop; reads, diagnostics, reconciliation, and history
remain available while writes are blocked.

Provider jobs, attempts, mappings, and audit records must carry the runtime
lineage returned by `ProviderRuntimeLineage`. No credential or request payload is
stored in the status registry or logs.

## Certification evidence

- Configuration, secret handling, status registry, kill switch, emergency stop,
  runtime mode, timeout, rate-limit, 5xx, auth, network, ambiguity, idempotency,
  webhook, privacy, and redaction contracts: `tests/test_staging_provider_certification.py`.
- Existing Shopify loopback, campaign, worker, duplicate-prevention, and
  reconciliation suites remain the provider-specific evidence.
- Real Shopify read-only account validation and one reversible test-store
  mutation require a test-store URL/token and operator confirmation; neither is
  present in this repository checkout.
- Ads mutation/spend calls are zero by configuration and remain disabled.

## Failure, recovery, and correction model

Timeout, 429, 5xx, authentication, network, and ambiguous results normalize to
safe retry/reconciliation classifications. Recovery is local and idempotent;
ambiguous operations reconcile before replay. Shopify correction is provider
dependent: draft update/delete is reversible in a test store, while a published
remote change may require a compensating update. No rollback guarantee is made
without provider evidence.

## Monitoring and storage ledger

The provider-neutral `/health/metrics` endpoint and staging metrics endpoint
expose request, worker, scheduler, queue/retry, Recovery, provider failure,
latency, and reconciliation counters. Alert thresholds are defined in
`production-operations-contracts.md`; no monitoring vendor is configured.
Staging review must record DB growth, media/object growth, jobs, attempts,
provider mappings, audit events, and Recovery records before and after each
provider exercise.

## Go/no-go

- Local deterministic certification: **100% / GO**.
- Staging foundation: **READY for controlled configuration**, not deployed.
- Selected Shopify real sandbox: **CONDITIONAL GO** after test-store credentials,
  backup-before, one mutation, reconciliation, and Recovery evidence.
- Other providers: **NOT VALIDATED**.
- Real Ads spend: **DISABLED / 0 calls**.
- Production deployment: **NO-GO** until object storage, monitoring, signing,
  provider credentials, and compliance review are complete.

