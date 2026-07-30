# ADR-044: Assign collections after product creation

Status: Accepted

Selected collection GIDs are applied through predefined mutations and persisted as normalized
assignments. Independent remote removals become drift; they are not repaired without confirmation.
