# Capability inventory

| Capability | Status | Evidence / boundary |
|---|---|---|
| Authentication, owner context | Partial / locally implemented | FastAPI auth routes and owner-scoped services; production identity/infra not live validated. |
| Business Agent and guided commerce | Partial, locally tested | Durable goals/plans/runs/checkpoints; live run in 1C.7 ended PARTIAL with no product artifact. |
| Product research/opportunities | Live but incomplete | ProductOpportunity authority and projections exist; no meaningful live candidate survived the fetch gate. |
| Trend, competitor, review intelligence | Implemented / fixture-heavy | Routes, models, evidence and deterministic analyses exist; real provider evidence is not broadly validated. |
| Website/external research | Configuration required | ApprovedWebFetcher and Brave adapter exist; source approval blocked the observed live fetch. |
| Supplier discovery/verification/shortlist | Partial, mostly local fixture | Provider-neutral and marketplace modules exist; live supplier providers are disabled/pending credentials. |
| RFQ/sourcing/economics/landed cost | Implemented / locally tested | Deterministic authorities and migrations exist; real freight, FX, duty and quote inputs are not production validated. |
| Content, campaigns, channels, ads, social | Partial / provider gated | Durable workflows and approval boundaries exist; external connectors and live credentials are not validated. |
| Inventory/orders/returns/analytics | Partial | Domain routes/workers exist; marketplace runtime readiness is configuration and certification dependent. |
| Operations/recovery/System Doctor | Implemented foundation | Health/readiness, recovery, diagnostics and workers exist; deployment SLO/restore proof remains outstanding. |
