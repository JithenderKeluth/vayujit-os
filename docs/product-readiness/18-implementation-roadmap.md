# Dependency-ordered implementation roadmap

| Phase | Goal | Acceptance |
|---|---|---|
| PR-0 | Runtime/data integrity | Fix budget Unicode parsing; preserve unknown/zero; clean release allowlist. |
| PR-1 | Goal→real product closure | Approved Brave/fetch configuration, real HTML, meaningful identity, durable ProductOpportunity, evidence and BA result. |
| PR-2 | Compare/select closure | Human-readable comparison and explicit product selection with provenance. |
| PR-3 | Live supplier closure | Provider-neutral live supplier discovery, identity and evidence; no contact/write. |
| PR-4 | Verification/shortlist | Due diligence, contradictions, freshness and human shortlist artifact. |
| PR-5 | Economics/decision | Quotes, FX/freight/duty inputs, landed cost, risk and decision brief with unknowns. |
| PR-6 | Launch preparation | Product/content/channel preparation with approvals and rollback. |
| PR-7 | Operate/grow | Inventory/orders/campaign/social/ads connectors, monitoring and recovery. |
| PR-8 | UX simplification | Hide IDs/provider internals, consistent state language, accessible next actions. |
| PR-9 | Production platform | Secret management, backups/restore, CI/CD, alerts, SLOs and vendor readiness. |
| PR-10 | Full milestone certification | Golden journey, security, performance, recovery and live evidence certification. |

Each phase must reuse existing authorities and close as a vertical business slice.

## Seller OS PR-SOS-08 status

PR-SOS-08 adds a shared, read-only Amazon India/Flipkart connectivity ledger and
reconciliation projection. The local transport is deterministic synthetic data;
external seller-account authorization, official contract verification, sandbox
access, and live provider calls remain explicit deployment gates. No marketplace
write, order acknowledgement, fulfilment, refund, payment, supplier action, or
credential disclosure is enabled by this phase.

PR-SOS-08.1 adds the Connection Center capability cards, explicit synthetic
transport labels, refresh/loading feedback, and accessible import controls.
The PostgreSQL/API, Angular, static, migration, and adjacent PR-SOS regression
gates pass; authenticated browser/CDP and axe scans remain pending because the
local browser harness could not initialize. See
[`../seller-os/pr-sos-08-1-validation.md`](../seller-os/pr-sos-08-1-validation.md).

> PR-SOS-09.1 local witness: production-like Compose startup, durable worker
> heartbeat, encrypted backup/restore reconstruction, and 36 authenticated
> launch checks are recorded in `docs/seller-os/pr-sos-09-1-validation.md`.
> Public production go-live remains uncertified pending the documented browser
> warning-state, accessibility-matrix, fresh-profile, and strict-mypy gates.

> PR-SOS-09.2 update: the launch-readiness warning projection and final local
> browser witness are now recorded in `docs/seller-os/pr-sos-09-2-validation.md`.
> 29/29 authenticated checks and all 12 axe states passed, but dedicated
> marker-fixture coverage, fresh-profile/proxy validation, and repository
> Python tooling remain pending; PR-SOS-09 is still **IMPLEMENTED / LOCAL
> CERTIFICATION PENDING**. No production or provider action is authorized.
