# Supplier Verification

Verification states are `UNVERIFIED`, `SELF_REPORTED`, `PARTIALLY_VERIFIED`, `VERIFIED`, `HIGH_CONFIDENCE`, `SUSPENDED`, and `BLOCKED`. Recording a state never creates independent legal clearance.

Business registration, GST/tax, address, factory, inspection, reference, certificate, sample, and historical-performance evidence are stored as provenance references. Supplier contacts are business-person data and remain owner-scoped.

## Certification evidence

Verification state changes are allowlisted and evidence-gated for `VERIFIED` and `HIGH_CONFIDENCE`; owner-scoped evidence is required. Certification claims and verification observations are append-only and retain historical versions.
