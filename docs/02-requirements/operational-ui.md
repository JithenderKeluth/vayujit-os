# Operational UI

## Dashboard

`GET /api/v1/dashboard/summary` returns owner-scoped database counts and ten recent safe audit
items. Brand filtering applies to Product, Artifact, Publishing, and Workflow metrics. Total
Brands remains an owner-wide metric. Retryable failures include only failed Publishing
executions explicitly marked retryable.

The UI shows action queues, a labelled CSS Workflow distribution chart, recent activity, and
bounded quick actions. No browser-side bulk aggregation is used.

## Approvals

`GET /api/v1/approvals` provides newest-first, paginated Artifact review queues with status,
Brand, Product, template, and bounded search filters. Details reuse the authoritative AI Artifact
service and include only same-Product/template versions for field-by-field inspection. Comparison
defaults to the immediately previous eligible version, prevents selecting the same version on
both sides, and identifies scalar and ordered-array changes. Approve, reject, and regenerate act
on the selected current version through existing lifecycle endpoints. Generated content is
untrusted and rendered only with Angular text interpolation; generated HTML, `innerHTML`,
sanitizer bypass, and unsafe DOM insertion are prohibited.

## Execution History

`GET /api/v1/operations/history` normalizes safe append-only audit events into a bounded
owner-scoped read model. It does not modify or merge domain records. List and timeline modes show
only safe summaries and stored relationships.

CSV export is UTF-8, limited to 5,000 filtered records, excludes raw metadata/content/snapshots,
and prefixes spreadsheet-formula-leading cells (`=`, `+`, `-`, `@`) with an apostrophe.

## Settings and diagnostics

Typed `OwnerPreference` columns persist timezone, display/pagination preferences, theme/density,
and supported AI/Publishing defaults. No unrestricted key-value store or fake provider controls
exist. Password changes verify the current password and never audit password values. Session
responses omit tokens and hashes.

Default Brand means the Brand selected after login only when no valid active Brand is already
established. Changing the default does not forcibly switch the current context. A preferred
prompt template is preselected during generation only while enabled. A preferred Publishing
destination is selected only while active and compatible with the selected Brand. Invalid,
archived, disabled, inaccessible, and incompatible references are ignored safely and require
reselection rather than silently submitting an unrelated choice.

System diagnostics expose version, environment, health, migration revision, runtime version, and
registered mock summaries without URLs, credentials, paths, environment variables, or secrets.
