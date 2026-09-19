# Business Agent orchestration (9G)

The Business Agent turns an owner-authored business goal into a structured,
versioned plan and a bounded, durable local run. It reuses the existing 9A–9F
product-opportunity, demand, competition, commercial, supplier, scoring, and
decision-brief boundaries through a provider-neutral capability registry.

Runs are owner-scoped and idempotent. Every capability step records an attempt,
checkpoint, and tool invocation with hashed inputs/outputs. Budgets bound steps,
provider calls, elapsed time, and evidence-gap loops. Prompt-injection-like text
in goal input is treated as untrusted data and never becomes an instruction.

The run produces a reviewable decision brief and remains waiting for explicit
owner approval. No external supplier contact, RFQ, purchase, payment, ad spend,
publication, inventory mutation, or other external write is available to the
agent. Approval and rejection are auditable and recovery is limited to safe,
owner-scoped retry/cancel controls.

Local route: `/intelligence/business-agent`

API prefix: `/api/v1/intelligence/business-agent`
