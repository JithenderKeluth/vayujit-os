# Competitor Discovery and Identity Resolution (Slice 10B)

This slice adds deterministic, owner-scoped competitor discovery on top of the Slice 10A
context, entity, product, observation, source, and evidence records.

## Safety boundary

DISABLED rejects execution. LOCAL_FIXTURE is deterministic and intended for local
certification. LIVE_READ_ONLY is deliberately fail-closed until an approved adapter is
configured. The implementation performs no contact, order, purchase, login, CAPTCHA, or
external mutation work.

## Resolution

Candidate text is normalized with Unicode NFKC, case folding, punctuation separation, and
whitespace collapse. Matching is deterministic:

1. existing competitor identifier (authoritative)
2. canonical product identity
3. normalized title plus compatible structured signals
4. weak candidate when evidence is incomplete

Conflicting brand/category signals produce AMBIGUOUS; no automatic confirmation is
performed for weak candidates. Every candidate records supporting, conflicting, and missing
signals, match level, score, rule version, source, evidence, and freshness.

## Durable replay

Requests are owner-scoped and idempotent. Executions persist immutable versioned snapshots
with a previous-snapshot pointer. Replaying a completed request returns the existing snapshot;
refresh creates a new snapshot without rewriting prior snapshots. Candidates are bounded by
maximum_candidates and deduplicated by source mode and source identifier.

## API

The authenticated API is under /api/v1/intelligence/competitors/discovery:

- create/list/get requests
- execute and refresh
- list/get candidates and explanations
- confirm, reject, or mark ambiguous
- list/get snapshots
- discovery system doctor

The Angular competitor workspace exposes local discovery and candidate review controls.
