# Sourcing Scenario Intelligence

Slice 8D is an owner-scoped, provider-independent decision-support layer. It consumes the
current Supplier Shortlist, Supplier Due Diligence, canonical Supplier Intelligence, and the
existing sourcing landed-cost calculator. It never contacts suppliers, sends RFQs, creates
purchase orders, reserves funds, or authorizes procurement.

## Numeric policy

- Money enters and leaves JSON as decimal strings and is calculated with 40-digit Decimal
  context, round-half-even, with persisted results at six decimal places.
- Quantities are positive whole units. Allocation quantities must exactly equal the context
  target quantity.
- Percentages have up to six decimal places. Sensitivity is bounded per dimension.
- Exact landed-cost mode requires each component to be explicit; a missing component is
  INSUFFICIENT_EVIDENCE, not zero.
- Commercial values entered in a scenario are assumptions and are retained in the immutable
  input snapshot. They do not update canonical supplier evidence.

## Workflow

Create a current supplier shortlist and due-diligence assessment, then open
/intelligence/sourcing-scenarios. Create a context from the exact shortlist version, define
one or more supplier allocations, and enter evidenced assumptions. Every calculation creates
an immutable version. Relative scoring is deterministic, versioned, and explained against the
exact comparison set.

The Generate evidenced baselines action derives single-supplier candidates and, when supplied,
one diversified allocation from the current shortlist, due-diligence state, canonical supplier
facts, and explicit cost assumptions. It persists only evidence-complete feasible candidates.
The response labels relative lowest cost, lowest capital, fastest supply, lowest risk, maximum
resilience, and balanced results where the comparison supports them; it does not invent missing
supplier prices. The generation request and each candidate have idempotency keys, and a partial
batch may be retried with the same key. A changed authoritative input is rejected on replay.

Approval is a human action on an exact current version. Missing evidence, critical due-diligence
blocks, stale lineage, MOQ infeasibility, breached capital limits, or breached margin targets
prevent approval. An approved version may create one internal planning handoff. That handoff
has external_dispatch=false.

## Local validation

Run focused unit and PostgreSQL integration suites:

    npm.cmd run test:intelligence:sourcing-scenarios
    npm.cmd run test:intelligence:sourcing-scenarios:integration

This slice is eligible only for local certification. It is not production, live, real-time, or
procurement certification.

## Certification status

The scenario domain, focused PostgreSQL replay/concurrency proof, Product Channel projection,
Operations, Calendar, System Doctor integrity counters, migration cycle, API unit suite,
Angular/Desktop checks, build, static checks, and production dependency audit have passed
locally at different checkpoints; a fresh full quality matrix is still required after the
8D.1 edits. The focused three-round transaction-race proof now covers context creation,
scenario generation, recalculation, recommendation, approval, research request, and internal
handoff. The three-supplier API journey and generation replay passed in disposable PostgreSQL.
The shared Operations Recovery endpoint supports audited, replay-safe stale-scenario
recalculation. Calculation retry, research-request retry, and projection repair remain explicitly
unsupported until an authoritative safe executor exists.

Local certification remains open. The broad API integration inventory has not been frozen or
fully executed. Owner isolation with two independent test owners, a measured local performance
baseline, complete storage ledger, crash/replay boundary proofs, integrity counter self-proof,
and the complete numeric/replay matrix remain unproven. This repository's
identity model currently enforces a single owner, so a true two-owner database race/isolation
test requires a dedicated compatible test fixture; random-ID and direct owner scoping are
covered, but that is not a substitute for the requested cross-owner proof.

The scenario layer does not perform procurement work, and no production/live certification is
claimed while these gates are open.
