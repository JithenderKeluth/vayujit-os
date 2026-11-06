# WP7B-R3 — isolated synthetic session setup

Snapshot: 2026-11-05T04:19:18.152Z. Status: **AWAITING_HUMAN_OBSERVATION**. This is a session checkpoint, not final certification.

## Isolation

Fresh R3 authorization only. The existing signed guard attested container `a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23`, instance `389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`, endpoint `127.0.0.1:55432`, role `vayujit_qa_admin`. Naming: `vayujit_qa<16-hex>_test`. Exact owner/marker/token/OID and signed lifecycle remain authoritative. No FORCE fallback, business/golden target or alternative instance is authorized.

QA URL: **http://127.0.0.1:55226**. Database: `vayujit_qadd240c756c70f504_test`. Token: `dd240c756c70f504`. Runtime PID: 41892.

Normal API/frontend listener identities were captured before startup in the session receipt. No stop, restart, connection substitution, normal configuration change, Docker restart or port takeover was performed. The QA runtime allocates unused loopback ports and serves the existing production Angular build; the fixture server disables .env loading and denies outbound sockets/providers. The R1 runtime/policy is reused as an engine, not as old authorization; all new ownership receipts say R3.

**Process-preservation qualification:** no explicit R3 stop/restart command was issued, but the normal API WatchFiles auto-reloader was observed reacting to the new `qa/wp7br3_audit.py` file. Therefore “no normal-process interruption” is NOT established. The owner separately said “I changed the app processes”; that accounts for some changes, not proof that all activity was owner-caused. No further Python edits or normal-process management will be performed. This is an unintended setup side effect, not a claimed application defect or authorization to pause/restart the app. No row-level business-data preservation claim is made for normal startup activity.

## Retained preparation failure

Attempt `6e9e32ae46d01290` reached migrated runtime readiness but fixture preparation failed with `WP3_FIXTURE_403_accounts` at `qa/wp7br3-session.mjs:102`: the synthetic Ads external account identifier lacked the existing `qa-wp7a2-` prefix. Only that fixture identifier was corrected; the guard was not changed. The failed receipt is retained as `tmp/qa-wp7br3/session-control-6e9e32ae46d01290.json`. Independent signed-instance query confirms its database absent and signed state DROPPED (`audit-6e9e32ae46d01290.json`). The current fresh attempt completed fixture preparation and reached the empty sign-in checkpoint.

The optional standalone audit helper initially failed closed on PowerShell's singleton-object JSON shape. A corrected in-memory read-only audit obtained the absence/preservation evidence; the helper itself is not claimed runtime-validated or recommended for execution. One inline diagnostic launch also failed argument quoting before execution; the corrected literal-argument invocation succeeded. Raw output, secrets and database URLs were not persisted.

## Fixtures and authentication

Existing canonical API/domain fixture mechanisms prepare an explicitly synthetic owner, goal/opportunity, catalog/inventory/financial scenarios, mock content artifact, sandbox Marketplace drafts, local unpublished Ads campaign/read-only recommendation, Social draft and future draft review checkpoint. These do not certify live evidence or provider authorization. The draft Campaign checkpoint is not a legitimately eligible reschedule fixture; C-10 remains unverified. No worker/publishing process is launched.

Passwords and storageState are not written to reports. The password-bearing setup occurs outside retained tracing. An empty sign-in page is provided for label/role speech; no login details need to be entered for the first check. Later authenticated navigation restores the synthetic cookie in process memory only.

## Routes

| Surface | Exact isolated route |
| --- | --- |
| login | http://127.0.0.1:55226/login |
| goals | http://127.0.0.1:55226/intelligence/business-agent |
| accounts | http://127.0.0.1:55226/marketplaces/accounts |
| meesho | http://127.0.0.1:55226/marketplaces/listings/677b6635-ccd2-4f7f-a5c0-c8c25b6b17d4/meesho |
| ads | http://127.0.0.1:55226/ads/recommendations |
| social | http://127.0.0.1:55226/social/posts/cb40399c-26a5-4800-9d94-190244129cfa |
| flipkart | http://127.0.0.1:55226/marketplaces/listings/62bdb510-9d0e-43b1-b3a4-009a6552045c/flipkart |
| finance | http://127.0.0.1:55226/marketplaces/financials |
| opportunity | http://127.0.0.1:55226/intelligence/product-opportunities/b0b7874b-b143-4afb-8c8f-0b804fd90fa2 |

## Bound and cleanup

Session expiry: **2026-11-05T04:48:54.540Z**. Only R3-owned browser/API/proxy processes may be closed. The launcher closes the owned browser, signals the existing runtime stop marker, and waits for signed marker-protected non-FORCE cleanup. Current cleanup: **PENDING_ACTIVE_BOUNDED_SESSION**. Independent post-cleanup database absence has **not yet been verified**. Do not read an active-session receipt as final cleanup PASS.

Launch command (only when no active R3 record/session exists):

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp7br3.ps1
```

The launcher deliberately refuses to overwrite an existing control receipt. Do not delete that receipt or bypass guards to restart. Review the previous session and cleanup first.
