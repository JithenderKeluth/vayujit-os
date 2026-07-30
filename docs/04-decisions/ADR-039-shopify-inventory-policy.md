# ADR-039: Conservative Shopify inventory

Status: Accepted.

Inventory quantity writes are disabled. Publishing content must never change stock as a side effect.
Continuous inventory synchronization, orders, and fulfillment are outside this connector.
