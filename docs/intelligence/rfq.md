# RFQ workflow

RFQs pin a requirement version and selected Supplier context. Approval is explicit; dispatch records only a manual state.

## Slice 4 closure contract

The sourcing boundary is local and deterministic. RFQ revisions append immutable versions and a dispatched RFQ cannot be rewritten. Shipping mode is bounded to AIR, SEA, ROAD, RAIL, COURIER, LOCAL, or UNKNOWN; supported Incoterms are EXW, FCA, FOB, CFR, CIF, DAP, and DDP, and every presentation carries **VERIFY INCOTERM RESPONSIBILITIES BEFORE ORDER**.

Logistics, duty/tax, and FX values are persisted as explicit versioned assumptions with classification and source/reference metadata. Live freight, FX, customs, supplier contact, purchasing, payments, document parsing, and autonomous ordering remain disabled. Currency conversion is labelled **ESTIMATED_CONVERSION** only when a valid non-expired manual FX assumption exists; otherwise the result is **NOT DIRECTLY COMPARABLE**.

Landed cost exposes supplier price, tooling, branding, packaging, inspection, freight, insurance, duty, tax, brokerage, local transport, warehouse inbound, FX/payment fee, and other components with classification, evidence and confidence. Capital, cash-timeline, sensitivity, scenario, scoring, critic, concentration, rules, and human decision projections are deterministic and historical records are append-only.

Product Channel and Calendar use bounded read projections. Unified sourcing history reuses sourcing records and recovery rows rather than creating a second audit system. Worker jobs are idempotent and terminal replay-safe; concurrent writes rely on owner-scoped identities and database uniqueness. Reports are available as JSON, Markdown, and escaped HTML. Untrusted RFQ, quote, sample, inspection, assumption, decision, and report text is rendered as text.

## Final sourcing certification evidence

The local PostgreSQL evidence set covers durable crash-before/crash-after checkpoints, true concurrent RFQ/approval/quote/sample/cost/scenario/score/decision/recovery actions, sequential replay, exact 28-table storage inventory, bounded endpoint timing/query review, recovery taxonomy, Product Channel, Calendar, unified History, report JSON/Markdown/HTML, privacy/XSS redaction, and focused Angular UX. External supplier contact, live freight/FX/duty-tax, purchasing, payments, document parsing, AXE, viewport automation, and aggregate integration runtime remain disabled or not configured by design.
