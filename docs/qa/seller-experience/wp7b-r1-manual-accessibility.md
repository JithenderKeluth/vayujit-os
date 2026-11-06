# WP7B-R1 — actual manual accessibility evidence

Date: 2026-11-05 (Asia/Calcutta). **Manual accessibility gate: INCOMPLETE.** No complete WCAG certification is claimed.

## Actual reader, not inferred speech

Windows Narrator was launched; executable version `10.0.26100.8972 (WinBuild.160101.0800)`. Chrome was `156.0.8078.76`. Common NVDA installation paths were absent; portable installations were not exhaustively ruled out. No reader was downloaded or installed.

The owner explicitly reported: “I can listen and report announcements”, then “QA window restored; Narrator audible.” This verifies availability/audibility, **not** the spoken name/role/state of any particular application control. The owner was asked for actual words on Ads preview opening. No semantic speech result is inferred from DOM, focus, accessibility tree or axe output.

Native QA window: `WP7BR1 MANUAL e383423462181a8e`. The uniquely identified synthetic Chrome window was restored by the owner after a minimized-window/input-protection interruption. Native automation then worked, before stopping with: “could not determine the current browser URL on Windows with enough confidence to enforce policy.” No further desktop input was sent after that stop. The isolated Playwright bridge was closed through its existing bounded stop path, not by bypassing that protection.

Required speech checks remain NOT VERIFIED unless an actual owner observation is appended: sign-in labels; navigation; goal disclosure/name/state; validation/error recovery; research and selection; marketplace import groups; Meesho editor controls; Ads title/role and focus restoration; dynamic loading/status feedback; review/approval instructions. “Audible” is not a PASS for this matrix.

Narrator was initially absent and launched for this session. Desktop control ended before its exit could be verified; the owner may close Narrator manually. No reader settings or Windows security/privacy settings were changed.

## Actual native browser zoom

Chrome's native menu was visually observed at 100% and 200%; the native zoom bubble showed 250%, 300%, then 400% after actual key input. No CSS transform, device emulation or CDP page scale set these values. Native browser-window maximize was also exercised, and Ctrl+0 restored 100% before finishing.

| Observed setting/state | Recorded CSS viewport / DPR | Observation | Status |
| --- | --- | --- | --- |
| Goals 100% | 986×556 / 1.5 | Native menu 100%; document width 971; page capture and axe retained | Setting/capture verified, whole form traversal incomplete |
| Goals 200% | 493×278 / 3 | Native menu 200%; document width 485; responsive application menu appeared | Setting/reflow snapshot verified; all form/error actions not verified |
| Goals 400% in initial window | 246×139 / 6 | Native 400% bubble; document width 320, horizontal overflow | Observed; viewport is below the standard 320 CSS-pixel reflow width, not by itself a 320px conformance failure |
| Ads 400%, preview | Same initial CSS viewport; then maximized | Long preview data visibly oversized the dialog and title was outside the initial visible portion. Tab advanced; Escape dismissed and visible focus returned to Preview | Defect observed; width/wrap fix implemented; complete native post-fix retest NOT VERIFIED |
| Reset to 100% | Native Ctrl+0 and 100% bubble | QA-only window returned to normal zoom | Verified |

Metrics/commands: `tmp/qa-seller-browser/e383423462181a8e/r1-manual-evidence.json`; native trace: `wp7br1-native-chrome/trace.zip`. Chrome desktop UI screenshots in the execution transcript establish the visible percentage and clipping observations. **Some Playwright page PNGs at native 400% are blank/incomplete crops**; they must not be represented as sufficient visual evidence. The actual desktop observation and recorded metrics are distinguished from those unreliable crops.

Post-fix Playwright 320 CSS-pixel dialog geometry/keyboard tests are separate automated responsive checks, **not** native zoom certification. Dashboard root-font 200% checks remain text resizing, not browser zoom.

## Contrast method and limits

The supplemental sampler records each actual foreground, ancestor background, font size/weight, outline/border, viewport/occlusion state, criterion, ratio and screenshot. It computes unrounded WCAG sRGB luminance, alpha-compositing only through verified solid backgrounds. Gradients, shadows, opacity/occlusion, missing targets and bounded unsampled nodes stay NOT VERIFIED. Native inactive text exemption is not applied to surrounding instructions. Focus-outline samples do not establish every non-text boundary or full focus conformance.

Examples actually measured in run `e383423462181a8e`:

| Rendered target | Foreground / background | Ratio | Requirement | Result |
| --- | --- | --- | --- | --- |
| Goal textarea | rgb(18,43,51) / rgb(255,255,255) | 14.7983857828 | 4.5:1, 1.4.3 | PASS for sampled state |
| Ads dialog h2 | Same | 14.7983857828 | 3:1 large text, 1.4.3 | PASS for sampled state |
| Social textarea | Same | 14.7983857828 | 4.5:1 | PASS for sampled state |
| Flipkart form label | Same | 14.7983857828 | 4.5:1 | PASS for sampled state |
| Meesho form label | Same | 14.7983857828 | 4.5:1 | PASS for sampled state |

That run has 57 PASS and 23 NOT VERIFIED text-sample records; it does not close all historical targets. Financial and Campaign target sampling was incomplete. Subsequent run evidence and any targeted corrections are recorded in the browser report. Do not silently convert samples missing from an unrendered state into PASS.

Settled-color follow-up `5bd3f03205fd40bd`: 173 text PASS / 27 NOT VERIFIED / 0 text FAIL. Financial caption text was actually exposed and measured at 14.7983857828:1 (rgb(18,43,51) on white). Settled Flipkart/Meesho Product buttons measured 13.7416737615:1 (rgb(18,49,59) on white), unlike earlier transition samples. However, 8 authored focus-outline samples failed at 2.3286826338:1, gold rgb(228,155,40) on white, against 3:1 under 1.4.11. The shared light-surface focus color was corrected to the existing strong brand token; case assertions now include focus failures. Final repair evidence is recorded separately, not retroactively assigned to this run.

Remaining sampled-target limits are explicit: 2 additional editor buttons per marketplace, 3 additional Flipkart labels, 13 additional financial headers; mobile oversized/occluded captions, labels and inputs; inactive focus indicators; and the Campaign reschedule panel whose draft checkpoint fixture is ineligible under the canonical authority. These are incomplete coverage, not waived criteria.

Post-Marketplace-fix run `428ad971b5ba262d` measured its authored outline at 8.5590892627:1, rgb(7,84,98) on white. It exposed two goal textarea outline failures at 2.3742314409:1, rgb(224,154,54) on white. The goal form/disclosure and light Ads workspace were then scoped to the same strong brand token. No global dark-navigation color was altered. An explicit focused-Close sample was added, along with failing assertions for goal/Close focus measurements. These source corrections are not a claim that all unsampled focus controls passed.

Final independent run `57e1c0c8d2d30df9`: 32 case PASS, 0 case FAIL. The measured goal textarea, Ads title/Close and Marketplace focus outlines are now rgb(7,84,98) on white, **8.5590892627:1**, above 3:1. Text measurements: 138 PASS / 18 NOT VERIFIED / 0 FAIL. Focus measurements: 18 PASS / 126 NOT VERIFIED / 0 FAIL; 12 rows have no focus sample. Its 32 axe scans retain 28 incomplete rule occurrences and zero violations. This closes the demonstrated color defects only; it does not close the speech, post-fix native zoom, Campaign fixture or unsampled-target requirements.

Outstanding: actual speech matrix, post-fix native zoom/form/dialog traversal, transition-state contrast adjudication, exact historical incomplete targets not exposed by current fixtures, unsampled focus/non-text borders and target-size/spacing/inline exceptions. Automated zero-violation scans do not close these manual gates.

Method references retained from the primary guidance: [WCAG contrast minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html), [relative luminance](https://www.w3.org/TR/WCAG22/#dfn-relative-luminance), [non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html), [reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html), [modal keyboard guidance](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/).
