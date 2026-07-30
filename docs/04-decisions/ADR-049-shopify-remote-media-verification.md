# ADR-049: Verify remote Shopify media before reuse

Status: Accepted

A local mapping is insufficient evidence. Reuse requires matching destination, shop fingerprint,
checksum, remote Product, remote existence, accessibility, and ready status. Unknown evidence is
never treated as reusable.
