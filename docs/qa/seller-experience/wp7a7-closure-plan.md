# WP7A-7 — seven-entry closure plan

Execution started 4 November 2026. Original scope: 48 entries, 41 inherited closed,
seven PARTIAL. Earlier reports and recovery evidence remain historical and unchanged.
No completion is inferred from this plan.

## Recorded HUMAN decisions

The owner explicitly approved the temporary pause of only the normal development
API/frontend for this package, with restoration afterward. PostgreSQL, permanent
and golden databases, and backup resources are not included. The process recovery
record is `tmp/qa-wp7a7/app-window.json`, separate from WP7A-6.

L-17 original acceptance, preserved verbatim:

> Local fake content/image creative preview, missing/expired/disabled authorization, stale references and HUMAN confirmation; never remote execution.

The owner explicitly answered **“Approve this explicit scope clarification”** to:
offline certification covers authorization states represented by the current
contract; provider token expiry remains explicitly UNVERIFIED where no
authoritative expiry contract exists. Content/image identity, HUMAN confirmation,
stale/recovery and no-spend checks remain mandatory. This authorizes no new expiry
model, real credentials, provider calls, or live certification. Approval is a scope
decision, not evidence that L-17 passed.

## Bounded execution order

| Original ID | Work | Required evidence |
|---|---|---|
| R-3feda36d | Existing image Social approval affordance and exact review | HUMAN, provenance, stale/replay/recovery, no publication |
| R-55e822d5 | Marketplace overview state tests | Configured versus live, absent/invalid/revoked/expired represented states, default deny |
| R-551d2f8c | Flipkart local preparation and authorization tests | True unpublished draft, prerequisites, exact review, expiry/revocation/stale/replay |
| R-db243c36 | Meesho local price preparation correction | Existing pricing policy, durable draft, manual boundaries, no dispatch |
| R-d6a495d5 | Amazon local preparation correction | Existing listing/variant/price/media authorities, durable unpublished preparation, exact authorization |
| L-16 | Campaign version/dependency tests | Exact artifacts, changed dependency, stale review, replay/recovery, no release |
| L-17 | Ads local creative and authorization tests | Approved clarification plus all remaining local assertions, no spend |

First reproduce bounded defects, then make minimal authority-preserving changes.
Use sequential frozen-source backend runs and a frozen production browser build;
do not infer test precedence from file modification times. Use installed Chrome
and Edge at desktop 1440 and mobile 390. Preserve negative assertions and axe rules.

## Safety and gate

Read-only attestation matched dedicated instance
`389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`, container
`a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23`,
loopback `127.0.0.1:55432`, non-superuser `vayujit_qa_admin`.
Only harness-created `vayujit_qa<16hex>_test` databases with signed lifecycle,
marker/token/OID/role verification may be used or cleaned up. A cleanup failure
stops execution; no previous exact recovery approval is transferable.

Keep WP7A INCOMPLETE until every required assertion has direct evidence and cleanup
and regressions pass. No WP7B/C/8, permanent/golden writes, live provider actions,
branches, commits or pushes. Carry forward PostgreSQL timestamp drift, historical
Ads 502, manual accessibility, financial-history/reconciliation, typing/lint debt,
and parked PC-first certification without claiming resolution.
