# Live-provider enablement

Live execution is disabled by default. Enable one provider at a time:

1. Configure encrypted credentials and a sandbox/test account.
2. Validate capability, timeout, quota, retry, idempotency, and reconciliation contracts.
3. Run read-only discovery and a dry run with the live switch false.
4. Obtain owner approval and enable only the domain switch (`VAYUJIT_LIVE_AI_ENABLED`, Social, Marketplace, or Ads).
5. Perform one bounded mutation, verify the remote identity, audit event, and reconciliation state.
6. Inject a failure, exercise recovery, and confirm rollback/disable behavior.
7. Keep Ads spend disabled until account, owner, currency, daily, campaign, and plan caps are independently confirmed.

No live provider is enabled by this branch.