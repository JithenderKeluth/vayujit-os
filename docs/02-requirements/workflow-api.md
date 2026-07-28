# Workflow API

The owner-authenticated `/api/v1/workflows` API exposes the constrained Product Content Publish
workflow. It coordinates existing domain services; it does not duplicate Product, Artifact,
approval, or Publishing records.

| Method | Path | Purpose |
|---|---|---|
| GET | `/templates` | List enabled system templates without executable definitions |
| POST | `/` | Create a draft for an active Product and compatible active destination |
| GET | `/` | Owner-scoped, filterable, paginated workflow history |
| GET | `/{id}` | Workflow, safe error, related IDs, and ordered step attempts |
| POST | `/{id}/start` | Run generation and pause for approval |
| POST | `/{id}/continue` | Re-read the authoritative Artifact decision and publish if approved |
| POST | `/{id}/retry` | Append an attempt for the failed retryable step |
| POST | `/{id}/cancel` | Cancel a draft, waiting, or failed workflow |

Creation accepts `product_id`, `destination_id`, `workflow_template_id`, and optional bounded AI
instructions. Brand and owner scope are derived and validated server-side. Continuation is
idempotent after completion. Rejected Artifacts fail with `artifact_rejected`; they are not
regenerated automatically. Publishing receives a stable workflow-derived idempotency key.

Workflow regression tests run only against the guarded, marked test database. Electron runtime
validation uses the renderer-ready smoke command documented in the local-development guide.
