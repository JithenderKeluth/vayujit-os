# Container Architecture

| Container | Responsibilities | Communication |
|---|---|---|
| Electron shell | Application lifecycle, secure window, preload bridge, FastAPI process startup/shutdown, secure session-token storage | Loads packaged Angular; starts FastAPI; narrow IPC only for desktop capabilities |
| Angular application | Screens, client validation, authenticated workflow, approval, and history interactions | JSON/HTTP to loopback FastAPI |
| FastAPI application | Authentication, use cases, domain rules, validation, persistence coordination, adapter orchestration, audit | SQL to PostgreSQL; filesystem API; typed adapter interfaces |
| PostgreSQL | Transactional source of truth and execution history | Accessible only to FastAPI |
| Local asset storage | Managed product assets and backup files | Accessible only through FastAPI services |
| AI provider adapters | Normalize provider calls and validate provider-specific responses | In-process interface; mock first, Ollama over loopback HTTP later |
| Connector adapters | Capability-scoped marketplace/publishing operations and idempotency | In-process mock adapters; production network adapters later |

HTTP is used between Angular and FastAPI because it provides a testable, typed, shell-independent application boundary. Electron IPC is not used for business operations. The FastAPI port is loopback-only and protected as described in the security architecture.

The backend is one deployable modular monolith. Modules do not access another module’s tables directly; application services coordinate cross-module use cases. See [container-architecture.mmd](diagrams/container-architecture.mmd).
