# System Context

## Scope

The local owner uses the VAYUJIT OS desktop application on one Windows machine. Electron hosts the Angular UI and manages the FastAPI process. FastAPI owns application behavior and stores business data in PostgreSQL and assets in managed local storage.

The MVP calls deterministic mock AI and mock publishing adapters in-process. An Ollama-compatible local provider is the next AI adapter. A mock marketplace adapter proves the connector contract but is outside the primary publishing journey. Production marketplaces, publishers, and cloud AI providers are future external systems and are not contacted by the MVP.

## Trust Boundaries

- The Angular renderer is untrusted presentation code and receives no direct database, filesystem, secret, or process access.
- The loopback HTTP API is authenticated and remains the only UI-to-domain boundary.
- FastAPI is the authority for validation, authorization, state transitions, and audit.
- Adapters receive minimum scoped inputs through application interfaces.
- PostgreSQL, encrypted secrets, backups, and local assets remain on the owner’s machine.

See [system-context.mmd](diagrams/system-context.mmd).
