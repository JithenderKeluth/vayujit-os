# WP7B-R2 — native zoom and contrast evidence

Date: 2026-11-05, Asia/Calcutta. **Fresh required zoom/contrast verification: NOT VERIFIED.** No new application rendering, screenshot, browser request or database operation was performed.

## Native zoom: inherited observation versus outstanding check

| R1 state | Recorded content viewport / DPR | Actual retained observation | R2 completion result |
| --- | --- | --- | --- |
| Goals 100% | 986×556 / 1.5 | Native Chrome menu percentage observed; document width 971 | NOT VERIFIED for full post-fix interaction |
| Goals 200% | 493×278 / 3 | Native menu percentage observed; document width 485 | NOT VERIFIED for full post-fix interaction |
| Goals 400% | 246×139 / 6 | Native 400% bubble observed; document width 320 | NOT VERIFIED; below 320 CSS-pixel viewport is not alone a conformance failure |
| Ads 400% preview before R1 repair | Initial 246×139 / 6, then maximized | Original overflow/title problem observed; native Escape returned focus | NOT VERIFIED after repair; do not reopen a repaired defect from old evidence |
| Post-fix automated 320px layout | 320 CSS-pixel viewport; dialog left 16/right 304, client/scroll width 288 | R1 actual responsive assertions passed in four contexts | Preserved automated PASS, **not native zoom verification** |

Source: `tmp/qa-seller-browser/e383423462181a8e/r1-manual-evidence.json`, R1 manual report, and final browser report. The native bridge requested a 1000×650 normal window; that request is not a fresh measurement of physical screen size. Some native-zoom Playwright PNGs are blank/incomplete crops. No such crop is used as visual PASS. A retained percentage/DPR does not establish every control, error and dialog interaction.

The twelve R2-Z rows in the [checklist](wp7b-r2-manual-checklist.md) all remain NOT VERIFIED: actual zoom/window/viewport/screenshot fields are null in R2. No CSS/root-font scaling or viewport resize was substituted. For a future safe test, use the browser's own Zoom controls at 100/200/400, capture the visible percentage and full window, then test reflow, keyboard/focus, fields, errors and modal dismissal. Measure content CSS pixels separately from outer window and OS scaling. [Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) explains the 320 CSS-pixel width and legitimate two-dimensional exceptions; [Resize Text](https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html) covers usable enlargement to 200%.

## Independent offline contrast arithmetic

R2 recomputed **340 retained text/focus comparisons**, with **0 mismatches**, across eleven unique foreground/background/threshold combinations from R1 runs `57e1c0c8d2d30df9` and `5bd3f03205fd40bd`. This is VERIFIED PASS for arithmetic/evidence consistency only, not 340 new manual tests or a current rendering certification.

For an sRGB channel s=channel/255, linearize with s/12.92 when s≤0.04045, otherwise ((s+0.055)/1.055)^2.4. L=0.2126R+0.7152G+0.0722B; ratio=(lighter L+0.05)/(darker L+0.05). R2 used retained effective foreground/backgrounds, not an invented canvas. The independent calculation did not import the application's QA contrast function.

| Retained rendered sample | Foreground / background RGB | Recomputed ratio | Threshold / scope | Evidence disposition |
| --- | --- | --- | --- | --- |
| Goal textarea text | 18,43,51 / 255,255,255 | 14.7983857828 | 4.5, SC 1.4.3 | Historical sampled PASS retained |
| Goal help text | 80,107,116 / 255,255,255 | 5.6812593604 | 4.5, SC 1.4.3 | Historical sampled PASS retained |
| Goal/Ads/Marketplace authored focus outline | 7,84,98 / 255,255,255 | 8.5590892627 | 3, SC 1.4.11 | R1 repaired sample PASS retained |
| Ads paragraph | 16,42,67 / 255,255,255 | 14.6416242989 | 4.5 | Historical sampled PASS retained |
| Ads Close text | 255,255,255 / 21,94,117 | 7.2668428169 | 4.5 | Historical sampled PASS retained |
| Unselected editor button text | 18,49,59 / 255,255,255 | 13.7416737615 | 4.5 | Historical sampled PASS retained |
| Selected editor button text | 255,255,255 / 20,93,118 | 7.3501463611 | 4.5 | Historical sampled PASS retained |
| Social timeline strong text | 16,47,53 / 255,255,255 | 14.1887464929 | 4.5 | Actual retained target exists; not every timeline state covered |
| Original Marketplace gold focus | 228,155,40 / 255,255,255 | 2.3286826338 | 3 | Historical FAIL already repaired in R1, **not a new R2 defect** |

The [text criterion](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) uses 4.5:1 normally and 3:1 for sufficiently large text; compare unrounded ratios. [Non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) requires 3:1 for applicable essential visual information against adjacent colors, with specific exceptions. This is not a blanket demand that every decorative border meets 3:1, or a blanket exception for all native controls. Determine whether appearance is author-modified and which indicator identifies the control/state.

Three retained image crops were visually inspected: goal textarea, Social timeline strong text, and financial caption. They confirm those historical text targets are present. They cannot establish current speech, native zoom, full focus-ring pixels, adjacent surroundings outside the crop or all state/boundary requirements. No new screenshot was captured.

## Exact final-R1 text samples still unverified

Source: `tmp/qa-seller-browser/57e1c0c8d2d30df9/wp7br1-browser.json`. These are **18 records**, not 18 unique defects. A dash/omitted index means the bounded-extra record did not identify one element; it is not a NOT APPLICABLE verdict.

| Row | Recorded state/context | Selector/index | Retained reason |
| --- | --- | --- | --- |
| 1 | FLIPKART-wp7br1-chrome-1440 | `.inner-tabs button` | Bounded sample: 2 additional matching targets not measured |
| 2 | FLIPKART-wp7br1-chrome-1440 | `main form label` | Bounded sample: 3 additional matching targets not measured |
| 3 | MEESHO-wp7br1-chrome-1440 | `.inner-tabs button` | Bounded sample: 2 additional matching targets not measured |
| 4 | goal-wp7br1-chrome-390 | `textarea[name=goal]` index 0 | Visibility, overlay, opacity or text-shadow requires additional rendered review. |
| 5 | FLIPKART-wp7br1-chrome-390 | `.inner-tabs button` | Bounded sample: 2 additional matching targets not measured |
| 6 | FLIPKART-wp7br1-chrome-390 | `main form label` index 6 | Visibility, overlay, opacity or text-shadow requires additional rendered review. |
| 7 | FLIPKART-wp7br1-chrome-390 | `main form label` | Bounded sample: 3 additional matching targets not measured |
| 8 | MEESHO-wp7br1-chrome-390 | `.inner-tabs button` | Bounded sample: 2 additional matching targets not measured |
| 9 | MEESHO-wp7br1-chrome-390 | `main input[type=number]` index 2 | Visibility, overlay, opacity or text-shadow requires additional rendered review. |
| 10 | FLIPKART-wp7br1-msedge-1440 | `.inner-tabs button` | Bounded sample: 2 additional matching targets not measured |
| 11 | FLIPKART-wp7br1-msedge-1440 | `main form label` | Bounded sample: 3 additional matching targets not measured |
| 12 | MEESHO-wp7br1-msedge-1440 | `.inner-tabs button` | Bounded sample: 2 additional matching targets not measured |
| 13 | goal-wp7br1-msedge-390 | `textarea[name=goal]` index 0 | Visibility, overlay, opacity or text-shadow requires additional rendered review. |
| 14 | FLIPKART-wp7br1-msedge-390 | `.inner-tabs button` | Bounded sample: 2 additional matching targets not measured |
| 15 | FLIPKART-wp7br1-msedge-390 | `main form label` index 6 | Visibility, overlay, opacity or text-shadow requires additional rendered review. |
| 16 | FLIPKART-wp7br1-msedge-390 | `main form label` | Bounded sample: 3 additional matching targets not measured |
| 17 | MEESHO-wp7br1-msedge-390 | `.inner-tabs button` | Bounded sample: 2 additional matching targets not measured |
| 18 | MEESHO-wp7br1-msedge-390 | `main input[type=number]` index 2 | Visibility, overlay, opacity or text-shadow requires additional rendered review. |

Financial captions/headers, Social states and Campaign textarea are additional inherited targets from broader R1/legacy records; their omission from this final focused run is not an exemption. R1 financial runs explicitly left thirteen additional headers unsampled and mobile captions obscured. The Campaign draft checkpoint was legitimately ineligible for rescheduling. No eligible state is manufactured in R2.

## Focus applicability — do not call all 126 records mandatory missing rings

Original 126 NOT VERIFIED focus-sample records are preserved. Read-only template review and matching R1 measurements support this narrow reconciliation:

| Sub-review | Observations | Verdict | Exact justification |
| --- | --- | --- | --- |
| NA-01: `#goal-help` own focus outline | 4 | NOT APPLICABLE | Static help paragraph without authored tabindex; its textarea focus and the paragraph's text contrast remain required |
| NA-02: dialog explanatory `p` own focus outline | 4 | NOT APPLICABLE | Static paragraph, not a keyboard target; dialog heading/Close and explanatory text remain required |
| NA-03: `main form label` own focus outline | 32 | NOT APPLICABLE | No authored tabindex on sampled Flipkart label templates; the associated input is the independent focus target. Label association/text contrast remain required |
| Matched unfocused Close samples | 4 | VERIFIED PASS for inherited evidence reconciliation only | Same context has an explicitly focused `ads-close-focus-` sample with PASS; no new speech or manual visibility result inferred |
| Remaining interactive observations | 82 | NOT VERIFIED | Button/input/mobile textarea focus states still require exposure and control/state reconciliation; occurrences are not unique controls |

Source checks: goal template's help paragraph, Ads template's explanatory paragraph, and Flipkart label templates; current source hashes exactly match R1. [Focus Visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html) concerns the keyboard interface's visible focus; static non-focusable text does not need its own focus ring. The programmatically focused Ads heading is **not** excluded by this reasoning. This adjudication changes no old report and does not claim every required focus indicator passed.

## Outstanding manual work and N/A policy

C-01–C-15 remain NOT VERIFIED as complete target groups. Expose exact elements, include active/hover/selected/error states and matching transition frames, inspect opacity/gradients/overlays and adjacent colors, then record measurements and aligned context screenshots. Do not default unknown backgrounds to white. Observe transitions without disabling them; earlier transient low-ratio observations remain unresolved as transition-state evidence, not a newly proved persistent defect.

Inactive-control text may qualify for a specific contrast exemption, but absence of a fixture never does; nearby instructions and meaningful disabled/review states still need evaluation. No current inactive-control exemption was asserted without evidence. [Target Size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) permits documented spacing, equivalent, inline, unmodified-agent or essential exceptions; a small target is not automatically FAIL or N/A. No new AAA focus-area requirement is imposed.

The legacy index has 3169 normalized observation keys: 2774 manual-required classifications and 395 historical-violation classifications. It retains 3109 historical “NOT RETESTED IN WP7B” statuses and 60 component-fix references. These are not current unique-defect counts. C-15 retains the exact index/hash and stable IDs, pending cause/applicability mapping rather than silently excluding unmatched records.

No current application-owned defect was newly demonstrated. If live safe verification later proves one, retain its route/state, reproduction, values, severity and impact, propose the smallest correction and request separate application-change authorization. R2 made no implementation changes.
