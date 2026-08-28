# External Research UX

Slice 6A.4 provides the user-facing External Research workspace at `/intelligence/external`. It reuses the Intelligence service and existing owner-scoped external APIs; it does not create a separate Angular application or enable live providers.

## Navigation and status

The workspace links Overview, Providers, Source Policy, Searches, Fetches, Evidence, Contradictions, Changes, Alerts, History, and Recovery. Runtime banners explicitly identify LOCAL FIXTURE, LIVE SEARCH ? NOT VALIDATED, LIVE FETCH ? NOT VALIDATED, EXTERNAL AI DISABLED, and UNRESTRICTED SCRAPING DISABLED. Provider enablement remains deployment-controlled.

## Safety and evidence

Search snippets are labelled DISCOVERY ONLY. Fetches and evidence show verification and freshness labels, including VERIFIED, SUPPORTED, STALE, EXPIRED, CONFLICTING, and AI_DISABLED. External URLs are restricted to HTTP(S), open with `noopener noreferrer`, and blocked URLs are not links. External content is rendered as escaped plain text; raw HTML and private provider payloads are never inserted.

## Policy, operations, and recovery

Source Policy exposes mode, allowlist readiness, domain states, robots/terms classification, and server-enforced budgets. Product Channel and Calendar remain informational/read-only projections. Recovery displays only server-advertised actions and keeps consequential operations confirmation-bound; Operations remains authoritative for workers, queues, provider state, kill switches, integrity, and performance.

## Accessibility and responsive behavior

The workspace uses semantic `main`, `nav`, headings, labelled tables with captions and scoped headers, text status labels, `role=alert` for failures, keyboard-reachable native controls, and visible focus outlines. Tables scroll within bounded containers and grids collapse at narrow widths (390px), while the same layout remains usable at 768px and 1280px+.

## Local/live boundary

Local deterministic fixtures are testable without credentials. Live search and approved live fetch remain NOT VALIDATED until deployment configuration supplies credentials and approved domains. No external AI, unrestricted scraping, browser automation, supplier contact, purchasing, or payment capability is exposed.
