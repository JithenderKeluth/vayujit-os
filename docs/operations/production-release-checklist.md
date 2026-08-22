# Production release checklist

Required sign-offs: security, encryption-key rotation, backup/restore, migration, database, media storage, monitoring, provider enablement, Ads spend, desktop signing, rollback, and compliance/privacy review.

Release gates: clean diff; no secrets; production configuration validation; security matrix; API/web/desktop tests; migration verification; backup drill; readiness health; and explicit approval for each live provider. Real Ads spend remains disabled until a separate signed approval.