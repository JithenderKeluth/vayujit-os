# WP7B — keyboard, visual and manual evidence

## Executed protocol

Synthetic canonical persisted fixtures; authenticated installed Chrome 156.0.8078.76 and Edge 156.0.4314.58; 1440×900 and 390×900. Playwright issues actual keyboard events, using Tab to reach controls, not locator click/fill/focus shortcuts. These are scripted/guided keyboard checks, **not witnessed screen-reader or native SendInput evidence**. API/domain-service fixture setup and HUMAN fixture decisions are not claimed as keyboard actions.

Broad run 66af017c1429b89e:

| Context | Passed | Failed |
| --- | --- | --- |
| wp7b-chrome-1440 | 21 | 2 |
| wp7b-chrome-390 | 20 | 3 |
| wp7b-msedge-1440 | 20 | 3 |
| wp7b-msedge-390 | 20 | 3 |

Focused corrected-source retest 071d1158209292db:

| Context | Passed | Failed |
| --- | --- | --- |
| wp7b-chrome-1440 | 11 | 2 |
| wp7b-chrome-390 | 12 | 1 |
| wp7b-msedge-1440 | 12 | 1 |
| wp7b-msedge-390 | 13 | 0 |

Per-case routes, failures, screenshots and traces: [gate JSON](wp7b-gate.json), [focused browser evidence](../../../tmp/qa-seller-browser/071d1158209292db/wp7b-browser.json). Screenshots are bounded viewport and full-page captures; trace.zip is retained per context. Exact checks and limitations are in the executable qa/wp7b-browser.mjs. Tested-source hash manifest: tmp/qa-seller-browser/071d1158209292db/wp7b-tested-source-sha256.json; unchanged during focused run: true.

## What the assertions establish

- Owner setup/sign-in and protected catalog redirect; keyboard inputs are synthetic only.
- Main navigation, mobile menu Enter/Escape and return focus.
- Bounded Tab/Shift+Tab focus checks on Research, Opportunity, Catalog, Suppliers, Sourcing, Economics, Finance, Inventory, Orders, Marketplace, Video, Social and Ads routes; these do **not** establish every action on those pages.
- Goal disclosure/textarea, variant invalid-JSON recovery, and named import/editor group tests. The broad run used an ambiguous descendant-summary selector and repeated the same Blue option; the focused harness uses the direct summary and distinct option combinations. Original failing evidence is preserved.
- Confirmed modal entry/trap defect before fix: Chrome390 / Edge desktop/mobile in broad run. The fix starts at its title, contains forward/reverse Tab on the sole Close control, supports Space close and Escape, and restores Preview focus. Actual independently successful contexts are listed in gate.browser.focused.dialog_keyboard_verified. Any initial 500 remains a failing availability outcome even when one bounded reload allows keyboard verification.
- Dashboard root-text enlargement to 200%, and Catalog width at 320 CSS pixels. Root font resizing is **not browser zoom**. No full visual or target-size conformance claim.

## Native / screen reader limitations

Native isolated Chrome window was uniquely identified, but capture failed twice: “window crop is outside captured monitor.” Fresh window selection and activation retry failed; native input stopped. No native keyboard events were sent. Evidence: tmp/qa-wp7b/native-evidence.json.

Narrator.exe is installed. Actual speech is not available through the current observation tools and no human speech witness participated. Landmarks/headings, labels/instructions, error announcements, dynamic statuses, tables/lists, dialog descriptions, button states, HUMAN review states and loading/failure/retry speech are **NOT VERIFIED**. AX trees, DOM labels and axe results are not substituted.

Remaining: exact historical obscured text/form/table targets, non-text focus contrast, actual 200%/400% browser zoom, target-size/spacing/inline exceptions and complete disabled/loading/error-state traversal. A human-compatible reader/browser session and native capture recovery are required before closing these gates.

[W3C modal keyboard guidance](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) informs entry, containment, dismissal and return-focus checks. [Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) distinguishes equivalent 320 CSS-pixel presentation and two-dimensional tables; individual cells are not blanket-exempt. [Target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) requires evaluating spacing and legitimate exceptions; a small inline link is not automatically a confirmed defect.
