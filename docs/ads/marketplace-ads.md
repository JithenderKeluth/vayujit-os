# Marketplace Ads (local deterministic slice)

VAYUJIT OS exposes normalized Marketplace Ads operations through the existing Ads Core. The current slice is intentionally local and deterministic: it never calls Amazon, Flipkart, or Meesho networks and never requires marketplace credentials.

## Supported boundary

- **Amazon Ads**: fake-certified adapter with Sponsored Products, Sponsored Brands, and Display capability metadata. Campaigns require an owner-scoped active listing and exact listing version. Keyword targeting, negative keywords, product/category targeting, INR/USD budgets, and deterministic metrics/conversions are modeled.
- **Flipkart Ads**: fake-certified adapter with product/display campaigns, product/category/audience targeting, and listing-version lineage.
- **Meesho Ads**: not supported in this slice. The capabilities endpoint returns an explicit unsupported reason; no fake Meesho campaign path is exposed.

## Flow

1. Create and validate an Ads account from **Ads → Accounts**.
2. Create an active marketplace listing through `POST /api/v1/ads/marketplace/listings`, tied to the owner, account, and Product. Each listing version is immutable.
3. Run readiness and preview with `POST /api/v1/ads/marketplace/campaigns/readiness` and `/preview`.
4. Confirm only the exact preview with `/campaigns/confirm`. This creates a durable local job; it does not spend money or contact a marketplace.
5. Run the queued job using the existing Ads worker route (`POST /api/v1/ads/jobs/{job_id}/run`). Groups, approved creatives, and ads use the same durable queue.
6. Import deterministic metrics, record conversions, inspect analytics, and reconcile the campaign. Listing and Product lineage remain in every campaign response.

## API surface

The normalized route group is `/api/v1/ads/marketplace`. It includes capabilities/providers, listing CRUD, readiness/preview/confirm, campaign detail/history, product-channel comparison, metrics/conversions/analytics, reconciliation, and deterministic failure simulation. All mutation routes require the authenticated owner and the exact local Origin.

Use the focused acceptance suite with:

```powershell
npm.cmd run test:ads:marketplace
```

The existing Ads Core, optimization, worker, security, and storage-integrity suites remain the source of truth for shared behavior.

## Slice 3 certification evidence

The dedicated closure suite is `apps/api/tests/test_ads_marketplace_closure.py` and runs with `npm.cmd run test:ads:marketplace:closure`. It covers Amazon crash-before and crash-after lease recovery, deterministic ambiguous-result reconciliation, Retry-After throttling, target validation, exact listing/creative replacement, Product Channel, Calendar, analytics, storage/privacy checks, and Flipkart full durable execution/version safety. The shared Ads suites provide the unified Recovery, optimization, security matrix, worker, lineage, and metric-safety evidence.

Amazon and Flipkart mutations are fake-provider only. A remote checkpoint is persisted before local finalization; a lost response is reconciled by deterministic identity instead of blind replay. Retryable throttling is bounded and restart-safe. Listings and creatives are immutable versions: v1 remains historical, v2 requires explicit preview/confirmation, and stale fingerprints are rejected. Amazon supports product, category, and exact listing targets; Flipkart exposes only its modeled product, listing, category, and audience targets. Amazon video and Meesho Ads remain explicitly unsupported.

Product Channel, Campaign, Calendar, analytics, history, and Recovery projections are owner-scoped and provider-isolated. Metrics are synthetic and currency-safe: incompatible monetary values do not receive an implicit FX conversion, and profitability is unavailable when required cost inputs are absent. Connector payloads and error responses exclude credentials, tokens, cookies, buyer PII, raw Orders, prompts, DSNs, local paths, and unrelated Products. Automated Axe and viewport harnesses are not configured; keyboard-native controls and static accessibility/responsive review are the local evidence. No live Amazon, Flipkart, or Meesho API is validated.
