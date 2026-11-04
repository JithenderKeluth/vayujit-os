# WP6B — Accessibility review, not a WCAG conformance certificate

2026-10-30. Actual installed Chrome/Edge,1440×900 and390×844, authenticated
synthetic disposable installations. No axe rule suppression, difficult-node
exclusions, hidden-content workaround or lowered threshold.

## Original occurrences and deduplication

Original WP6A report `a373ab59c1c0c318/wp6a-retest.json`:27 document scans,
0 violations, **16 incomplete rule occurrences /29 node occurrences**. Eleven
route/rule/selector keys collapse into the following six semantic root groups;
variant selectors for the same caption controls are not new defects. The original
counts remain historical and are not subtracted merely because new scans differ.

| Original root / target | Inspection and correction | Disposition |
| --- | --- | --- |
| `/ai/video` `.quick-actions`, aria-prohibited-attr6 occurrences | Labelled generic div had no suitable role. Added group role, preserved links/access name. Real getByRole assertions; visible keyboard navigation; group contrast14.64:1 and representative link7.56:1. | Confirmed semantic defect corrected. Full screen-reader announcement not certified. |
| Caption textareas, two duplicated selector variants/positions | Both original controls measured14.80:1 with unobscured centres when scrolled into view. They were duplicate, unbound forms with hardcoded submitted content. Retain one existing labelled textarea, bind actual text, reject missing inputs; no node excluded from axe. | Duplicate/data-entry defect corrected; retained textarea manually measured14.80:1 with visible solid focus, not declared passed from an offscreen axe result. |
| Scene Narration /On-screen text, `label:nth-child(3/4) textarea` | Open actual persisted synthetic storyboard editor. Scroll/focus each field, measure colours and centre hit target. Both14.80:1, unobscured, solid focus in Chrome390 and Edge1440/390. | Bounded normal-state contrast/focus verified. No all-theme claim. |
| Video empty-row `td` | Original row spanned9 columns under8 headers. Corrected span8 and explicit column scopes. Expose the same wide cell through horizontal scrolling;14.64:1, unobscured in all three follow-up contexts. | Structural defect corrected; no generated output invented. |
| `/social` table, th-has-data-cells3 occurrences | Actual accessible-tree inspection shows named region, table/row/four columnheaders. Body has zero rows; separate visible text honestly says no posts. Keyboard region focus/ArrowRight works. | Honest empty state, not a missing rendered data row. Populated provider-post/header associations and full assistive-technology reading remain NOT TESTED. Engine incomplete remains retained. |
| `/social` `th:nth-child(3/4)` | The original Status and Action cells—not Video substitutes—scrolled into view independently. Both14.19:1, unobscured, correctly scoped in Chrome390 and Edge1440/390. | Bounded contrast verified; populated Social table still not certified. |

## Actual final evidence

| Accepted run | Groups | Axe scans | Violations | Incomplete rules /nodes | Manual measurements |
| --- | ---: | ---: | ---: | ---: | ---: |
| Main `e62facf73615c750` | 8 PASS | 28 | 0 | 12 /19 | 30, all MEASURED_PASS |
| Social/empty-cell follow-up `dca65d7d5070a63b` | 4 PASS (includes repeated initial empty-state group) | 10 | 0 | 11 /13 | 9, all MEASURED_PASS |

Do not sum these into12 unique complete workflows or compare incomplete totals
as a defect trend: scan states/counts differ. All engine incomplete findings remain
in each `browser-evidence.json`. Manual computed-style and centre-hit measurements
supplement the established axe engine; they do not replace it or waive incompletes.

Source roots under `tmp/qa-seller-browser/<token>/`: `wp6b-retest.json`,
`wp6b-social-review.json`, screenshots, per-context evidence and `trace.zip`.
The Social follow-up also records actual Playwright accessibility-tree snapshots.
The private synthetic traces are not safe public attachments without review.

## Keyboard, layout, form and recovery evidence

- Actual caption focus →Tab →Shift+Tab returns to the input; solid focus visible.
  Storyboard fields are ordinary labelled editable controls; fixture persists via
  canonical API. Existing storyboard save/stale-version/approval guards retain
  adjacent API coverage. No real generation/approval is simulated as completed.
- Chrome390 and Edge390 Application menu opens with Enter, closes with Escape and
  restores summary focus. This bounded sequence does not prove all dialogs trap-
  free; all modal/state permutations remain untested.
- Named Video and Social scroll regions take focus and ArrowRight. Wide table
  content remains reachable rather than cropped/removed. All reviewed documents
  fit normal1440/390 viewports.
- Actual200% root text-size tests on Video pass document-width assertions and axe
  in Chrome390 and Edge1440/390. This is **text resizing**, not certification of
  browser toolbar zoom, OS magnification, forced colours or every responsive state.
- Finance normal/incomplete/known-cost/reload and exact Ads503 →Refresh recovery
  exercised. Invalid negative financial writes reject422 at API; no nonexistent
  Finance editing screen was invented for browser coverage. Caption input is inert
  without a selected generated video; Add track remains disabled.
- Representative Quick action target104.6×43.6px. Whole visible Video-control scan
  found Products (height20.64px) and inline Review Catalog products (21px on mobile)
  below24px. Inline/spacing exceptions need manual adjudication; this is retained
  review debt, not an automatic WCAG failure or blanket touch-target PASS. No
  physical touch-device or every spacing/overlap condition certification.

## Remaining manual scope / explicit non-claims

Original WP6 Catalog inline mutation-error textarea state was not replayed here;
its prior partial disposition remains unchanged. Calendar conditional ARIA, every
dialog/focus-return path, all themes/hover/disabled states, screen-reader software,
forced colours, browser zoom and physical devices remain manual follow-up.

Social populated tables, generated-video review/player/caption-track creation,
real provider errors, high-volume data and consequential approvals are not certified.
The entered-caption API body is independently Angular-tested but not claimed as
real rendering/provider certification. This is a bounded local accessibility review,
not complete WCAG compliance or full application accessibility closure.
