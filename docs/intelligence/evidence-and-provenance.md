# Evidence and provenance

Every evidence row belongs to an owner and source, may reference a research run, stores observation/retrieval timestamps, a content hash, normalized value, bounded excerpt, trust classification, verification state, freshness state, and correlation ID.

Evidence is append-oriented. A changed observation is represented by a new row with `previous_evidence_id`; the earlier row remains available. Claims link to one or more evidence IDs. Model output is interpretation and is never promoted to evidence automatically.

External content is classified as `untrusted_external_data`. URLs are validated before persistence and only `http`/`https` URLs without embedded credentials, private hosts, loopback, link-local, reserved, metadata, or non-standard ports are accepted.
