# QA Phase 4 exploratory architecture

Extends, not replaces, Phases 1–3B. Read `architecture.md`, `phase-3b-validation.md`,
the coverage matrix, immutable reviewed findings, Phase 3B resolution ledger and
active backlog before this work. Whole-application certification stays INCOMPLETE.

## Executable pipeline

`npm.cmd run qa:phase4` uses `qa/run.mjs --phase4`:

1. Current TypeScript/Python source inventory (`audit({write:false})` preserves
   earlier coverage and inventory reports). Save separate Phase 4 source inventory.
2. Production Angular build, then one fresh marker-protected PostgreSQL installation
   per desktop/mobile project. Existing Phase 3 fixture/supervisor and 18 persisted
   API regressions create legitimate synthetic Product, selected opportunity,
   supplier/DD/economics, stock/order/financial/signal contexts.
3. Phase 4 reverse proxy/browser safety policy reuses only bounded preparation
   authorities. Sandbox-account payload guards, LOCAL_FIXTURE supplier restriction,
   canonical kill switches, server egress guard and isolated Chrome context remain.
   Restart/worker/backup/provider execution is not permitted by Phase 4.
4. `qa/phase4-surface.mjs` maps exact source declarations to real fixture contexts.
   Unavailable parameter IDs are **REQUIRES_UNAVAILABLE_CANONICAL_CONTEXT**, not
   guessed UUIDs, claimed populated pages, or proof a production feature is missing.
5. `qa/tests/phase4.spec.mjs` groups explicit read-only visits by actual route area.
   `qa/explore.mjs` captures controls, forms, captions/tables, hidden/conditional
   controls present in DOM, empty/loading/error/status wording, HTTP outcomes,
   console/page errors, screenshots and full-document axe scans.
6. Separate deterministic seller tasks exercise supported login/history/logout,
   catalog edit/cancel/save/reload, stock filter/mapping-cancel/injected error/retry,
   and exact caption/financial-node focus/scroll/viewport investigation.
7. Report generation joins actual source/DOM/API evidence into route/control and
   12-journey matrices, preserves prior open findings, and requires exact expected
   scenario IDs, successful API regressions and normal disposable cleanup to classify
   a bounded run successful. A bounded successful run is never whole-app PASS.

## Safety of exploration

Discovery does not click discovered controls. Explicit task code is reviewed; the
reusable action registry rejects unknown actions and wrong routes before a click.
GET visits may trigger application initialization requests; denied requests and
unexpected API failures are captured rather than bypassed. No production files or
authorities are changed. No live providers, credentials, remote browser navigation,
publishing, contact, payment, procurement, Docker management or backup activity.

No input values, cookies, headers or request bodies are included in surface/network
inventories. Screenshots/traces still contain synthetic session data and remain
local under ignored `tmp/qa-agent`; never publish automatically. Queries are omitted
from network summaries; explicit scenario evidence retains only synthetic context.

## Coverage semantics

- **Source declaration** is not a runtime page or feature completion claim.
- **Visited** means actual route and DOM evidence, not every control/state tested.
- **Discovered control** includes repeated navigation; unique fingerprints and
  visible occurrences are reported separately from explicit action occurrences.
- Hidden DOM controls are recorded; unopened dialogs/conditional states absent from
  the DOM are **not discovered**, not inferred unsupported.
- Static unmatched backend endpoints are candidates for human review, not confirmed
  missing UI. Registered OpenAPI is separately captured for each fixture.
- Axe-confirmed violations, suspected API/assertion defects, recommendations,
  historical missing workflows and untested contexts are separate categories.
- Wider-viewport contrast success does not clear a mobile clipped caption. Exact
  four historical settlement headers are selected semantically, not discarded when
  a later full-document scan produces no incomplete targets.

Existing metadata fixtures do not certify migrations or full production readiness.
Electron, assistive technology, live credentials and real marketplace certification
remain untested. Earlier reports/hashes and open findings are not silently closed.
