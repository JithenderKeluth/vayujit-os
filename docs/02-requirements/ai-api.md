# AI Content Generation API

All routes use `/api/v1/ai`, require an authenticated local owner, and return JSON.

| Method | Route | Purpose |
|---|---|---|
| GET | `/providers` | List locally available provider capabilities |
| GET | `/templates` | List enabled template summaries |
| POST | `/generations` | Generate and validate content synchronously |
| GET | `/generations` | Paginated/filterable generation history |
| GET | `/generations/{id}` | Get request status and safe failure details |
| GET | `/artifacts` | Alias for filterable artifact-oriented history |
| GET | `/artifacts/{id}` | Get structured content and review metadata |
| POST | `/artifacts/{id}/approve` | Approve a pending-review artifact |
| POST | `/artifacts/{id}/reject` | Reject with a required reason |
| POST | `/artifacts/{id}/regenerate` | Create the next product artifact version |

Generation accepts `product_id`, an optional enabled `prompt_template_id`, and optional
`additional_instructions` of at most 2,000 characters. Archived products and products belonging
to archived brands cannot generate.

The response is either `completed` with an `artifact_id`, or `failed` with a stable
`error_code` and safe message. Provider output is accepted only when it matches the strict
product-content schema and contains no markup.

History filters include product, brand, request status, artifact status, date range, page, and
page size. Review decisions are idempotent only when repeated in the same target state.
# Preferred prompt template

The owner preference stores an enabled prompt-template identifier. The generation screen
preselects it when available and permits an explicit override before submission. Safe template
summaries expose names and versions but never system instructions or raw template JSON.
