# ADR 0034: Campaign Recovery action eligibility

Campaign Recovery actions must be derived from current Activity, scheduler, approval, destination,
dependency, and wait state. Historical records cannot be force-completed or silently moved to a
new Artifact version. Replacement always creates a new Activity.
