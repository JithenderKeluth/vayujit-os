# WP7B — accessibility inventory

2525 retained evidence files were indexed; 0 unreadable. 3169 normalized observation keys are **not unique defects**. Repeated rule/context/node occurrences are not summed into a defect count. Complete row-level occurrence references: [reviewed JSON](../../../tmp/qa-wp7b/accessibility-observations-reviewed.json).

Keys preserve normalized route, route-component bucket, rule, DOM selector, recorded browser/viewport and unresolved cause. Unknown context is retained as unknown; route buckets are not falsely claimed as verified source-component attribution. Underlying causes have been attributed only where demonstrated. Different selectors may still share a cause; historical violations are not automatically current defects.

| Semantic group | Disposition | Relevant criterion / limitation |
| --- | --- | --- |
| Import controls named on generic div | RESOLVED AND RETESTED; explicit group role and preserved accessible label | 4.1.2 relevance; original axe result was incomplete, not a newly confirmed axe violation |
| Meesho editor controls named on generic div | RESOLVED AND RETESTED; group, not invented tablist semantics | 4.1.2 relevance; actual spoken output not verified |
| Optimization preview dialog | RESOLVED AND RETESTED IN FOUR CONTEXTS; loading 500 separate | Keyboard/focus order and modal APG; not full screen-reader certification |
| Social image-review and Campaign reschedule textareas | Manual verification required for exact retained targets | Contrast 1.4.3; no blanket closure from current route scans |
| Flipkart/Meesho final forms and Social timeline strong nodes | Manual verification required for exact retained states | Contrast 1.4.3; hidden/obscured nodes must be exposed |
| Financial captions/headers and empty Social/Ads tables | Retain exact historical incomplete evidence; not automatically a defect or resolved | 1.3.1 relevance; empty/obscured content can prevent automated adjudication |
| Historical Phase 1–4/WP6/WP7 remaining targets | Row-level historical violation/manual-required classifications retained | No deletion, waiver or silent closure |

Fresh broad scans: 92, 0 violation rule/context occurrences, 60 incomplete rule/context occurrences (882 repeated nodes). Focused retest: 52 scans, 0 violation and 33 incomplete rule/context occurrences (331 repeated nodes). These are different execution scopes, not additive unique-defect totals.

WP7A-7's retained 40 scans / 22 incomplete rule-context occurrences / 76 repeated nodes remain historical evidence, not 22 unique defects.

Zero axe violations is not full accessibility compliance. Criteria references: [Keyboard](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html), [Focus visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html), [Name/role/value](https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html).
