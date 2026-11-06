# Handbook coverage and validation

Classification: HANDBOOK REFERENCE DRAFT / CURRENT UI AND VISUAL CERTIFICATION PENDING.

| Dimension | Actual numerator / denominator | Meaning |
| --- | --- | --- |
| Static route representation | 156 / 156 (100%) | Includes six redirects; not a functional or UI PASS. |
| Page-family reference sections | 104 / 104 | Covers 150 declared page routes, with shared/conditional behavior limitations. |
| Declared field entries | 693 / 693 | Source guidance and explicit unknowns, not 693 independently validated form contracts. |
| Manually reviewed semantic overrides | 26 / 693 (3.75%) | Five additional reschedule fields source-reviewed; dynamic API contracts remain gaps. |
| Historical screenshot families | 15 / 104 (14.42%) | 19 genuine retained synthetic images; zero replacements. |
| Fresh authenticated UI | 0 / 150 (0%) | No current authorized screenshot session; no fresh captures. |
| Structural documentation checks | 17 passed / 17 | Not layout or application certification. |

Edition 0.9.1: P032 Campaign detail and shared rescheduling reference updated for existing WP7B-R5 evidence. No post-baseline application change was found. See r5-update-report.md and r5-update-preservation.json for the bounded comparison; all other reference sections and screenshots must remain unchanged.

20 chapters; six illustrative journeys; 24 task prompts. Total pages NOT VERIFIED. Word open/TOC page values/PDF export/visual review NOT VERIFIED; native automation BLOCKED and disabled. See render-and-environment-limitations.md for the Office preservation incident. See handbook-tests.xml for actual self-test results. No application test suite ran.

Final metadata:

```json
{
  "edition": "0.9.1",
  "generated_at": "2026-11-06T17:41:05.121Z",
  "chapters": 20,
  "page_families": 104,
  "page_routes": 150,
  "redirects": 6,
  "route_entries": 156,
  "field_entries": 693,
  "manually_reviewed_semantic_overrides": 26,
  "screenshot_files": 19,
  "families_with_screenshots": 15,
  "fresh_current_ui_pages": 0,
  "worked_journeys": 6,
  "prompts": 24,
  "route_inventory_coverage": {
    "numerator": 156,
    "denominator": 156,
    "percent": 100,
    "meaning": "Source-declared route representation only, not functional/current UI coverage"
  },
  "fresh_ui_coverage": {
    "numerator": 0,
    "denominator": 150,
    "percent": 0
  },
  "render_status": "BLOCKED",
  "completeness": "REFERENCE_EDITION_WITH_EXPLICIT_GAPS",
  "page_count": null,
  "word_open_verified": false,
  "visual_review": "NOT_VERIFIED",
  "structured_checks_passed": 17,
  "structured_checks_failed": 0
}
```
