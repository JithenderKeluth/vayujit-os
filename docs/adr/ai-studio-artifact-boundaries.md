# ADR: AI Studio artifact boundaries

AI output is persisted as independent GeneratedArtifact versions per product, channel, and content type. Product and Brand records remain the source of truth; prompts and provider output are never treated as trusted instructions.
