# ADR 0043: Normalize marketplace listings

Status: Accepted

Listings, attributes, variants, prices, inventory, and drift are normalized in a
dedicated commerce domain. Marketplace-specific fields do not leak into the
Product table, while raw remote state is retained only as safe diagnostics.

