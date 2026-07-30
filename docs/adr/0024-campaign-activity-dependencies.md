# ADR 0024: Campaign activity dependencies

Dependencies are bounded directed edges with four typed semantics. Deterministic graph traversal
rejects cycles before persistence. Executable expressions and cross-Campaign references are
forbidden.
