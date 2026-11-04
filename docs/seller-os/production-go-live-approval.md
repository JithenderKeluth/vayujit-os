# Production go-live approval record

This is a HUMAN approval form, not an automatic readiness decision. Completing
it does not register a marketplace account or authorize an external write until
the named owner signs the exact operation.

## Installation identity

- Installation/domain: `____________________________________________`
- Owner/admin identity: `____________________________________________`
- Approved operator(s) and SSH key owners: `__________________________`
- Database model: `one private PostgreSQL database; ck_users_single_owner`
- Planned activation date/window and timezone: `_______________________`

## Required evidence checklist

| Gate | Evidence/reference | State | Owner initials/date |
| --- | --- | --- | --- |
| Host sizing and patching | Resource baseline, OS/kernel, Docker versions | NOT REVIEWED | |
| Firewall and SSH | Rule export, operator access, break-glass test | NOT REVIEWED | |
| Domain and HTTPS | Certificate chain, renewal owner, HTTPS checks | NOT REVIEWED | |
| Database privacy | Private endpoint, dedicated role, encryption | NOT REVIEWED | |
| Durable media | Private bucket, access policy, restore check | NOT REVIEWED | |
| Secret manager | Secret references, custody, rotation schedule | NOT REVIEWED | |
| Backup | Encrypted artifact, checksum, off-server copy | NOT REVIEWED | |
| Restore | Disposable restore witness, RPO/RTO observation | NOT REVIEWED | |
| Owner/business | Truthful legal/contact/tax information | NOT REVIEWED | |
| Product/catalog | Product, SKU, image, category and evidence | NOT REVIEWED | |
| Inventory | Physical stock evidence and location | NOT REVIEWED | |
| Financials | INR prices, acquisition cost, fee assumptions | NOT REVIEWED | |
| Supplier evidence | Provenance, freshness, contradictions, unknowns | NOT REVIEWED | |
| Amazon India | Registration/API/read-only status | NOT APPLICABLE or BLOCKED | |
| Flipkart | Registration/API/read-only status | NOT APPLICABLE or BLOCKED | |
| HUMAN readiness review | Launch-readiness and Action Center review | NOT REVIEWED | |
| External mutation stop | All provider/write switches remain false | REQUIRED PASS | |

## Explicit decisions

The owner must write a decision, not leave a checkbox implied:

1. **Deploy the single-seller installation to the approved private host:**
   `APPROVE / HOLD` — reason: `______________________________`
2. **Keep VAYUJIT read-only and marketplace mutations disabled after deploy:**
   `APPROVE / HOLD` — reason: `______________________________`
3. **Authorize Amazon India registration/read-only certification:**
   `APPROVE / HOLD / NOT PLANNED` — account status: `__________________`
4. **Authorize Flipkart registration/read-only certification:**
   `APPROVE / HOLD / NOT PLANNED` — account status: `__________________`
5. **Authorize a later external write/publication operation:**
   `DENY / DEFER / APPROVE A NAMED SINGLE-USE OPERATION`
   — artifact, operation, expiry, and reason: `__________________________`

No approval may substitute for missing evidence, a disabled safety control, a
provider's registration decision, or a failed backup/restore witness.

## Required owner inputs

Provide: legal business identity, owner/admin contact, GST/tax and settlement
status, INR accounting policy, product/SKU/category/image/cost/stock evidence,
supplier evidence, shipping/returns assumptions, host/domain choice,
PostgreSQL/storage/backup choice, secret custody and rotation owners, TLS
renewal owner, RPO/RTO, SSH operators, monitoring/on-call contact, marketplace
registration/API status, and any provider approval references. Secrets remain
in the secret manager and are not copied into this record.

## Sign-off

- Owner name/signature: `____________________________________________`
- Date/time/timezone: `_______________________________________________`
- Technical operator: `_______________________________________________`
- Security/backup witness: `__________________________________________`
- Recorded decision ID/correlation ID: `_______________________________`

Until this record is complete and the named HUMAN decisions are approved,
deployment may remain prepared but VAYUJIT must stay fail-closed and
read-only. No provider call, listing publication, procurement, payment, or
marketplace write is authorized by this document alone.

