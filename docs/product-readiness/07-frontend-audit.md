# Frontend audit

Angular routing is lazy-loaded and protected by auth guards, with broad route coverage in `apps/web/src/app/app.routes.ts`. The application has shared navigation/design patterns and an Electron host.

Observed risks to close incrementally:

- broad route/component surface creates duplicated loading/error/status mapping risk;
- API-backed pages need consistent retry and partial-success handling;
- technical identifiers appear in primary forms on some advanced workflows;
- long evidence pages require responsive, keyboard and screen-reader checks at milestone level;
- live/local/provider state must be derived from server truth rather than stale component state.

No evidence supports a frontend rewrite. Use route-specific vertical fixes and shared components.
