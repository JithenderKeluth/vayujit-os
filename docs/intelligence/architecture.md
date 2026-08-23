# Intelligence architecture

VAYUJIT Intelligence is a bounded context for Product Research and Supplier Intelligence. The local Slice 1 pipeline is:

`Source -> Evidence -> Claim -> Rule evaluation -> Score -> Recommendation -> Human review -> Approved opportunity`

The context owns research projects, durable research runs, sources, immutable evidence, claims, deterministic rule configuration/evaluations, opportunities, and review history. It references the existing owner identity and audit infrastructure but does not manipulate Product ORM records.

External research is disabled by default. The current execution endpoint is a local foundation only and does not call IndiaMART, Alibaba, search engines, or unrestricted web fetches.
