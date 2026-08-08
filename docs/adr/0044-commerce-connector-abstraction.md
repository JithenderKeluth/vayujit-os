# ADR 0044: Separate commerce connectors from publishing connectors

Status: Accepted

Commerce connectors expose account, catalog, listing, inventory, order, fee, and
settlement operations. They do not reuse generic content publishing execution
tables for commerce state. A deterministic fake connector is the first adapter.

