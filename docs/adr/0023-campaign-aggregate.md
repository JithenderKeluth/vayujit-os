# ADR 0023: Campaign aggregate

Campaign metadata, activities, dependencies, and schedule links are normalized owner-scoped
records. Publishing schedules and executions remain separate authoritative aggregates. This keeps
Campaign planning transactional without duplicating connector or worker state.
