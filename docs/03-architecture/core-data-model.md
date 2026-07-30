# Core Data Model

All identifiers are UUIDs. Mutable records contain `created_at` and `updated_at` UTC timestamps; execution/audit records are append-oriented. `owner_id` references the sole `User` where ownership must remain explicit.

| Entity | Important attributes |
|---|---|
| User | `id`, `username`, `password_hash`, `status`, `last_login_at`, timestamps |
| Brand | `id`, `owner_id`, `name`, `normalized_name`, `slug`, identity fields, `status`, `is_active_context`, `archived_at`, timestamps |
| Product | `id`, `brand_id`, `owner_id`, normalized identity, type/status, content, tags, decimal pricing, identifiers, inventory, weight, flags, archive/timestamps |
| ProductAsset | `id`, `product_id`, `storage_key`, `media_type`, `size_bytes`, `checksum`, timestamps |
| PromptTemplate | `id`, `key`, `version`, `template`, `output_schema_version`, `status`, timestamps |
| AIProviderConfiguration | `id`, `provider_type`, `display_name`, `secret_reference`, `settings_json`, `enabled`, timestamps |
| WorkflowDefinition | `id`, `key`, `version`, `definition_json`, `status`, timestamps |
| WorkflowExecution | `id`, `definition_id`, `product_id`, `owner_id`, `state`, `current_step`, `correlation_id`, `failure_code`, timestamps |
| WorkflowStepExecution | `id`, `workflow_execution_id`, `step_key`, `attempt`, `state`, `input_reference`, `output_reference`, `error_code`, `started_at`, `finished_at` |
| ApprovalRequest | `id`, `workflow_execution_id`, `artifact_id`, `status`, `requested_at`, `decided_at`, `decided_by`, `comment` |
| GeneratedArtifact | `id`, `workflow_execution_id`, `product_id`, `prompt_template_id`, `provider_configuration_id`, `schema_version`, `content_json`, `validation_status`, timestamps |
| PublishingConnection | `id`, `adapter_type`, `display_name`, `secret_reference`, `settings_json`, `status`, timestamps |
| PublishingExecution | `id`, `workflow_execution_id`, `artifact_id`, `connection_id`, `idempotency_key`, `status`, `external_id`, `external_url`, `error_code`, timestamps |
| AuditEvent | `id`, `actor_id`, `event_type`, `entity_type`, `entity_id`, `correlation_id`, `sanitized_metadata`, `occurred_at` |
| ApplicationSetting | `id`, `key`, `value_json`, `secret_reference`, `updated_by`, timestamps |

Brand names and slugs are unique per owner. A partial unique index permits only one
`is_active_context = true` brand per owner, and a check constraint prevents archived brands from
remaining active. Archive is a soft state transition.

Key constraints also include unique username, SKU per owner, prompt/definition key plus version,
one active approval per execution, and unique publishing idempotency key. Generated artifacts are
immutable versions. See [core-data-model.mmd](diagrams/core-data-model.mmd).

Product normalized names and slugs are unique per brand. Non-null SKU and barcode values are
unique per owner. Money uses `NUMERIC(12,2)`; weight uses `NUMERIC(12,3)`. Database checks prevent
negative prices, costs, weight, inventory, and thresholds; compare-at price below sale price; and
status/archive-timestamp disagreement.

`PublishingDestination` stores strict safe mock configuration and an optional Brand scope.
`PublishingExecution` stores owner-scoped idempotency and schema-versioned content/request
snapshots. `PublishingExecutionAttempt` is immutable and unique by execution plus attempt number.
