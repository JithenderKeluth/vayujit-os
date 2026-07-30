# ADR 0041: Two-worker Campaign acceptance harness

The final concurrency scenario requires two workers with independent sessions, injected time,
lease expiry, stale recovery, and fake connector state. It remains pending until implemented as one
coherent guarded test; unit simulations cannot substitute for it.
