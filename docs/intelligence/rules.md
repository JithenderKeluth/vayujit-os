# Intelligence rules

Rules are separate from Ads rules. Categories are owner-scoped and versioned. The initial category registry is Physical, Logistics, Safety, Regulatory, Economics, Market, Competition, Supplier, and Risk.

Each rule stores a logical key, immutable version, priority, severity, hard-block flag, operator, conditions, parameters, and reason template. Updating a logical rule creates a new version and disables the prior version. Evaluations persist the exact rule ID and version used.

Slice 1 supports simple deterministic operators (`exists`, `gte`, `lte`, and `in`). Real market signals and supplier data are intentionally not fabricated.
