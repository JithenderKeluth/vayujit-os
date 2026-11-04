# Phase 4A independent finding resolution

2026-10-26T03:59:12.493Z. **ACCESSIBILITY_REMEDIATION_VALIDATED_BOUNDED_SCOPE**. Application **INCOMPLETE**.

The 102 original axe records are route/rule buckets sharing roots, not 102 independent code bugs. No original Phase 4 assertion or contrast helper was edited. Every old finding is retained in the backlog, including resolved history.

## Original eight failed scenarios

| Scenario | Viewport | Retest | Original finding IDs |
| --- | --- | --- | --- |
| QA-P4-SURFACE-AI | desktop | passed | QA-P4-AXE-001F12348729, QA-P4-AXE-5087095AA670, QA-P4-AXE-5E13BE44E3A4, QA-P4-AXE-DD250ACC3B69, QA-P4-AXE-B92F2A83E235, QA-P4-AXE-8A51650AE106, QA-P4-AXE-E8DCA3F276C4, QA-P4-AXE-2E450747C233, QA-P4-AXE-75F369D37253, QA-P4-AXE-FFB4A299A7CE, QA-P4-AXE-2D7E9087CD96, QA-P4-AXE-5E5F9D8178D6, QA-P4-AXE-34A8ABF24CC4, QA-P4-AXE-42FE7B94A7D8, QA-P4-ASSERT-C42568577235, QA-P4-UX-OVERFLOW-805927FDFA67 |
| QA-P4-SURFACE-INTELLIGENCE | desktop | passed | QA-P4-AXE-8E00B31BBCEC, QA-P4-AXE-5125939B31FA, QA-P4-AXE-E9B916722E14, QA-P4-AXE-2E2C527E83C9, QA-P4-AXE-AA47B13918CB, QA-P4-AXE-0A3596EDDB06, QA-P4-AXE-D7DD15FFCE5B, QA-P4-AXE-0BB638A4CD4C, QA-P4-AXE-D710A11DAF0F, QA-P4-AXE-FBA4993C75D8, QA-P4-AXE-5A35D76B79B9, QA-P4-AXE-B7376E19BA87, QA-P4-AXE-C6D5B2B4C7E1, QA-P4-AXE-76479A8A6DF4, QA-P4-AXE-78D838E8B612, QA-P4-AXE-F0BACDB7A3BA, QA-P4-AXE-F75FFFA4B7D0, QA-P4-AXE-8950ECCA4CCC, QA-P4-AXE-4A89BCBB98E6, QA-P4-AXE-8280F5E3D289, QA-P4-AXE-1E1BC8507674, QA-P4-AXE-763F1B4A4390, QA-P4-AXE-0F52BC939E41, QA-P4-AXE-C7838FC35B1A, QA-P4-AXE-26AEEB64E1BD, QA-P4-AXE-338F8353CBE9, QA-P4-AXE-9C85044DF29F, QA-P4-AXE-BCE52D1D245F, QA-P4-AXE-9A12E729646E, QA-P4-AXE-601357805E06, QA-P4-AXE-8C8B1F278405, QA-P4-AXE-8DC6F8DCDEC2, QA-P4-AXE-10C33F043B34, QA-P4-AXE-F35A3F1CCC3B, QA-P4-AXE-91CF6D09DACC, QA-P4-AXE-B4F94EEF1625, QA-P4-AXE-B6A22B4A01D6, QA-P4-AXE-B80713638977, QA-P4-AXE-2599632DCD78, QA-P4-AXE-B04BA9EDFEA5, QA-P4-AXE-C1475768FD6F, QA-P4-AXE-5F89506AC241, QA-P4-AXE-253C0733D8E7, QA-P4-AXE-4C1A2779E46E, QA-P4-ASSERT-B98DFC06C7B1, QA-P4-UX-OVERFLOW-4A67C5636387, QA-P4-UX-RESEARCH-LENGTH |
| QA-P4-SURFACE-MARKETPLACES | desktop | passed | QA-P4-AXE-204FB7530B1E, QA-P4-ASSERT-FC9019123F6D |
| QA-P4-SURFACE-ADS | mobile | passed | QA-P4-AXE-E96F9DFDE280, QA-P4-AXE-23DF0FDF8B0E, QA-P4-AXE-E40C2783EE3D, QA-P4-AXE-44ACD6654124, QA-P4-AXE-CB04ED4A4EA6, QA-P4-AXE-3E5F633E4037, QA-P4-AXE-D7BBEB7BBE2A, QA-P4-AXE-DC01B46528F7, QA-P4-AXE-FD6BE146A5F0, QA-P4-AXE-D9E4382CA736, QA-P4-AXE-3A8E81633B75, QA-P4-AXE-A16747D8ABCB, QA-P4-AXE-6D3829F9EEF4, QA-P4-AXE-D6DAE6D2EE22, QA-P4-AXE-A271A0498E89, QA-P4-AXE-F00D78BBBB9B, QA-P4-AXE-A1E598DC9852, QA-P4-AXE-E14F2270CBE9, QA-P4-AXE-3C9CF969E8F2, QA-P4-AXE-A2CA3D432552, QA-P4-AXE-79435C8AA158, QA-P4-AXE-91E14988E5D5, QA-P4-AXE-A6D1540C04AA, QA-P4-AXE-89DAC1CD93F9, QA-P4-AXE-513CFFA471E1, QA-P4-AXE-66308571F015, QA-P4-AXE-FE9BD5EDDAEF, QA-P4-AXE-2B7FA3EFC0F3, QA-P4-AXE-6765E73EDC71, QA-P4-AXE-AF8BF75CA180, QA-P4-AXE-430F9652F664, QA-P4-AXE-9ED3FC173084, QA-P4-AXE-528EB4702FE9, QA-P4-AXE-86986F1B529F, QA-P4-AXE-B55758865EA3, QA-P4-AXE-9F962BE094D5, QA-P4-AXE-FF234C7614B0, QA-P4-ASSERT-47F74387E395 |
| QA-P4-SURFACE-AI | mobile | passed | QA-P4-AXE-001F12348729, QA-P4-AXE-5087095AA670, QA-P4-AXE-5E13BE44E3A4, QA-P4-AXE-DD250ACC3B69, QA-P4-AXE-B92F2A83E235, QA-P4-AXE-8A51650AE106, QA-P4-AXE-E8DCA3F276C4, QA-P4-AXE-2E450747C233, QA-P4-AXE-75F369D37253, QA-P4-AXE-FFB4A299A7CE, QA-P4-AXE-2D7E9087CD96, QA-P4-AXE-5E5F9D8178D6, QA-P4-AXE-34A8ABF24CC4, QA-P4-AXE-42FE7B94A7D8, QA-P4-AXE-CE8A889155F0, QA-P4-ASSERT-02BB0B433F4A |
| QA-P4-SURFACE-INTELLIGENCE | mobile | passed | QA-P4-AXE-8E00B31BBCEC, QA-P4-AXE-5125939B31FA, QA-P4-AXE-E9B916722E14, QA-P4-AXE-2E2C527E83C9, QA-P4-AXE-AA47B13918CB, QA-P4-AXE-0A3596EDDB06, QA-P4-AXE-D7DD15FFCE5B, QA-P4-AXE-0BB638A4CD4C, QA-P4-AXE-D710A11DAF0F, QA-P4-AXE-FBA4993C75D8, QA-P4-AXE-5A35D76B79B9, QA-P4-AXE-B7376E19BA87, QA-P4-AXE-C6D5B2B4C7E1, QA-P4-AXE-76479A8A6DF4, QA-P4-AXE-78D838E8B612, QA-P4-AXE-F0BACDB7A3BA, QA-P4-AXE-F75FFFA4B7D0, QA-P4-AXE-8950ECCA4CCC, QA-P4-AXE-4A89BCBB98E6, QA-P4-AXE-8280F5E3D289, QA-P4-AXE-1E1BC8507674, QA-P4-AXE-763F1B4A4390, QA-P4-AXE-0F52BC939E41, QA-P4-AXE-C7838FC35B1A, QA-P4-AXE-26AEEB64E1BD, QA-P4-AXE-338F8353CBE9, QA-P4-AXE-9C85044DF29F, QA-P4-AXE-BCE52D1D245F, QA-P4-AXE-9A12E729646E, QA-P4-AXE-601357805E06, QA-P4-AXE-8C8B1F278405, QA-P4-AXE-8DC6F8DCDEC2, QA-P4-AXE-10C33F043B34, QA-P4-AXE-F35A3F1CCC3B, QA-P4-AXE-91CF6D09DACC, QA-P4-AXE-B4F94EEF1625, QA-P4-AXE-B6A22B4A01D6, QA-P4-AXE-B80713638977, QA-P4-AXE-2599632DCD78, QA-P4-AXE-B04BA9EDFEA5, QA-P4-AXE-C1475768FD6F, QA-P4-AXE-5F89506AC241, QA-P4-AXE-253C0733D8E7, QA-P4-AXE-4C1A2779E46E, QA-P4-ASSERT-503A9F1D5FF5, QA-P4-UX-RESEARCH-LENGTH |
| QA-P4-SURFACE-MARKETPLACES | mobile | passed | QA-P4-AXE-204FB7530B1E, QA-P4-AXE-B1E92B58C67D, QA-P4-AXE-E00F1DD38EB3, QA-P4-API-67A1C8127DF2, QA-P4-ASSERT-F8D3F24797EE |
| QA-P4-SURFACE-SOCIAL | mobile | passed | QA-P4-AXE-A1CF7B3F220C, QA-P4-AXE-7C0BAFB59154, QA-P4-ASSERT-700D428F916A |

Intelligence also included the separately audited H1 fixture restriction; a failed scenario is not an independent business bug. Exact original errors, element targets, before/after screenshots, traces and API evidence remain in [the JSON ledger](phase-4a-resolution.json).

## Root corrections

- R11: Populated Trend context setup and context list reused the same heading ID and region name. Give the populated list its own unique heading ID and matching labelledby reference.
- R12: Product detail workspace and its inner product summary had the same accessible name. Use a distinct Product opportunity workspace region name while retaining the visible product headings.
- R10: A populated external-research badge collection named a generic div without a compatible role. Use an explicitly named group; preserve labels, badges and server-derived recovery actions.
- R1: Routed components repeated the application shell main landmark. Use a named section inside the existing sole application main; preserve headings, classes and navigation.
- R2: Generation summary aside was nested within another landmark/form. Use a named Generation summary section, preserving controls and form semantics.
- R3: Status selects and date inputs lacked associated visible labels. Explicit unique for/id associations; group labels with their controls; retain filter query contract.
- R4: Generic progress div carried ARIA properties without a compatible role. Named progressbar with canonical current/min/max and textual step values.
- R5: Action column headings were empty. Visible Actions column heading with col scope; retain every action.
- R6: Empty-state foreground and small status text lost contrast on their actual backgrounds. Reuse darker theme foreground; small website state text inherits its verified state color.
- R7: Overflowing table containers were not keyboard focusable. Named tabindex=0 regions, unique accurate names and existing-theme visible focus; ArrowRight and Tab escape tested.
- R8: Description terms and definitions were children of a generic div. Semantic dl wrapper without removing or changing data.
- R9: Wide table intrinsic width made its caption exceed the mobile viewport and clip. Size caption to an inline-size query container, allow wrapping and keep it at the scroll start; preserve full table columns and keyboard scrolling.
- H1: Phase 4 proxy denied three automatic owner-scoped local context POSTs; not provider calls. Permit only audited metadata payloads to exact canonical context endpoints, retain backend authentication, owner checks and deny acquisition/approvals.

## Per-finding ledger

| Stable ID | Route | Root | Result | Changed source |
| --- | --- | --- | --- | --- |
| QA-UX-CURRENCY-DESKTOP | /products/new | OUT_OF_SCOPE | OPEN / preserved | apps/web/src/app/products/product-form.component.ts |
| QA-UX-CURRENCY-MOBILE | /products/new | OUT_OF_SCOPE | OPEN / preserved | apps/web/src/app/products/product-form.component.ts |
| QA-P2-UX-ECONOMICS-DESKTOP | /intelligence/sourcing-economics | OUT_OF_SCOPE | OPEN / preserved | apps/web/src/app/intelligence/sourcing-economics-workspace.component.ts |
| QA-P2-UX-ECONOMICS-MOBILE | /intelligence/sourcing-economics | OUT_OF_SCOPE | OPEN / preserved | apps/web/src/app/intelligence/sourcing-economics-workspace.component.ts |
| QA-P3-GAP-001 | /api/v1/financial/calculations | OUT_OF_SCOPE | OPEN / preserved |  |
| QA-P3-GAP-002 | /api/v1/operations/action-center/signals/{id}/action | OUT_OF_SCOPE | OPEN / preserved |  |
| QA-P3-GAP-003 | /marketplaces/inventory | OUT_OF_SCOPE | OPEN / preserved | apps/web/src/app/marketplaces/unified-inventory.component.ts |
| QA-P3-A11Y-REVIEW-001 | /intelligence/sourcing-economics | R9 | RESOLVED / independent retest | apps/web/src/app/intelligence/sourcing-economics-workspace.component.ts, apps/web/src/app/intelligence/supplier-due-diligence.component.ts |
| QA-UX-PRE-RUN-MODE-001 | /intelligence/business-agent | OUT_OF_SCOPE | OPEN / preserved | apps/web/src/app/intelligence/business-agent-workspace.component.ts |
| QA-P4-AXE-E96F9DFDE280 | /ads | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-23DF0FDF8B0E | /ads | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-E40C2783EE3D | /ads/create | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-44ACD6654124 | /ads/create | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-CB04ED4A4EA6 | /ads/calendar | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-3E5F633E4037 | /ads/calendar | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-D7BBEB7BBE2A | /ads/accounts | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-DC01B46528F7 | /ads/accounts | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-FD6BE146A5F0 | /ads/campaigns | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-D9E4382CA736 | /ads/campaigns | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-3A8E81633B75 | /ads/analytics | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-A16747D8ABCB | /ads/analytics | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-6D3829F9EEF4 | /ads/recovery | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-D6DAE6D2EE22 | /ads/recovery | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-A271A0498E89 | /ads/settings | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-F00D78BBBB9B | /ads/settings | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts |
| QA-P4-AXE-A1E598DC9852 | /ads/marketing | R1 | RESOLVED / independent retest | apps/web/src/app/ads/marketing-plan.component.ts |
| QA-P4-AXE-E14F2270CBE9 | /ads/marketing | R1 | RESOLVED / independent retest | apps/web/src/app/ads/marketing-plan.component.ts |
| QA-P4-AXE-3C9CF969E8F2 | /ads/optimization | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-A2CA3D432552 | /ads/optimization | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-79435C8AA158 | /ads/recommendations | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-91E14988E5D5 | /ads/recommendations | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-A6D1540C04AA | /ads/optimization-rules | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-89DAC1CD93F9 | /ads/optimization-rules | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-513CFFA471E1 | /ads/anomalies | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-66308571F015 | /ads/anomalies | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-FE9BD5EDDAEF | /ads/experiments | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-2B7FA3EFC0F3 | /ads/experiments | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-6765E73EDC71 | /ads/optimization-history | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-AF8BF75CA180 | /ads/optimization-history | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-430F9652F664 | /ads/comparison | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-9ED3FC173084 | /ads/comparison | R1 | RESOLVED / independent retest | apps/web/src/app/ads/ads-optimization.component.ts |
| QA-P4-AXE-001F12348729 | /ai/generate | R2 | RESOLVED / independent retest | apps/web/src/app/ai/ai-generate.component.ts |
| QA-P4-AXE-5087095AA670 | /ai/video/bulk | R1 | RESOLVED / independent retest | apps/web/src/app/ai/ai-video-bulk.component.ts |
| QA-P4-AXE-5E13BE44E3A4 | /ai/video/bulk | R1 | RESOLVED / independent retest | apps/web/src/app/ai/ai-video-bulk.component.ts |
| QA-P4-AXE-DD250ACC3B69 | /ai/video/bulk | R1 | RESOLVED / independent retest | apps/web/src/app/ai/ai-video-bulk.component.ts |
| QA-P4-AXE-B92F2A83E235 | /ai/video | R4 | RESOLVED / independent retest | apps/web/src/app/ai/ai-video.component.ts |
| QA-P4-AXE-8A51650AE106 | /ai/video | R1 | RESOLVED / independent retest | apps/web/src/app/ai/ai-video.component.ts |
| QA-P4-AXE-E8DCA3F276C4 | /ai/video | R1 | RESOLVED / independent retest | apps/web/src/app/ai/ai-video.component.ts |
| QA-P4-AXE-2E450747C233 | /ai/video | R1 | RESOLVED / independent retest | apps/web/src/app/ai/ai-video.component.ts |
| QA-P4-AXE-75F369D37253 | /ai/studio/seo | R1 | RESOLVED / independent retest | apps/web/src/app/ai/ai-seo.component.ts |
| QA-P4-AXE-FFB4A299A7CE | /ai/studio/seo | R1 | RESOLVED / independent retest | apps/web/src/app/ai/ai-seo.component.ts |
| QA-P4-AXE-2D7E9087CD96 | /ai/studio/seo | R1 | RESOLVED / independent retest | apps/web/src/app/ai/ai-seo.component.ts |
| QA-P4-AXE-5E5F9D8178D6 | /ai/history | R5 | RESOLVED / independent retest | apps/web/src/app/ai/ai-history.component.ts |
| QA-P4-AXE-34A8ABF24CC4 | /ai/history | R3 | RESOLVED / independent retest | apps/web/src/app/ai/ai-history.component.ts, apps/web/src/app/ai/ai.css |
| QA-P4-AXE-42FE7B94A7D8 | /ai/history | R3 | RESOLVED / independent retest | apps/web/src/app/ai/ai-history.component.ts, apps/web/src/app/ai/ai.css |
| QA-P4-ASSERT-C42568577235 | /ai/usage | OVERLAPPING_SCENARIO_RECORD | RESOLVED / independent retest | See linked original scenario and route/rule resolution rows |
| QA-P4-AXE-8E00B31BBCEC | /intelligence/supplier-engagement | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/supplier-engagement-workspace.component.ts |
| QA-P4-AXE-5125939B31FA | /intelligence/supplier-engagement | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/supplier-engagement-workspace.component.ts |
| QA-P4-AXE-E9B916722E14 | /intelligence/trends | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/trend-intelligence-workspace.component.ts |
| QA-P4-AXE-2E2C527E83C9 | /intelligence/trends | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/trend-intelligence-workspace.component.ts |
| QA-P4-AXE-AA47B13918CB | /intelligence/sourcing-scenarios | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/sourcing-scenarios.component.ts |
| QA-P4-AXE-0A3596EDDB06 | /intelligence/sourcing-scenarios | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/sourcing-scenarios.component.ts |
| QA-P4-AXE-D7DD15FFCE5B | /intelligence/sourcing-scenarios | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/sourcing-scenarios.component.ts |
| QA-P4-AXE-0BB638A4CD4C | /intelligence/reviews | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/review-intelligence-workspace.component.ts |
| QA-P4-AXE-D710A11DAF0F | /intelligence/reviews | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/review-intelligence-workspace.component.ts |
| QA-P4-AXE-FBA4993C75D8 | /intelligence/competitors | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/competitor-intelligence-workspace.component.ts |
| QA-P4-AXE-5A35D76B79B9 | /intelligence/competitors | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/competitor-intelligence-workspace.component.ts |
| QA-P4-AXE-B7376E19BA87 | /intelligence/product-opportunities | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/product-opportunity-workspace.component.ts |
| QA-P4-AXE-C6D5B2B4C7E1 | /intelligence/product-opportunities | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/product-opportunity-workspace.component.ts |
| QA-P4-AXE-76479A8A6DF4 | /intelligence/product-opportunities/:id | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/product-opportunity-workspace.component.ts |
| QA-P4-AXE-78D838E8B612 | /intelligence/product-opportunities/:id | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/product-opportunity-workspace.component.ts |
| QA-P4-AXE-F0BACDB7A3BA | /intelligence/sourcing | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/sourcing-workspace.component.ts |
| QA-P4-AXE-F75FFFA4B7D0 | /intelligence/sourcing | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/sourcing-workspace.component.ts |
| QA-P4-AXE-8950ECCA4CCC | /intelligence/alibaba | R6 | RESOLVED / independent retest | apps/web/src/app/intelligence/alibaba-discovery.component.ts |
| QA-P4-AXE-4A89BCBB98E6 | /intelligence/alibaba | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/alibaba-discovery.component.ts |
| QA-P4-AXE-8280F5E3D289 | /intelligence/alibaba | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/alibaba-discovery.component.ts |
| QA-P4-AXE-1E1BC8507674 | /intelligence/indiamart | R6 | RESOLVED / independent retest | apps/web/src/app/intelligence/indiamart-discovery.component.ts |
| QA-P4-AXE-763F1B4A4390 | /intelligence/indiamart | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/indiamart-discovery.component.ts |
| QA-P4-AXE-0F52BC939E41 | /intelligence/indiamart | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/indiamart-discovery.component.ts |
| QA-P4-AXE-C7838FC35B1A | /intelligence/tradeindia | R6 | RESOLVED / independent retest | apps/web/src/app/intelligence/tradeindia-discovery.component.ts |
| QA-P4-AXE-26AEEB64E1BD | /intelligence/tradeindia | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/tradeindia-discovery.component.ts |
| QA-P4-AXE-338F8353CBE9 | /intelligence/tradeindia | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/tradeindia-discovery.component.ts |
| QA-P4-AXE-9C85044DF29F | /intelligence/global-sources | R6 | RESOLVED / independent retest | apps/web/src/app/intelligence/global-sources-discovery.component.ts |
| QA-P4-AXE-BCE52D1D245F | /intelligence/global-sources | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/global-sources-discovery.component.ts |
| QA-P4-AXE-9A12E729646E | /intelligence/global-sources | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/global-sources-discovery.component.ts |
| QA-P4-AXE-601357805E06 | /intelligence/websites | R6 | RESOLVED / independent retest | apps/web/src/app/intelligence/website-intelligence.component.ts |
| QA-P4-AXE-8C8B1F278405 | /intelligence/websites | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/website-intelligence.component.ts |
| QA-P4-AXE-8DC6F8DCDEC2 | /intelligence/websites | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/website-intelligence.component.ts |
| QA-P4-AXE-10C33F043B34 | /intelligence/websites | R7 | RESOLVED / independent retest | apps/web/src/app/intelligence/website-intelligence.component.ts, apps/web/src/styles.css |
| QA-P4-AXE-F35A3F1CCC3B | /intelligence/external | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/external-research-workspace.component.ts |
| QA-P4-AXE-91CF6D09DACC | /intelligence/external | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/external-research-workspace.component.ts |
| QA-P4-AXE-B4F94EEF1625 | /intelligence/external | R7 | RESOLVED / independent retest | apps/web/src/app/intelligence/external-research-workspace.component.ts, apps/web/src/styles.css |
| QA-P4-AXE-B6A22B4A01D6 | /intelligence/autonomous | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/autonomous-research.component.ts |
| QA-P4-AXE-B80713638977 | /intelligence/autonomous | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/autonomous-research.component.ts |
| QA-P4-AXE-2599632DCD78 | /intelligence | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/intelligence-workspace.component.ts |
| QA-P4-AXE-B04BA9EDFEA5 | /intelligence | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/intelligence-workspace.component.ts |
| QA-P4-AXE-C1475768FD6F | /intelligence/supplier-shortlisting | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/supplier-shortlisting.component.ts |
| QA-P4-AXE-5F89506AC241 | /intelligence/supplier-shortlisting | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/supplier-shortlisting.component.ts |
| QA-P4-AXE-253C0733D8E7 | /intelligence/supplier-portfolios | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/supplier-portfolio-workspace.component.ts |
| QA-P4-AXE-4C1A2779E46E | /intelligence/supplier-portfolios | R1 | RESOLVED / independent retest | apps/web/src/app/intelligence/supplier-portfolio-workspace.component.ts |
| QA-P4-ASSERT-B98DFC06C7B1 | /intelligence/cross-marketplace | OVERLAPPING_SCENARIO_RECORD | RESOLVED / independent retest | See linked original scenario and route/rule resolution rows |
| QA-P4-AXE-204FB7530B1E | /marketplaces/video | R8 | RESOLVED / independent retest | apps/web/src/app/marketplaces/marketplace-video.component.ts |
| QA-P4-ASSERT-FC9019123F6D | /marketplaces/financials | OVERLAPPING_SCENARIO_RECORD | RESOLVED / independent retest | See linked original scenario and route/rule resolution rows |
| QA-P4-AXE-1BD3E57BFE08 | /publishing/jobs | R5 | RESOLVED / independent retest | apps/web/src/app/publishing/jobs.component.ts |
| QA-P4-AXE-528EB4702FE9 | /ads/calendar | R7 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts, apps/web/src/styles.css |
| QA-P4-AXE-86986F1B529F | /ads/accounts | R7 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts, apps/web/src/styles.css |
| QA-P4-AXE-B55758865EA3 | /ads/campaigns | R7 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts, apps/web/src/styles.css |
| QA-P4-AXE-9F962BE094D5 | /ads/analytics | R7 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts, apps/web/src/styles.css |
| QA-P4-AXE-FF234C7614B0 | /ads/recovery | R7 | RESOLVED / independent retest | apps/web/src/app/ads/ads-workspace.component.ts, apps/web/src/styles.css |
| QA-P4-ASSERT-47F74387E395 | /ads/comparison | OVERLAPPING_SCENARIO_RECORD | RESOLVED / independent retest | See linked original scenario and route/rule resolution rows |
| QA-P4-AXE-CE8A889155F0 | /ai/video | R7 | RESOLVED / independent retest | apps/web/src/app/ai/ai-video.component.ts, apps/web/src/styles.css |
| QA-P4-ASSERT-02BB0B433F4A | /ai/usage | OVERLAPPING_SCENARIO_RECORD | RESOLVED / independent retest | See linked original scenario and route/rule resolution rows |
| QA-P4-ASSERT-503A9F1D5FF5 | /intelligence/cross-marketplace | OVERLAPPING_SCENARIO_RECORD | RESOLVED / independent retest | See linked original scenario and route/rule resolution rows |
| QA-P4-AXE-B1E92B58C67D | /marketplaces/video | R7 | RESOLVED / independent retest | apps/web/src/app/marketplaces/marketplace-video.component.ts, apps/web/src/styles.css |
| QA-P4-AXE-E00F1DD38EB3 | /marketplaces/meesho | R7 | RESOLVED / independent retest | apps/web/src/app/marketplaces/meesho-workspace.component.ts, apps/web/src/styles.css |
| QA-P4-API-67A1C8127DF2 | /marketplaces/accounts | OUT_OF_SCOPE | OPEN / preserved | apps/web/src/app/marketplaces/marketplace-accounts.component.ts |
| QA-P4-ASSERT-F8D3F24797EE | /marketplaces/financials | OVERLAPPING_SCENARIO_RECORD | RESOLVED / independent retest | See linked original scenario and route/rule resolution rows |
| QA-P4-AXE-A1CF7B3F220C | /social | R7 | RESOLVED / independent retest | apps/web/src/app/social/social-workspace.component.ts, apps/web/src/styles.css |
| QA-P4-AXE-7C0BAFB59154 | /social/settings | R7 | RESOLVED / independent retest | apps/web/src/app/social/social-workspace.component.ts, apps/web/src/styles.css |
| QA-P4-ASSERT-700D428F916A | /social/settings | OVERLAPPING_SCENARIO_RECORD | RESOLVED / independent retest | See linked original scenario and route/rule resolution rows |
| QA-P4-UX-STOCK-EMPTY | /marketplaces/inventory | OUT_OF_SCOPE | OPEN / preserved | apps/web/src/app/marketplaces/unified-inventory.component.ts |
| QA-P4-A11Y-CAPTION-CLIPPING | /intelligence/sourcing-economics | R9 | RESOLVED / independent retest | apps/web/src/app/intelligence/sourcing-economics-workspace.component.ts, apps/web/src/app/intelligence/supplier-due-diligence.component.ts |
| QA-P4-UX-OVERFLOW-805927FDFA67 | /ai/video | OUT_OF_SCOPE | OPEN / preserved | apps/web/src/app/ai/ai-video.component.ts |
| QA-P4-UX-OVERFLOW-4A67C5636387 | /intelligence/autonomous | OUT_OF_SCOPE | OPEN / preserved | apps/web/src/app/intelligence/autonomous-research.component.ts |
| QA-P4-UX-RESEARCH-LENGTH | /intelligence/external | OUT_OF_SCOPE | OPEN / preserved | apps/web/src/app/intelligence/external-research-workspace.component.ts |
| QA-P4-AXE-53F6D1D5D94D | /intelligence/trends | R11 | RESOLVED / independent retest | apps/web/src/app/intelligence/trend-intelligence-workspace.component.ts |
| QA-P4-AXE-26DC4E2A2543 | /intelligence/product-opportunities/:id | R12 | RESOLVED / independent retest | apps/web/src/app/intelligence/product-opportunity-workspace.component.ts |
| QA-P4-AXE-C81046A29D13 | /intelligence/external | R10 | RESOLVED / independent retest | apps/web/src/app/intelligence/external-research-workspace.component.ts |
| QA-P4A-A11Y-MANUAL-001 | /intelligence | MANUAL_REVIEW | OPEN / preserved |  |

Each JSON row includes exact original result, source, correction and independent after-evidence; the caption row lists all 48 actual target reviews. Historical review additionally requires eight financial-header reviews. No unresolved full-document incomplete result is hidden or declared WCAG PASS.
