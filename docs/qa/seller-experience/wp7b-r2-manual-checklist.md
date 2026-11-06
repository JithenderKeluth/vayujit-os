# WP7B-R2 — exact remaining manual worklist

Date: 2026-11-05, Asia/Calcutta. **Gate B INCOMPLETE. Gate A PASS is preserved, not rerun.**

## Safety prerequisite — currently not met

No QA database lifecycle authority is granted by R2. R1's nine disposable databases were removed; its native bridge is recorded COMPLETED. Current read-only window inventory found no tagged R1 QA window and no Narrator window/process. Narrator remains installed. No ordinary application window was selected or operated, no HTTP application request was made, and no database was inspected, created, recovered or deleted.

Do not use the normal `127.0.0.1:4200` business installation, old deleted-fixture UUIDs, or the expired R1 origin as a shortcut. Page GETs can persist projections/anomalies; “only looking” does not establish database safety. Do not run R1 lifecycle commands under R2.

Before future execution, obtain separate authority for an actual isolated synthetic fixture session (including any needed creation/use/cleanup), or supply an already authorized active non-production session whose scope explicitly covers this verification. Verify its exact identity and fixture context through the existing guards. A connection string, window title or old approval is not sufficient authority. No application implementation authority is included.

## Checklist scope and decision rules

The 40 rows below are **review groups**, not 40 unique defects or an exhaustive WCAG certification denominator. Thirteen speech groups and the historical contrast/target items come from the WP7B manual report/inventory and R1 Gate B remaining list. Twelve native-zoom rows are the four explicitly critical interaction surfaces at R2's requested three zoom settings. No new AAA focus-appearance requirement or arbitrary device matrix is introduced. Exact source paths, criterion IDs, retained pending selectors and legacy-index hash are in [gate JSON](wp7b-r2-gate.json).

- VERIFIED PASS: an identified applicable check has sufficient actual evidence, with its scope/date explicit.
- VERIFIED FAIL: an applicable behavior or measurement is demonstrated to fail; record reproduction and request separate implementation authority.
- NOT VERIFIED: missing environment, speech, target, reliable capture or sufficient evidence. This blocks Gate B; it is not an application defect by itself.
- NOT APPLICABLE: a specific criterion/measurement does not apply, with a recorded reason. Absence of a fixture is never this exemption.

## Speech — actual words required

| ID | Interaction | Acceptance / criterion | Required observation | Result |
| --- | --- | --- | --- | --- |
| R2-SR-01 | Sign-in labels | 1.3.1, 3.3.2, 4.1.2; inherited WP7B/R1 manual scope | Email/password controls, required/secure-field information and show-password state are intelligible; no credentials spoken or recorded. | NOT VERIFIED |
| R2-SR-02 | Navigation, landmarks and headings | 1.3.1, 2.4.1, 2.4.3; inherited WP7B/R1 manual scope | Skip link, primary navigation, current page and heading/landmark sequence are understandable; focus moves predictably. | NOT VERIFIED |
| R2-SR-03 | Goal disclosure | 2.1.1, 4.1.2; inherited WP7B/R1 manual scope | Disclosure name and expanded/collapsed state are spoken before/after Enter and Space; no lost draft/focus. | NOT VERIFIED |
| R2-SR-04 | Goal fields | 1.3.1, 3.3.2, 4.1.2; inherited WP7B/R1 manual scope | Textarea label, required state and relevant help are spoken on focus; do not require one exact wording. | NOT VERIFIED |
| R2-SR-05 | Form errors and recovery | 3.3.1, 4.1.3; inherited WP7B/R1 manual scope | Actual invalid field and explanatory error are conveyed, with recovery feedback; never submit a valid business artifact. | NOT VERIFIED |
| R2-SR-06 | Marketplace import controls | 1.3.1, 4.1.2; inherited WP7B/R1 manual scope | Read-only imports group and each control name/state are identifiable; focusing is allowed, executing an import is not. | NOT VERIFIED |
| R2-SR-07 | Meesho editor controls | 2.1.1, 4.1.2; inherited WP7B/R1 manual scope | Listing editor sections group, button names and resulting local panel are understandable; do not assert invented tablist semantics. | NOT VERIFIED |
| R2-SR-08 | Ads dialog entry | 2.4.3, 4.1.2, APG modal; inherited WP7B/R1 manual scope | Read-only Preview opens with meaningful dialog/title context and focus inside. | NOT VERIFIED |
| R2-SR-09 | Ads containment, dismissal and return | 2.1.1, 2.1.2, 2.4.3, APG modal; inherited WP7B/R1 manual scope | Tab/Shift+Tab remain in the dialog; Space on Close and Escape dismiss; returned Preview focus is spoken. | NOT VERIFIED |
| R2-SR-10 | Dynamic loading/status/retry | 4.1.3; inherited WP7B/R1 manual scope | Relevant waiting/error/result messages without focus changes are actually announced; distinguish silence from an unexercised state. | NOT VERIFIED |
| R2-SR-11 | Review/approval controls | 3.3.2, 4.1.2; inherited WP7B/R1 manual scope | Read labels, checkbox/disabled states and unmet prerequisites without activating approval/execution. | NOT VERIFIED |
| R2-SR-12 | Research and selection context | 1.3.1, 4.1.2; inherited WP7B/R1 manual scope | Current goal/product, synthetic/unknown evidence and existing selection state remain comprehensible; do not select/reject or research. | NOT VERIFIED |
| R2-SR-13 | Tables and lists | 1.3.1; inherited WP7B/R1 manual scope | Relevant captions, headers, row relationships and list order are intelligible with actual reader navigation. | NOT VERIFIED |

Wording may vary with voice/verbosity. Record what the listener actually hears; do not copy the expected column into actual results. No R2 utterance has been observed. Required controls must have understandable names/roles/states; relevant messages need appropriate announcements. See [Name/Role/Value](https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html), [Status Messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html), [Error Identification](https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html) and [Labels/Instructions](https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions.html). APG modal behavior supplements the existing application contract; it is not an invented new WCAG criterion.

## Native zoom — each row requires full interaction, not just a percentage

| ID | Critical screen | Native zoom | Criterion / acceptance | Result |
| --- | --- | --- | --- | --- |
| R2-Z-01 | Goals and form/error state | 100% | R2 baseline comparison; R2 §3 / R1 native-zoom scope | NOT VERIFIED |
| R2-Z-02 | Goals and form/error state | 200% | 1.4.4, 2.1.1, 2.4.7; R2 §3 / R1 native-zoom scope | NOT VERIFIED |
| R2-Z-03 | Goals and form/error state | 400% | 1.4.10, 2.1.1, 2.4.7; R2 §3 / R1 native-zoom scope | NOT VERIFIED |
| R2-Z-04 | Marketplace import controls | 100% | R2 baseline comparison; R2 §3 / R1 native-zoom scope | NOT VERIFIED |
| R2-Z-05 | Marketplace import controls | 200% | 1.4.4, 2.1.1, 2.4.7; R2 §3 / R1 native-zoom scope | NOT VERIFIED |
| R2-Z-06 | Marketplace import controls | 400% | 1.4.10, 2.1.1, 2.4.7; R2 §3 / R1 native-zoom scope | NOT VERIFIED |
| R2-Z-07 | Meesho editor | 100% | R2 baseline comparison; R2 §3 / R1 native-zoom scope | NOT VERIFIED |
| R2-Z-08 | Meesho editor | 200% | 1.4.4, 2.1.1, 2.4.7; R2 §3 / R1 native-zoom scope | NOT VERIFIED |
| R2-Z-09 | Meesho editor | 400% | 1.4.10, 2.1.1, 2.4.7; R2 §3 / R1 native-zoom scope | NOT VERIFIED |
| R2-Z-10 | Ads preview dialog | 100% | R2 baseline comparison; R2 §3 / R1 native-zoom scope | NOT VERIFIED |
| R2-Z-11 | Ads preview dialog | 200% | 1.4.4, 2.1.1, 2.4.7; R2 §3 / R1 native-zoom scope | NOT VERIFIED |
| R2-Z-12 | Ads preview dialog | 400% | 1.4.10, 2.1.1, 2.4.7; R2 §3 / R1 native-zoom scope | NOT VERIFIED |

For every row record: actual browser menu percentage, window and content viewport dimensions, OS scaling/DPR if available, full-window screenshot including the percentage, page screenshot, visible content, reflow/overflow, Tab/Shift+Tab, visible focus, fields/errors and dialog Close/Escape/return focus where relevant. Native 200% relates to [resize text](https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html); 400% review relates to [reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html). At 400%, target a starting content width of 1280 CSS pixels, yielding approximately 320 CSS pixels; window outer dimensions and physical pixels are not interchangeable. Retain the two-dimensional-layout exception only where actually applicable; table cells do not receive a blanket exemption.

## Contrast and remaining target applicability

| ID | Remaining target / state | Applicable criterion | Result |
| --- | --- | --- | --- |
| R2-C-01 | Social image-review textarea: main textarea | 1.4.3 | NOT VERIFIED |
| R2-C-02 | Social timeline strong text: .timeline strong | 1.4.3 | NOT VERIFIED |
| R2-C-03 | Flipkart labels and unmeasured forms: main form label; three extra matching labels; mobile index 6 | 1.4.3 | NOT VERIFIED |
| R2-C-04 | Flipkart remaining editor buttons: .inner-tabs button; two beyond the eight-element sample | 1.4.3,1.4.11 | NOT VERIFIED |
| R2-C-05 | Meesho remaining editor buttons: .inner-tabs button; two beyond the eight-element sample | 1.4.3,1.4.11 | NOT VERIFIED |
| R2-C-06 | Mobile Meesho/goal fields: Meesho main input[type=number] index 2; goal textarea index 0 | 1.4.3,1.4.11 | NOT VERIFIED |
| R2-C-07 | Financial captions, including mobile occlusion: main caption; actual recorded targets, not guessed new rows | 1.4.3 | NOT VERIFIED |
| R2-C-08 | Financial headers beyond sample: main th; thirteen additional matching targets in finance runs | 1.4.3 | NOT VERIFIED |
| R2-C-09 | Ads dialog historical obscured heading/state: [role=dialog] h2 and relevant error/loading states | 1.4.3,1.4.11 | NOT VERIFIED |
| R2-C-10 | Campaign reschedule textarea: .reschedule-panel textarea; needs legitimately eligible fixture | 1.4.3 | NOT VERIFIED |
| R2-C-11 | Remaining interactive focus states: Unfocused buttons/inputs and mobile goal samples, after applicability/deduplication | 1.4.11,2.4.7 | NOT VERIFIED |
| R2-C-12 | Essential control boundaries and state indicators: Actual authored input/checkbox/select boundary or indicator and adjacent colors | 1.4.11 | NOT VERIFIED |
| R2-C-13 | Transition/hover/selected state contrast: 180ms transition evidence must align color sample and rendered frame | 1.4.3,1.4.11 | NOT VERIFIED |
| R2-C-14 | Target size, spacing and legitimate exceptions: Relevant controls; do not blanket-exempt small links | 2.5.8 | NOT VERIFIED |
| R2-C-15 | Legacy manual-target reconciliation: Stable observation IDs in accessibility-observations-reviewed.json | Per recorded rule and applicability; no new blanket criterion | NOT VERIFIED |

These rows retain the existing incomplete work; they do not reclassify historical violations as new defects. C-15 references every stable key in the retained 3169-key legacy index, whose 3109 “NOT RETESTED IN WP7B” labels remain historical. Keys/occurrences are not unique defects and may share causes. Do not silently exclude unmapped entries or require one new test per repeated occurrence without cause/applicability review.

## Concise human-executable protocol — only after the safety prerequisite is satisfied

1. Record the authorized synthetic origin, active fixture IDs, browser/reader versions, date, reader language and relevant verbosity. Have a listener present. Start the installed reader manually if needed; never install software or change security/privacy settings for this checklist.
2. In the goal workspace, use Tab to the disclosure; exercise Enter and Space. Tab into fields, read help and required state. Use the existing invalid synthetic-form scenario to observe error/recovery; do not save a valid goal.
3. Focus Marketplace import controls to hear names/group/states; **do not execute an import, validation, reconnect, authorization or provider call**. In Meesho, inspect local editor panels without saving pricing, inventory or publication.
4. Open only the canonical local read-only Ads Preview. Record actual title/role speech. Test Tab, Shift+Tab, Space on Close and Escape, then listen to returned focus. Do not confirm or execute an optimization.
5. Read already persisted research/selection and review/approval states; never select/reject, approve, research, dispatch or publish. Observe existing loading/error/status fixtures without weakening authority or creating an artificial success.
6. Repeat the four critical surfaces at native 100%, 200%, 400%. Set zoom through Chrome/Edge's own controls, show the percentage and capture it. Scroll and traverse controls; do not use CSS transforms, root-font changes or viewport emulation as zoom proof. Reset native zoom afterward.
7. For C-01–C-15 expose the exact retained element/state, inspect foreground/adjacent colors including alpha/overlays, calculate without rounding thresholds, record applicability and an aligned screenshot. Never suppress axe rules or disable transitions to manufacture a clean state.
8. For each observation supply: `ID | fixture/route | browser/version | reader/version | action | exact words heard or measured colors/ratio | screenshot/trace | verdict | reason/witness/date`. “Not heard” after a completed action differs from “not executed.” Stop if the URL/window identity becomes uncertain.

No runtime step above was executed in R2. Newly demonstrated defects require reproduction/severity/business impact and a separately approved minimal fix; do not implement automatically. See [speech evidence](wp7b-r2-screen-reader-evidence.md), [zoom/contrast evidence](wp7b-r2-zoom-contrast-evidence.md) and [assessment](wp7b-r2-assessment.md).
