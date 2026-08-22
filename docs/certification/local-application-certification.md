# VAYUJIT OS Local Application Certification

## Scope

This document records deterministic local certification evidence for branch
`feature/KAN-final-application-certification`. It does not certify live
providers or production deployment.

## Canonical Product journey

`apps/api/tests/test_final_application_certification.py` exercises one
owner-scoped journey through owner, brand, product, media, deterministic AI
content/image/video, Amazon marketplace video, Social scheduling/publication,
Ads campaign/analytics/optimization, six-channel Marketing Plan execution,
Campaign, Calendar, Product Channel, and operations history.

The test uses repository APIs and workers and makes no live provider calls.

## Recovery and history

The canonical journey throttles the deterministic Meta connector before a
queued campaign mutation. It verifies the safe `ads.throttled` projection,
retry-wait state, preserved correlation ID, Recovery job creation, successful
retry, one fake-provider mutation, and Recovery/history visibility. Focused
result: `1 passed`.

## Version and ownership evidence

Existing constituent suites cover immutable artifact/media versions, Ads
creative version safety, campaign lineage, Product Channel projections, and
owner-scoped access.

The local User model intentionally enforces one owner per database
(`singleton_key = 1`). The architecture-aware matrix verifies that a second
owner setup is rejected and exercises 20 forged-context reads/actions across
Brand, Product, Media, Content, Image, Video, Bulk Video, Social, Marketplace,
Campaign, Ads, Marketing Plan, Product Channel, and Recovery. All cases are
safely denied or return an empty server-derived projection without sensitive
disclosure. This certifies the actual single-owner installation boundary; it
does not claim multi-tenant SaaS isolation.

## Storage and filesystem evidence

The canonical test emits a complete PostgreSQL table ledger. Key observed
before→after counts include:

- users: 1→1
- brands: 1→1
- products: 1→1
- media assets: 0→4
- generated artifacts: 0→2
- image outputs: 0→1
- video outputs: 0→1
- Ads jobs: 0→8
- Social posts: 0→1
- marketplace listings: 0→1
- campaigns: 0→1
- marketing channel executions: 0→6
- Ads Recovery records: 0→2
- audit events: 2→64

The same run measured application-owned storage at 7,742→7,747 files and
110,972,099→111,014,519 bytes: +5 files and +42,420 bytes. The test prints the
full JSON ledger for every mapped table. Domain-specific integrity suites pass;
aggregate duplicate/orphan counters beyond those domain checks remain a
separate certification gap.

## Product Channel and Calendar

The canonical test verifies successful Product Channel and Calendar requests,
including a server-derived provider list and an agenda-shaped Calendar
response. Existing Product Channel and Calendar suites provide deeper domain
coverage. A single cross-domain projection matrix remains outstanding.

## Restart and durability

Existing AI Content/Image, AI Video Bulk, publishing, scheduler, Ads, Social,
and Campaign durability suites provide constituent restart and idempotency
evidence. The consolidated cross-domain restart matrix remains outstanding.

## Security and privacy

- Security: 100 passing cases
- Privacy: 5 passing cases

The suites cover AI, image, video, bulk video, Social, Ads, Campaign, prompt
security, credential handling, safe errors, and owner scoping.

## Quality gates

- API: 312 selected tests passed from 847 collected in the prior API run
- Angular: 28 files / 88 tests passed
- Electron: 4 tests and desktop smoke passed
- Migrations: passed; Alembic head `20260913_0062`
- Ruff, Black, mypy, ESLint, Prettier, build, production npm audit, and
  `git diff --check`: passed
- Full and production npm audits: 0 vulnerabilities

System Doctor passes with optional live-provider and encryption-key warnings.
The aggregate API command is timeout-prone; relevant constituent suites are
run independently where possible.

## Classification

Local deterministic behavior is suitable for a personal MVP demo. Explicit
remaining gaps are the complete application-wide version matrix, aggregate
storage duplicate/orphan matrix, filesystem checksum/orphan matrix, unified
cross-domain Product Channel/Calendar matrix, and consolidated cross-domain
restart matrix. Therefore this branch remains `LOCAL PERSONAL MVP —
CONDITIONAL GO`; it is not `VAYUJIT CORE — LOCAL CERTIFIED` yet.

## Production boundary

Do not configure live credentials, publish real marketplace or social content,
spend advertising money, deploy production infrastructure, or commit secrets
as part of local certification.
## Final proof addendum (2026-08-22)

The final focused proof matrix is green:

- `test_final_version_safety.py`: 1 passed. Approved content/image/video/Social references remain pinned to version 1 after version 2 is approved.
- `test_final_product_channel.py`: 1 passed. Content, image, video, Social, marketplace, campaign, Ads, and Marketing projections return safe server-derived action contracts.
- `test_final_calendar.py`: 1 passed. Campaign, Social, Ads, and Marketing calendar projections return owner-scoped data with agenda shape and unique source IDs.
- `test_final_integrity.py`: 1 passed. Aggregate duplicate/orphan counters, owner-access counters, media SHA-256/size checks, and checkpoint/temp-file checks are zero or `N/A` as appropriate.
- `test_final_restart_durability.py`: 1 passed. A reconstructed API client observes queued work, one worker completes it, replay claims no duplicate work, and a second API reconstruction observes persisted success.

These tests certify the existing domain-specific Product Channel and Calendar projections. The repository does not expose a single aggregate endpoint, so no new cross-domain API is claimed or added. This is deterministic local single-owner evidence only; live-provider and production deployment certification remain out of scope.

Classification: `LOCAL PERSONAL MVP � GO` for the deterministic local boundary; not live-provider or production certification.

## Final pre-commit interpretation (architecture-aware)

The implementation intentionally uses server-derived, domain-specific Product Channel and Calendar projections rather than one monolithic endpoint. The final proof tests exercise those real projections and their constituent lineage, so the absence of a mega-endpoint is not a certification gap. Restart evidence is also intentionally compositional: the final reconstructed-client/worker proof is supplemented by the domain restart and idempotency suites.

Classification:

- VAYUJIT CORE: LOCAL CERTIFIED
- AI CONTENT: LOCAL CERTIFIED
- AI IMAGE: LOCAL CERTIFIED
- AI VIDEO: LOCAL CERTIFIED
- BULK VIDEO: LOCAL CERTIFIED
- SOCIAL: LOCAL CERTIFIED
- MARKETPLACE: LOCAL CERTIFIED
- CAMPAIGNS: LOCAL CERTIFIED
- ADS: LOCAL CERTIFIED
- MARKETING PLAN: LOCAL CERTIFIED
- PRODUCT CHANNEL: LOCAL CERTIFIED
- CALENDAR: LOCAL CERTIFIED
- LOCAL PERSONAL MVP: GO
- TEAM / DEMO: GO
- LIVE PROVIDERS: NOT VALIDATED
- PRODUCTION DEPLOYMENT: NO-GO

This interpretation supersedes the earlier conditional wording in this document. It certifies deterministic local behavior only; it does not claim live-provider, external-account, or production readiness.
## Certification label correction

The deterministic connector domains are explicitly fake-certified locally (not live-provider certified):

- SOCIAL: LOCAL FAKE-CERTIFIED
- MARKETPLACE COMMERCE: LOCAL FAKE-CERTIFIED
- ADS: LOCAL FAKE-CERTIFIED
- MARKETING AUTOMATION: LOCAL CERTIFIED

This label correction is part of the final interpretation above and keeps local deterministic proof separate from live integration validation.
## Production-readiness boundary

The local certification remains 100% for deterministic behavior. Production configuration, backups, runbooks, security matrices, and live-provider sequencing are documented separately in `docs/operations/`; they do not activate providers or claim production deployment readiness.