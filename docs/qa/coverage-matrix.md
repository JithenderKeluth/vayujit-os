# QA source coverage inventory

TypeScript AST route declarations + Python AST API/model declarations. References and test filenames are inventory, not executed coverage or proof of UI accessibility.

154 route declarations; 1610 API declarations; 421 models; 390 backend test files; 68 Angular spec files.

All paths, API handlers, source locations, model tables, candidate frontend API references and test-file counts are in [application-inventory.json](application-inventory.json). API declarations are reconciled with actual OpenAPI in each disposable run. Dynamic bindings are not inferred as exact API coverage.

| Route | Kind | Access | Discoverability | Existing spec (not rerun) | Risk | Phase 1 status |
| --- | --- | --- | --- | --- | --- | --- |
| /intelligence/sourcing-economics | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/sourcing-economics-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/supplier-engagement | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/supplier-engagement-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/trends | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/trend-intelligence-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/trends/:contextId | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/intelligence/trend-intelligence-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/business-agent | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/business-agent-workspace.component.spec.ts | P0 | NOT_EXECUTED |
| /intelligence/sourcing-scenarios | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/sourcing-scenarios.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/reviews | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/review-intelligence-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/competitors | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/competitor-intelligence-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/product-opportunities | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/product-opportunity-workspace.component.spec.ts | P0 | NOT_EXECUTED |
| /intelligence/product-opportunities/:opportunityId | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/intelligence/product-opportunity-workspace.component.spec.ts | P0 | NOT_EXECUTED |
| / | REDIRECT | guest/redirect | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /setup | PAGE | guest/redirect | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /login | PAGE | guest/redirect | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /ads | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/ads/ads-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /ads/create | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ads/ads-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /ads/calendar | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ads/ads-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /ads/accounts/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ads/ads-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /ads/campaigns/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ads/ads-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /ads/accounts | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ads/ads-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /ads/campaigns | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ads/ads-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /ads/analytics | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ads/ads-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /ads/recovery | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ads/ads-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /ads/settings | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ads/ads-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /ads/marketing | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ads/marketing-plan.component.spec.ts | P1 | NOT_EXECUTED |
| /ads/optimization | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ads/recommendations | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ads/optimization-rules | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ads/anomalies | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ads/experiments | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ads/optimization-history | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ads/comparison | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /dashboard | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/operations/dashboard.component.spec.ts | P1 | NOT_EXECUTED |
| /operations/action-center | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/operations/action-center.component.spec.ts | P1 | NOT_EXECUTED |
| /operations/launch-readiness | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/operations/launch-readiness.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/sourcing | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/sourcing-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/alibaba | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/alibaba-discovery.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/indiamart | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/indiamart-discovery.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/tradeindia | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/tradeindia-discovery.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/global-sources | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/global-sources-discovery.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/websites | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/website-intelligence.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/external | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/external-research-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/autonomous | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/autonomous-research.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/due-diligence | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/supplier-due-diligence.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/intelligence-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /campaigns | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /campaigns/new | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /campaigns/:id/video/:activityId | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /campaigns/:id/video | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /campaigns/:id/activities/new | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /campaigns/:id/dependencies | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /campaigns/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /calendar | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /social | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/social/social-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /social/compose | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/social/social-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /social/channel | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/social/social-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /social/accounts | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/social/social-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /social/analytics | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/social/social-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /social/posts/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/social/social-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /social/recovery | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/social/social-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /social/settings | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/social/social-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /marketplaces | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /marketplaces/overview | REDIRECT | guest/redirect | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /marketplaces/video | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /marketplaces/flipkart | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/marketplaces/flipkart-workspace.component.spec.ts | P0 | NOT_EXECUTED |
| /marketplaces/listings/:id/flipkart | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/marketplaces/flipkart-workspace.component.spec.ts | P0 | NOT_EXECUTED |
| /marketplaces/meesho | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/marketplaces/meesho-workspace.component.spec.ts | P0 | NOT_EXECUTED |
| /marketplaces/listings/:id/meesho | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/marketplaces/meesho-workspace.component.spec.ts | P0 | NOT_EXECUTED |
| /marketplaces/amazon | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/marketplaces/amazon-workspace.component.spec.ts | P0 | NOT_EXECUTED |
| /marketplaces/listings/:id/amazon | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/marketplaces/amazon-workspace.component.spec.ts | P0 | NOT_EXECUTED |
| /marketplaces/accounts | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/marketplaces/marketplace-accounts.component.spec.ts | P0 | NOT_EXECUTED |
| /marketplaces/listings | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /marketplaces/inventory | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /marketplaces/orders | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /marketplaces/settlements | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /marketplaces/analytics | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /marketplaces/financials | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /brands | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /brands/new | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /brands/:id/edit | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /brands/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /products | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /catalog | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /catalog/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /products/new | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /products/:id/edit | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /products/:id/channels | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /products/:id/media | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /products/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /ai | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ai/generate | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ai/studio | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ai/images/assets/:outputId | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ai/video/bulk | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ai/video | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/ai/ai-video.component.spec.ts | P1 | NOT_EXECUTED |
| /ai/images/bulk | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ai/images | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ai/studio/seo | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ai/studio/bulk | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ai/ai-bulk.component.spec.ts | P1 | NOT_EXECUTED |
| /ai/studio/artifacts/:id/compare | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ai/ai-artifact.component.spec.ts | P1 | NOT_EXECUTED |
| /ai/artifacts/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ai/ai-artifact.component.spec.ts | P1 | NOT_EXECUTED |
| /ai/history | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ai/brand-voices | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ai/presets | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /ai/usage | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /settings/ai/providers | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /settings/ai/providers/openai-compatible | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /settings/publishing/connectors | REDIRECT | guest/redirect | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /settings/publishing/connectors/wordpress | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /settings/publishing/connectors/shopify | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/publishing/shopify-settings.component.spec.ts | P1 | NOT_EXECUTED |
| /publishing/destinations/shopify | REDIRECT | guest/redirect | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /publishing/destinations/wordpress | REDIRECT | guest/redirect | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /media | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/media/media-list.component.spec.ts | P1 | NOT_EXECUTED |
| /media/upload | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/media/media-upload.component.spec.ts | P1 | NOT_EXECUTED |
| /media/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /publishing | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /publishing/destinations | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /publishing/destinations/new | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /publishing/destinations/:id/edit | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /publishing/destinations/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /publishing/new | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/publishing/publish-new.component.spec.ts | P1 | NOT_EXECUTED |
| /publishing/executions | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /publishing/executions/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /publishing/schedules | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /publishing/schedules/new | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /publishing/schedules/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /publishing/jobs | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /publishing/jobs/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /operations/workers | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /operations/workers/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /workflows | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /workflows/new | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /workflows/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /approvals | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P0 | NOT_EXECUTED |
| /approvals/:id | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/ai/ai-artifact.component.spec.ts | P0 | NOT_EXECUTED |
| /operations | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/operations/control-center.component.spec.ts | P1 | NOT_EXECUTED |
| /operations/jobs | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/operations/control-center.component.spec.ts | P1 | NOT_EXECUTED |
| /operations/providers | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/operations/control-center.component.spec.ts | P1 | NOT_EXECUTED |
| /operations/storage | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/operations/control-center.component.spec.ts | P1 | NOT_EXECUTED |
| /operations/security | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/operations/control-center.component.spec.ts | P1 | NOT_EXECUTED |
| /operations/releases | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/operations/control-center.component.spec.ts | P1 | NOT_EXECUTED |
| /operations/configuration | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/operations/control-center.component.spec.ts | P1 | NOT_EXECUTED |
| /operations/health | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /operations/recovery | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /operations/backups | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /operations/audit | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /execution-history | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /settings/providers | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /settings | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /settings/:section | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |
| /intelligence/supplier-shortlisting | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/supplier-shortlisting.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/supplier-portfolios/:portfolioId | PAGE | authGuard | CONTEXTUAL_OR_DEEP_LINK_REVIEW | apps/web/src/app/intelligence/supplier-portfolio-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/supplier-portfolios | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/supplier-portfolio-workspace.component.spec.ts | P1 | NOT_EXECUTED |
| /intelligence/cross-marketplace | PAGE | authGuard | PRIMARY_OR_ADVANCED_NAV | apps/web/src/app/intelligence/cross-marketplace-supplier.component.spec.ts | P1 | NOT_EXECUTED |
| /** | REDIRECT | guest/redirect | CONTEXTUAL_OR_DEEP_LINK_REVIEW | NO_DIRECT_SPEC | P1 | NOT_EXECUTED |

Backend endpoints without a static service reference are review candidates, not automatically missing features. Adapters, workers, internal ledgers and safety controls deliberately have no page. Deep links need persisted IDs before browser coverage.

<!-- PHASE3 -->
## Phase 3 actual operational coverage

Prior executed coverage and resolutions remain in [Phase 1 retest](phase-1-retest-report.json), [Phase 2](phase-2-coverage.json) and [remediation](remediation-retest.json). The source inventory is not proof of execution.

| Scenario | Viewport | Status |
| --- | --- | --- |
| QA-P3-01 | desktop | passed |
| QA-P3-02 | desktop | passed |
| QA-P3-03 | desktop | passed |
| QA-P3-04 | desktop | passed |
| QA-P3-05 | desktop | passed |
| QA-P3-06 | desktop | passed |
| QA-P3B-01 | desktop | passed |
| QA-P3B-02 | desktop | passed |
| QA-P3B-03 | desktop | passed |
| QA-P3-01 | mobile | passed |
| QA-P3-02 | mobile | passed |
| QA-P3-03 | mobile | passed |
| QA-P3-04 | mobile | passed |
| QA-P3-05 | mobile | passed |
| QA-P3-06 | mobile | passed |
| QA-P3B-01 | mobile | passed |
| QA-P3B-02 | mobile | passed |
| QA-P3B-03 | mobile | passed |

| Persisted scenario | Installation | Status |
| --- | --- | --- |
| test_01_stock_adjustment_replay_stale_and_negative | desktop | PASS |
| test_02_reservation_release_consume_and_invalid_transition | desktop | PASS |
| test_03_order_cancel_ship_return_and_no_automatic_refund | desktop | PASS |
| test_04_concurrent_final_unit_duplicate_delivery_and_multiline_rollback | desktop | PASS |
| test_05_conflicting_stock_key_is_not_silently_accepted | desktop | PASS |
| test_06_financial_event_rounding_loss_and_reconciliation_oracle | desktop | PASS |
| test_07_conflicting_financial_event_is_rejected | desktop | PASS |
| test_08_unknown_cost_revision_does_not_resurrect_old_known_cost | desktop | PASS |
| test_09_current_financial_snapshot_and_later_refund | desktop | PASS |
| test_10_settlement_unknown_mismatch_revision_and_precision | desktop | PASS |
| test_11_business_agent_unknowns_loss_and_default_deny | desktop | PASS |
| test_12_action_center_persisted_replay_concurrency_and_history | desktop | PASS |
| test_13_conflicting_signal_transition_key_rejected | desktop | PASS |
| test_14_human_impersonation_external_action_and_unauthorized_resources | desktop | PASS |
| test_15_source_changes_rescan_and_signal_resolution | desktop | PASS |
| test_16_fresh_process_database_reconstruction | desktop | PASS |
| test_17_canonical_order_synthetic_provenance_and_state_change | desktop | PASS |
| test_18_prepare_original_mobile_states_and_operational_browser_data | desktop | PASS |
| test_01_stock_adjustment_replay_stale_and_negative | mobile | PASS |
| test_02_reservation_release_consume_and_invalid_transition | mobile | PASS |
| test_03_order_cancel_ship_return_and_no_automatic_refund | mobile | PASS |
| test_04_concurrent_final_unit_duplicate_delivery_and_multiline_rollback | mobile | PASS |
| test_05_conflicting_stock_key_is_not_silently_accepted | mobile | PASS |
| test_06_financial_event_rounding_loss_and_reconciliation_oracle | mobile | PASS |
| test_07_conflicting_financial_event_is_rejected | mobile | PASS |
| test_08_unknown_cost_revision_does_not_resurrect_old_known_cost | mobile | PASS |
| test_09_current_financial_snapshot_and_later_refund | mobile | PASS |
| test_10_settlement_unknown_mismatch_revision_and_precision | mobile | PASS |
| test_11_business_agent_unknowns_loss_and_default_deny | mobile | PASS |
| test_12_action_center_persisted_replay_concurrency_and_history | mobile | PASS |
| test_13_conflicting_signal_transition_key_rejected | mobile | PASS |
| test_14_human_impersonation_external_action_and_unauthorized_resources | mobile | PASS |
| test_15_source_changes_rescan_and_signal_resolution | mobile | PASS |
| test_16_fresh_process_database_reconstruction | mobile | PASS |
| test_17_canonical_order_synthetic_provenance_and_state_change | mobile | PASS |
| test_18_prepare_original_mobile_states_and_operational_browser_data | mobile | PASS |

### Unexecuted/blocked scope

- Real provider, external publication, payment/refund dispatch, supplier contact and marketplace authorization are intentionally not executed.
- Order creation/lifecycle uses the actual synthetic-provider API; the UI is a read-only projection, not a seller order-entry or refund-dispatch authority.
- Action Center supports local signal acknowledge/snooze/resolve/reopen, not a complete persisted approval/rejection/execution workflow. Its request-action response is not proof of an executed or durably approved action.
- Independent fresh-process database reconstruction is tested; database service outage and publishing-worker restart remain NOT EXECUTED to avoid interacting with unrelated runtime/backup services.
- Browser failures/timeouts and committed-response loss use explicit network interception, not a claim of real infrastructure failure or worker recovery.
- ORM metadata fixtures do not validate the complete migration chain. No migration certification is claimed.
- No applicable GST treatment, real marketplace fee schedule, bank reconciliation or complete net-profit accounting is inferred from hypothetical synthetic evidence.
- Keyboard checks are bounded; screen-reader/assistive-technology certification and comprehensive modal focus-trap testing remain unexecuted.

<!-- PHASE2 -->
## Phase 2 executed coverage

The source inventory above is not an execution ledger. Phase 1 execution remains in [executed-coverage.json](executed-coverage.json). The following rows are actual Phase 2 scenarios, not comprehensive page coverage.

| Scenario | Viewport | Status |
| --- | --- | --- |
| QA-P2-01 selected product supplier context and incomplete due diligence | desktop | passed |
| QA-P2-02 modeled contribution API UI consistency and reload | desktop | passed |
| QA-P2-03 explicit HUMAN review, duplicate replay and reopening decision | desktop | passed |
| QA-P2-04 product cost edit cancel, persistence and immutable economic snapshot | desktop | passed |
| QA-P2-01 selected product supplier context and incomplete due diligence | mobile | passed |
| QA-P2-02 modeled contribution API UI consistency and reload | mobile | passed |
| QA-P2-03 explicit HUMAN review, duplicate replay and reopening decision | mobile | passed |
| QA-P2-04 product cost edit cancel, persistence and immutable economic snapshot | mobile | passed |

| Persisted API / financial scenario | Fixture installation | Status |
| --- | --- | --- |
| test_01_selection_supplier_due_diligence_decision | desktop | PASS |
| test_02_fractional_rounding_and_capital | desktop | PASS |
| test_03_positive_negative_and_zero_margin | desktop | PASS |
| test_04_missing_invalid_currency_and_tax_unknown | desktop | PASS |
| test_05_idempotency_history_and_reload | desktop | PASS |
| test_06_changed_readiness_does_not_silently_accept_old_cost | desktop | PASS |
| test_07_independent_database_reconstruction | desktop | PASS |
| test_08_human_controls_and_business_decision_history | desktop | PASS |
| test_09_explicit_tax_rate_arithmetic_and_unknown_basis | desktop | PASS |
| test_10_capital_shortfall_is_not_zero | desktop | PASS |
| test_11_prepare_current_browser_review_after_fixture_changes | desktop | PASS |
| test_01_selection_supplier_due_diligence_decision | mobile | PASS |
| test_02_fractional_rounding_and_capital | mobile | PASS |
| test_03_positive_negative_and_zero_margin | mobile | PASS |
| test_04_missing_invalid_currency_and_tax_unknown | mobile | PASS |
| test_05_idempotency_history_and_reload | mobile | PASS |
| test_06_changed_readiness_does_not_silently_accept_old_cost | mobile | PASS |
| test_07_independent_database_reconstruction | mobile | PASS |
| test_08_human_controls_and_business_decision_history | mobile | PASS |
| test_09_explicit_tax_rate_arithmetic_and_unknown_basis | mobile | PASS |
| test_10_capital_shortfall_is_not_zero | mobile | PASS |
| test_11_prepare_current_browser_review_after_fixture_changes | mobile | PASS |

### Explicit gaps

- Manual synthetic ProductOpportunity candidates are authored through the canonical API; real product web discovery is NOT executed or claimed.
- Supplier LOCAL_FIXTURE evidence is synthetic/unverified, not live supplier proof. Switching suppliers/multiple-supplier comparisons remain unexecuted.
- GST and marketplace fee schedules are not inferred. Explicit hypothetical fee arithmetic and unknown tax exclusions are tested; jurisdictional tax certification is not claimed.
- Metadata-created disposable schemas retain the Phase 1 migration limitation; no migration PASS is claimed.
- Full order/refund/settlement net-profit lifecycle and cross-installation isolation remain Phase 3 gaps.

<!-- PHASE4B -->
## Phase 4B initial stock entry

INITIAL_STOCK_ENTRY_VALIDATED_BOUNDED_LOCAL_SCOPE. Opening stock browser: 16/16 pass; API: 36/36 pass, adjacent API: 45/45 pass. See [stock validation](phase-4b-validation.md), [route/control evidence](phase-4b-route-control-coverage.json), [finding ledger](phase-4b-resolution.md). 117 resolved, 12 open; whole application INCOMPLETE. Prior sections remain historical evidence.
