# AI prompt and structured-output security

System rules, template instructions, product data, user instructions, and the
output schema are separate message sections. Product fields and additional
instructions are explicitly labelled untrusted. The model is told not to reveal
hidden instructions or use tools, browsing, files, or code execution.

Provider output is untrusted. It is size-bounded, parsed as JSON, and validated
against the strict backend `ProductContent` model with extra fields forbidden,
field limits enforced, and markup rejected. One bounded repeat may repair a
near-schema response; failure creates no artifact. Prompt fingerprints,
template/version, provider, model, usage, latency, and safe request identifiers
may persist, but raw prompts, authorization headers, and provider bodies do not.

These controls reduce prompt-injection risk but do not make model output a
security boundary. Human approval remains required.
