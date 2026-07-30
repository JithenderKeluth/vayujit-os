# ADR 0025: Campaign readiness calculation

Readiness is calculated from authoritative Brand, Product, exact Artifact version, destination,
Campaign window, dependency, maintenance, and quota state. Persisted readiness is a projection and
is recalculated before scheduling.
