# Marketplace activation checklist

- [ ] Amazon India and/or Flipkart seller account ownership is verified by the
      business owner outside this local milestone.
- [ ] Provider contract, scopes, read permissions, token storage, and expiry
      handling are approved.
- [ ] Account environment and transport mode are truthful (`SYNTHETIC`,
      `SANDBOX`, or `LIVE_READ_ONLY`).
- [ ] Read-only import and reconciliation are tested with a provider-approved
      credential. Live writes remain disabled.
- [ ] Internal SKU to marketplace SKU/listing mapping has no duplicates or
      invented ASIN/FSN/remote IDs.
- [ ] Unmapped products, stale imports, and reconciliation exceptions are
      resolved or explicitly accepted by a HUMAN.
- [ ] External-write authorization is separate, single-use, auditable, and
      emergency-stop aware. No publication is performed by PR-SOS-09.
