# Definition of done for future slices

A slice is complete only when it states:

- business objective and seller value;
- existing authority reused and files/modules changed;
- data/API/frontend/security/migration impact;
- unit, integration, UI, failure and regression tests;
- live-data or explicit configuration validation;
- observed/derived/AI/human/unknown provenance;
- empty, blocked, stale, partial and retry behavior;
- acceptance artifact a seller can understand;
- rollback and operational considerations;
- classification using the ladder: IMPLEMENTED → LOCALLY TESTED → LOCAL CERTIFIED → LIVE VALIDATED → LIVE CERTIFIED → PRODUCTION CERTIFIED.

Tests passing alone never closes a slice.
