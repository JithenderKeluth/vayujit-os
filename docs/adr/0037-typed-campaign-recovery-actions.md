# ADR 0037: Typed Campaign Recovery actions

Recovery exposes a closed action allowlist derived from current Activity state. Unsafe actions are
suppressed and rejected server-side. Force-success and historical Artifact mutation are prohibited.
