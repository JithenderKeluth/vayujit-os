# Domain Boundaries

All modules expose application interfaces and own their persistence mappings. Cross-module references use identifiers; direct imports of another module’s repositories, ORM models, or internal services are prohibited.

| Module | Responsibility and owned entities | Public interfaces | Allowed dependencies | Prohibited dependencies |
|---|---|---|---|---|
| Identity | Owner lifecycle, credentials, sessions; `User` | initialize owner, authenticate, revoke/validate session | Settings, Audit interface | Brand/product/workflow internals |
| Brands | Brand identity, lifecycle, archive state, and active context; `Brand` | create/get/list/update/archive/restore/activate brand | Identity actor ID, Audit interface | Product persistence |
| Products | Product identity, content, commerce metadata, lifecycle; `Product` | create/get/list/update/activate/draft/archive/restore product | Brands ownership query, Identity actor ID, Audit | AI, workflow, publishing internals |
| AI | Provider configuration, prompts, generation; `PromptTemplate`, `AIProviderConfiguration`, `GeneratedArtifact` | generate structured artifact, validate result | Settings, Products DTO, Audit | Approval/publishing state changes |
| Workflows | Definitions, executions, steps, transition policy; `WorkflowDefinition`, `WorkflowExecution`, `WorkflowStepExecution` | start, advance, fail, retry, cancel, recover, history | Products query, AI, Approvals, Publishing interfaces, Audit | UI/Electron, adapter implementations |
| Approvals | Human decision lifecycle; `ApprovalRequest` | request, approve, reject, get pending | Identity actor, Audit | Direct publishing or workflow persistence |
| Publishing | Connections and idempotent operations; `PublishingConnection`, `PublishingExecution` | publish approved artifact, get result/capabilities | Approvals decision query, AI artifact query, Audit | Product/identity persistence |
| Audit | Append-only business/security evidence; `AuditEvent` | append sanitized event, query history | Identity actor ID | Any module mutation |
| Settings | Non-secret configuration and protected secret references; `ApplicationSetting` | get/update setting, resolve protected secret | OS secret protection, Audit | Business-domain persistence |

The workflow application service coordinates the vertical slice through public interfaces. Domain events may be introduced later but are not required for Sprint 1.

The Brands module owns all brand persistence. It receives the authenticated actor from Identity
and writes events only through the Audit interface. Active-context changes are serialized per
owner and constrained in PostgreSQL.

The Products module owns product persistence and lifecycle validation. Brand reassignment is
allowed only to a non-archived brand owned by the actor and creates a distinct audit event.
Products expose decimal money as strings and do not depend on future inventory, workflow, AI, or
publishing implementations.
