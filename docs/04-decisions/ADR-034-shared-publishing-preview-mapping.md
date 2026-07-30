# ADR-034: Shared Publishing preview mapping

Status: Accepted

The API owns WordPress mapping and sanitization. Preview and execution call the same backend mapping
functions; Angular renders typed results and does not independently recreate or bypass sanitization.
