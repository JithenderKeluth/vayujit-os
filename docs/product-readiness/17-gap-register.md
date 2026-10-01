# Master gap register

| ID | Area | Concrete problem/evidence | Severity | Dependency | Closure test |
|---|---|---|---|---|---|
| PR-001 | Live product research | ApprovedWebFetcher rejected every 1C.7 URL before HTTP; no product artifact. | P0 | Approved source policy + Brave config | Real URL→HTML→identity→ProductOpportunity→BA projection. |
| PR-002 | Commercial correctness | `₹3 lakh` became unresolved capital/currency in goal parsing. | P1 | UTF-8/request boundary | API and journey assertions preserve amount/currency. |
| PR-003 | Product selection | No real candidates reached compare/select. | P1 | PR-001 | Human selection persists against observed evidence. |
| PR-004 | Supplier live data | Marketplace providers are fixture/provider-gated. | P1 | PR-003 + credentials | Real supplier evidence and provenance. |
| PR-005 | Economics | Real FX/freight/duty/quote inputs are not live certified. | P1 | PR-004 | Unknown vs zero and deterministic landed-cost brief. |
| PR-006 | Production operations | Backups, restore, alerts, rollback and vendor provisioning lack evidence. | P0 | All live slices | Deployment drill and operational acceptance. |
| PR-007 | UX complexity | Primary workflows expose IDs/provider concepts and inconsistent blocked states. | P2 | Vertical journey evidence | Zero-technical-knowledge usability review. |
| PR-008 | Test value | Existing coverage emphasizes implementation over seller artifact. | P2 | PR-001–005 | Golden journey acceptance suite. |
| PR-009 | Worktree hygiene | Generated `output/` is untracked; broad local artifacts exist on disk. | P1 | Before release commit | Explicit allowlist and clean release tree. |
| PR-010 | Observability | Live readiness/latency/provider failure SLO evidence is incomplete. | P2 | PR-006 | Metrics, alerts, quota and recovery dashboards. |
