# Supplier Scoring

Supplier scores are deterministic and explainable. The default model evaluates Product Match, Commercial Competitiveness, MOQ Flexibility, Lead Time, Capability, Verification, Quality Evidence, Communication, Logistics, and Risk. Weights total 100 and each dimension stores score, weight, contribution, reason, and evidence.

Historical score evaluations are immutable by model version. Hard rules and warning signals override optimistic score interpretation. Currency is preserved; no exchange rate is invented. Converted values must be explicitly labeled `ESTIMATED_CONVERSION`.

## Certification evidence

Score evaluation concurrency is keyed by supplier and model version. Historical scores remain immutable, evidence lineage is retained, risk dimensions are explicit, and mixed currencies are marked non-comparable rather than numerically ranked.
