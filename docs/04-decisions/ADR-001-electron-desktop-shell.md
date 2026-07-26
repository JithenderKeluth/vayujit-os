# ADR-001: Electron Desktop Shell

**Status:** Accepted

## Context
The Windows-first Angular application needs packaging, window security, backend lifecycle management, and limited OS integration.

## Decision
Use Electron with a sandboxed, context-isolated renderer, no renderer Node integration, and a narrow preload API. Electron starts/stops FastAPI; business calls use authenticated loopback HTTP.

## Alternatives Considered
Tauri (smaller footprint but a second systems-language toolchain); browser-only UI (weaker desktop lifecycle/packaging); native Windows UI (poor Angular fit).

## Consequences
Angular fits directly and desktop tooling is mature, at the cost of runtime size and a larger security surface.

## Risks
Renderer compromise, insecure IPC, and orphaned backend processes.

## Follow-up Actions
Pin Electron; define CSP/navigation/permission tests; document startup, shutdown, packaging, and update strategy.
