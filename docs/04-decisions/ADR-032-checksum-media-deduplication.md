# ADR-032: Checksum media deduplication

Status: Accepted

SHA-256 is unique per owner. Duplicate uploads reuse metadata and bytes while allowing future
business associations. WordPress mappings remain site-specific and are verified before reuse.
