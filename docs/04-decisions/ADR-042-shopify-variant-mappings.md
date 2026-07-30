# ADR-042: Persist stable Shopify variant mappings

Status: Accepted

Persist destination, Product, stable local key, remote variant and inventory-item identifiers in a
normalized table. Updates match mappings rather than array positions. Remote-only variants are
preserved and surfaced as drift.
