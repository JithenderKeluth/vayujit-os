# Test coverage audit

The repository has focused unit, integration, API, provider, worker, certification, security and frontend coverage across the slices. The LIVE-1C.6 focused suite passed 14/14 with a test-only source-approval override; LIVE-1C.7 validated orchestration but not a live product artifact.

Current test-value gap: implementation tests can prove a row, endpoint or page without proving a seller-meaningful artifact. Milestone tests must assert meaningful product identity, evidence/provenance, comparison, human selection, supplier context, economics and decision output. Keep tests scoped by blast radius; certify globally only at milestones.
