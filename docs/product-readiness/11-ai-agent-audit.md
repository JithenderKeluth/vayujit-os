# AI and agent audit

Business Agent is durable, owner-scoped, bounded and approval-gated. It records goals, plans, runs, checkpoints, attempts and evidence projections. Deterministic/local providers and mock AI modes are explicit fallbacks.

The trust contract must remain strict:

- OBSERVED facts come from source evidence;
- DERIVED values come from deterministic calculations;
- AI interpretation is labeled and cannot invent price, sales, supplier, review, freight or duty facts;
- HUMAN DECISION is separate from automated research;
- UNKNOWN, stale, contradictory and insufficient evidence remain visible.

The live run exposed a real correctness gap in natural-language budget parsing, not an AI authority to silently infer capital.
