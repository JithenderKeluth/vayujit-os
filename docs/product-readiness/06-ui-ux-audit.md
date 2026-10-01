# UI/UX audit

## Strengths

Guided journey cards, evidence labels, local/live mode language, empty/error states, recovery links, and progressive sections are present across the newer surfaces. Screenshots show a coherent visual language and explicit human-review boundaries.

## High-impact issues

- First-use surfaces still expose technical prerequisites in places (UUID/context IDs, provider modes, raw evidence/lineage panels). These belong under Advanced; normal seller actions should use names and selections.
- A blocked provider can present a technically correct error but not always a concrete next action such as “configure approved source” or “use local preview”.
- Empty, blocked, unavailable, stale, and partial states need consistent wording and status semantics across intelligence and sourcing routes.
- Large information-dense pages can obscure the next business decision; prioritize decision, explanation, evidence, then lineage.

These are UX closure items, not justification for replacing the existing design system.
