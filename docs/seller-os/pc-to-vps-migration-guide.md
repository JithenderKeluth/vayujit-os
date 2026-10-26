# PC-to-VPS migration guide

This guide describes a future owner-approved move from the private PC profile
to the provider-neutral Linux/VPS topology. It is not an automated migration,
and it does not authorize a host purchase, public deployment, marketplace API
call, or external write.

## Before scheduling a move

- [ ] Owner chooses a named VPS operator, region, domain, and recovery contact.
- [ ] Owner approves managed versus private self-hosted PostgreSQL, storage,
  secret custody, maintenance window, RPO/RTO, and access list.
- [ ] A fresh PC DB/media encrypted backup has passed verification, with the
  private age identity available through its separate recovery custody.
- [ ] The selected target has a separately created private DB/role, TLS,
  secret manager, durable media, encrypted off-server backup, firewall, and
  monitoring; ports 5432/API/worker/web are not public.
- [ ] An isolated disposable target and reviewed data-transfer procedure are
  available. Never restore a PC dump directly over production during rehearsal.
- [ ] PC and VPS application/migration versions are recorded and compatible.

## Controlled migration outline

1. Freeze business edits, inventory changes, credential changes, and scheduled
   jobs on the PC. Stop the PC app after a final verified backup.
2. Transfer only encrypted backup artifacts through an owner-approved secure
   channel. Do not transfer the age private key with them; provision/re-wrap
   recovery access under the target's approved secret custody.
3. Restore database and media to a disposable target first. Verify migration
   head, `ck_users_single_owner`, one-owner records, representative counts,
   media manifest checksums, authentication, readiness, and HUMAN-only
   approval boundaries.
4. Validate the production configuration with all external actions disabled.
   Rotate session, DB, and application encryption secrets according to a
   reviewed re-encryption/credential recovery plan; do not copy PC secrets
   blindly or lose decryption keys for stored credentials.
5. Perform authenticated browser and backup/restore checks over HTTPS, then
   obtain the owner’s written cutover approval. Until it is signed, the PC
   remains the authoritative installation and the VPS remains non-live.
6. Cut DNS only after TLS, access restrictions, monitoring, operator
   responsibility, and rollback are verified. Keep one writer at a time; never
   run PC and VPS as concurrent writable business systems.
7. Observe agreed readiness and backup windows. If rollback is required, stop
   the VPS writer, preserve its state, and follow a reviewed reconciliation
   plan; never blindly replay an older PC backup over newer records.
8. Retire the PC business volume only after the owner has accepted the target,
   verified backup/recovery, and approved retention/destruction.

## Items requiring separate HUMAN decisions

Domain/DNS control; VPS/managed DB/storage provider; region and retention;
privacy/security review; operator identities; credential rekeying; any
marketplace account/API access; live read-only tests; external-write approval;
cutover/rollback window; and PC data retention/decommission. Provider-specific
Amazon/Flipkart requirements remain `UNVERIFIED — HUMAN FOLLOW-UP REQUIRED`
until official documentation and the seller account's actual approvals are
checked.
