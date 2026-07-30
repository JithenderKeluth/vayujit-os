# ADR 0031: Campaign terminal-state projection

Campaign terminal state is derived centrally from required and optional Activity projections.
Required dead-letter or failure produces failure, unresolved operational prerequisites produce
blocked, and optional terminal failures after required success produce partial completion.
