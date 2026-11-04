# Canonical WP7 coverage addendum — WP7A-4

Additive evidence only; original matrix/addenda and historical caveats remain unchanged. Source: wp7a3-required-coverage.json minus its already closed L-11. Gate: INCOMPLETE.

| Original ID | Route | Outcome | Exact remaining disposition |
|---|---|---|---|
| R-184826c3 | `/intelligence/trends/:contextId` | PARTIAL | Owned context/reload verified; populated observation/source analysis remains unverified. |
| R-8a5edab2 | `/` | PASS | VERIFIED_LOCAL_SCOPE |
| R-7e93fba0 | `/login` | PASS | VERIFIED_LOCAL_SCOPE |
| R-17b7d214 | `/ads/accounts/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-66842e70 | `/ads/campaigns/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-794214d7 | `/campaigns/:id/video/:activityId` | PARTIAL | Exact approved Video binding and reload verified; the activityId route renders an overview rather than an activity-specific detail. |
| R-ec41ffe0 | `/campaigns/:id/video` | PASS | VERIFIED_LOCAL_SCOPE |
| R-8522d9c2 | `/campaigns/:id/activities/new` | PASS | VERIFIED_LOCAL_SCOPE |
| R-f4ba2c21 | `/campaigns/:id/dependencies` | PASS | VERIFIED_LOCAL_SCOPE |
| R-e4940841 | `/campaigns/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-3feda36d | `/social/posts/:id` | PARTIAL | Canonical social draft and persisted identity checked; image/video-specific and stale-review permutations remain. |
| R-55e822d5 | `/marketplaces/overview` | PARTIAL | Overview and reload checked; full configured-channel snapshot requires remaining account fixtures. |
| R-551d2f8c | `/marketplaces/listings/:id/flipkart` | PARTIAL | Exact catalog-linked draft/default-deny reviewed; complete channel readiness/review authorization transitions remain. |
| R-db243c36 | `/marketplaces/listings/:id/meesho` | PARTIAL | Exact catalog-linked draft/default-deny reviewed; complete channel readiness/review authorization transitions remain. |
| R-d6a495d5 | `/marketplaces/listings/:id/amazon` | PARTIAL | Exact catalog-linked draft/default-deny reviewed; complete channel readiness/review authorization transitions remain. |
| R-8f16bd41 | `/ai/images/assets/:outputId` | PASS | VERIFIED_LOCAL_SCOPE |
| R-5e241b88 | `/ai/studio/artifacts/:id/compare` | PASS | VERIFIED_LOCAL_SCOPE |
| R-75d260b7 | `/ai/artifacts/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-2e8db403 | `/settings/publishing/connectors` | PASS | VERIFIED_LOCAL_SCOPE |
| R-756ae8b2 | `/publishing/destinations/shopify` | PASS | VERIFIED_LOCAL_SCOPE |
| R-af04ee8c | `/publishing/destinations/wordpress` | PASS | VERIFIED_LOCAL_SCOPE |
| R-730f1388 | `/media/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-a8d8b217 | `/publishing/destinations/:id/edit` | PASS | VERIFIED_LOCAL_SCOPE |
| R-9b0fb4bc | `/publishing/destinations/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-68adcdc8 | `/publishing/executions/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-2b4d90d2 | `/publishing/schedules/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-30072869 | `/publishing/jobs/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-e309647e | `/operations/workers/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-9dc8a702 | `/workflows/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-541d7261 | `/approvals/:id` | PASS | VERIFIED_LOCAL_SCOPE |
| R-eb4987ba | `/intelligence/supplier-portfolios/:portfolioId` | PASS | VERIFIED_LOCAL_SCOPE |
| R-8d64a30d | `/**` | PASS | VERIFIED_LOCAL_SCOPE |
| L-09 | `/ai/generate` | PASS | VERIFIED_LOCAL_SCOPE |
| L-10 | `/ai/studio` | PARTIAL | Completed snapshot retained; queued old-context work rejects as stale after a Product change. Provider retry/supersession permutations remain. |
| L-12 | `/ai/images` | PARTIAL | Image regeneration/reload/source approval retained; injected provider failure/recovery still requires exact child controls. |
| L-13 | `/ai/studio/bulk` | PARTIAL | Canonical cancellation/reload exercised; partial success/provider retry combinations remain. |
| L-14 | `/ai/images/bulk` | PASS | VERIFIED_LOCAL_SCOPE |
| L-15 | `/ai/studio/seo` | PARTIAL | Keyword/tag creation and tag reload executed; analysis history/reanalysis/context permutations remain. |
| L-16 | `/campaigns/new` | PARTIAL | Canonical product/approved-content activity binding persisted; full recovery/stale binding permutations remain. |
| L-17 | `/ads/campaigns/:id` | PARTIAL | Persisted fake Ads campaign, explicit HUMAN confirmation and reload checked; creative/stale/expired-authorization permutations remain. |
| L-18 | `/ai/brand-voices` | PASS | VERIFIED_LOCAL_SCOPE |
| L-19 | `/ai/presets` | PASS | VERIFIED_LOCAL_SCOPE |
| L-20 | `/ai/usage` | PASS | VERIFIED_LOCAL_SCOPE |
| L-21 | `/ai/video/bulk` | PARTIAL | Actual local deterministic bulk Video preview, fingerprint, queued child and worker completion executed; cancel/retry/partial and browser reload identity remain. |
| L-22 | `/social/compose` | PARTIAL | Supported composer and persisted text draft exercised; Video composer needs a canonical approved Video output. |
| L-23 | `/ads/marketing` | PARTIAL | Manual persisted plan preview/confirmation/reload exercised; recommendation/version/change permutations remain. |
| L-24 | `/settings/ai/providers` | PASS | VERIFIED_LOCAL_SCOPE |
| L-25 | `/ai/artifacts/:id` | PASS | VERIFIED_LOCAL_SCOPE |

See wp7a4-browser-evidence.md, wp7a4-defect-register.md, wp7a4-coverage-closure.md and the machine-readable ledger/gate. No whole-application certification is inferred.
