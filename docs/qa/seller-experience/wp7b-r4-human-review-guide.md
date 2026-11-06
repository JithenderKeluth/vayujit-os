# WP7B-R4 — consolidated human review

**SESSION CLOSED — historical URLs below are evidence only. Do not use them or substitute the normal business app. Fresh explicit isolated-session authorization is required for further review. Narrator may be exited manually.**

Use only the existing **Chrome QA window tagged `WP7BR4 SYNTHETIC 208c03c2118d62af`**, origin **http://127.0.0.1:53891**. It is authenticated with synthetic data. Do not enter your normal login or open these links in your normal business browser. Type/paste a destination into the address bar of the existing QA tab when needed.

Session expires **5 November 2026, 11:06:57 PM IST** (17:36:57 UTC), or earlier if completed. Do not use a retired URL after cleanup. No live-provider, approval, import, supplier contact or publication action is part of this review.

Keep Narrator running. Record its version/language once if known. The automation cannot hear it. For each group, report **PASS / FAIL / UNCLEAR**, with any actual words optionally quoted. Report only what you actually heard, not the expected column. The already reported login names/roles, show/hide state and login error speech are preserved and **not requested again**.

## Batch A — goals and navigation (one page)

URL: http://127.0.0.1:53891/intelligence/business-agent

| Review ID | Action | Listen for / expected behavior |
| --- | --- | --- |
| R2-SR-02 | Use the skip link/Tab and Narrator's normal page-reading navigation. | Meaningful main/navigation/heading context and predictable focus, not a confusing unnamed region. |
| R2-SR-03 | Tab to **Start another research goal**; Enter opens, Space closes, Enter reopens. | Name and expanded/collapsed state before and after; focus stays understandable. |
| R2-SR-04 | Tab into the goal textarea and read its instructions. | Goal label, required field and relevant help. |
| R2-SR-05 | Type only `abc`; Tab to **Create research goal**, Enter. Then replace the text with `[QA SYNTHETIC] review draft only`, **without submitting again**. | The actual short-input error identifies the problem; correcting the draft clears/reconciles the error. No valid goal is created. |
| R2-SR-10 | Listen during the short-input error/recovery above. Later, refresh the Financials page once and listen for any loading/status message. | Relevant error/recovery/status announcement without manually moving focus just to find it. If loading was too fast to hear, record UNCLEAR for that part, not PASS. |

Do not activate **Start run**, **Confirm goal context**, discovery or a valid goal submission.

## Batch B — marketplace controls (two pages)

| Review ID | Exact QA URL and action | Listen for / expected behavior |
| --- | --- | --- |
| R2-SR-06 | http://127.0.0.1:53891/marketplaces/accounts — Tab through the import controls without activating any import. | Read-only imports context; distinguishable catalog/order/inventory/financial control names and states. |
| R2-SR-07 | http://127.0.0.1:53891/marketplaces/listings/04063430-a79a-4026-8810-d005cc8e9b9a/meesho — Tab to Product/Category in **Listing editor sections**, Enter to switch the local panel. | Group and button names, understandable panel change. These are grouped buttons, not a claimed tablist. |
| R2-SR-11 | Same Meesho page — open only the **Readiness** editor section; read unmet prerequisites and review controls. | HUMAN review/approval labels, disabled states and missing prerequisites are intelligible. **Do not approve, authorize, save or publish.** |

## Batch C — read-only Ads preview (one page)

URL: http://127.0.0.1:53891/ads/recommendations

| Review ID | Action | Listen for / expected behavior |
| --- | --- | --- |
| R2-SR-08 | Tab to **Preview**, Enter. | Meaningful dialog/title/context announced and focus enters the preview. |
| R2-SR-09 | Tab/Shift+Tab inside; Space on **Close**. Reopen using Enter and dismiss with Escape. | Dialog controls remain understandable; dismissal returns to the correct Preview control, with audible returned-focus context. |

Do not confirm or execute an optimization. The keyboard containment itself is also automated; the human requirement here is what Narrator actually announces.

## Batch D — persisted context and a financial table (two pages)

| Review ID | Exact QA URL and action | Listen for / expected behavior |
| --- | --- | --- |
| R2-SR-12 | http://127.0.0.1:53891/intelligence/product-opportunities/d4278fb4-b7ae-4d63-984a-adbbc4bddb97?goal_id=a63bd41c-bc1d-45e0-a86c-e39d1e694468 — read current product, goal/selection context and evidence notes. | Synthetic/unknown evidence and existing selection are not presented as real verified market success. Do not select/reject or research. |
| R2-SR-13 | http://127.0.0.1:53891/marketplaces/financials — use Narrator's normal table-reading navigation on one populated table. | Caption, column/row relationships and values are understandable. If you cannot establish a header/cell relationship, record UNCLEAR. |

## One response for the whole session

Reply with A/B/C/D results, identifying any individual review ID that was FAIL or UNCLEAR. If only some checks in a batch were performed, say which; unperformed checks remain NOT VERIFIED. Optional exact words improve diagnosis, but absent words will never be invented. The QA title tag is synthetic instrumentation; automated page-title semantics are checked separately on unmodified pages.

## Native zoom / visual review

Native zoom is checked independently where safe tooling can prove Chrome's actual percentage. Do not substitute CSS scaling or a resized viewport. Any remaining human-only task will name its exact screen/setting and ask whether text, focus, fields and dialogs remain usable. No duplicate full keyboard test is requested. Ambiguous caption/overlay/transition/target-size cases remain NOT VERIFIED until measured or specifically observed; no blanket WCAG PASS is inferred from axe.

### Remaining native procedure — only in a freshly approved isolated session

Record Chrome version, Windows display scaling, physical window dimensions and the actual Zoom percentage visible in Chrome's menu. Use Chrome's native menu to set 100%, 200%, then 400%; capture the menu percentage and full window at each setting. Record inner viewport dimensions separately. CSS scaling, mobile emulation, DPR and width alone do not prove browser zoom.

| Review IDs | Synthetic screen | Settings |
| --- | --- | --- |
| R2-Z-01, R2-Z-02, R2-Z-03 | Goals, including legitimate short-input error | 100%, 200%, 400% respectively |
| R2-Z-04, R2-Z-05, R2-Z-06 | Marketplace import controls, focus only | 100%, 200%, 400% respectively |
| R2-Z-07, R2-Z-08, R2-Z-09 | Newly issued Meesho draft URL | 100%, 200%, 400% respectively |
| R2-Z-10, R2-Z-11, R2-Z-12 | Read-only Ads Preview dialog | 100%, 200%, 400% respectively |

At each setting, record visible text/control clipping, horizontal and vertical overflow, reading order, keyboard reachability, focus visibility, field/error usability, and dialog entry/dismissal. Capture screenshots and PASS/FAIL/UNCLEAR per ID; document legitimate two-dimensional table exceptions rather than claiming blanket failure or exemption. Start with a window that provides1280CSS pixels at100% where feasible, yielding320CSS pixels at400%; record actual values instead of assuming. Reset native zoom to100% at completion. Do not import, approve or execute external actions.

C09 loading/error contrast, C12 essential boundary applicability, C13 transient state samples, C14 spacing/target exceptions and C15 legacy reconciliation remain targeted follow-up work, not an instruction to repeat every historical measurement. Do not certify them by subjective batch approval.

After the review, exit Narrator manually if no longer needed. R4 could not safely control its Home window after the app-control approval timeout; no shared ShellHost process was terminated.
