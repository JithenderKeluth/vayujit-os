# ADR 0032: Missed-activity resolution persistence

Resume decisions are append-only normalized resolution records. Original Activities and execution
times remain unchanged. One-catch-up creates a new Activity identity using the exact original
Artifact version; skipping is limited to optional Activities.
