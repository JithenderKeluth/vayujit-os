# ADR 0027: Campaign scheduler integration

Campaign publication delegates to the PostgreSQL Publishing scheduler through stable normalized
links. The scheduler remains responsible for occurrence identities, job materialization, worker
leases, retries, connector calls, and reconciliation.
