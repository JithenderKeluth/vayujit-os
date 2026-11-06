# WP7B-R3 — human-assisted accessibility guide

Snapshot: 2026-11-05T04:19:18.152Z. Use only **http://127.0.0.1:55226** in the window titled **WP7BR3 SYNTHETIC dd240c756c70f504**. Do not use ports 4200/8000 or real credentials. Current browser: Chrome 156.0.8078.76. The automated verifier cannot hear Narrator. Please start the installed Windows Narrator yourself if needed; do not install software or change security/privacy settings.

## First checkpoint — R2-SR-01 only

The QA window may be minimized. Restore only **WP7BR3 SYNTHETIC dd240c756c70f504 - Google Chrome** yourself. Do not use the ordinary VAYUJIT OS window. Automation sent no input when its desktop image did not show the QA surface. If you cannot locate this exact window/address, stop and report NOT VERIFIED.

1. Restore the exact QA window above and check its address ends in /login. All fields must be empty.
2. With Narrator running, click the visible Email label/input, then press Tab to Password. Do not type a password. Tab onward to Show password; use Space once if available, then return it to hidden.
3. Report the actual words spoken at Email, Password and Show password before/after toggling. Expected: meaningful labels, editable/secure field information, and meaningful show/hide state. Exact wording may differ. Do not report any password or personal information.
4. Tell us your browser version, Narrator version if known, reader language/verbosity if changed, and whether anything was silent or confusing. “Narrator audible” alone is not semantic evidence.

**Stop here and reply with what you actually heard. Do not execute the remaining sessions yet.** If the URL/window is uncertain, the session expired or there is no speech, say so; that is NOT VERIFIED, not automatic application failure.

## Remaining grouped sessions — execute one instructed test at a time

| Session | Stable IDs | Actions and required evidence |
| --- | --- | --- |
| Navigation and goals | SR-02–05, SR-10 | Skip link/headings; disclosure Enter/Space and spoken state; focus goal fields/help; existing invalid-input recovery without creating a valid goal; actual status speech. |
| Research and review | SR-11–13 | Read persisted synthetic context, review prerequisites and table/header relationships. No selection, discovery, approval or external execution. |
| Marketplace editors | SR-06–07 | Focus import controls without invoking them; traverse named Meesho editor group/buttons and local panels without saving or publishing. |
| Ads | SR-08–09 | Read-only Preview only; hear title/role, Tab/Shift+Tab containment, Space Close/Escape, returned focus speech. Never confirm execution. |
| Native zoom | Z-01–12 | Four original critical surfaces at actual Chrome 100/200/400%; show percentage, record full-window screenshot, CSS viewport/DPR, reflow, keyboard/focus, forms/errors/dialogs. No CSS scaling or viewport-only substitute. |
| Contrast | C-01–15 | Exact retained targets and actual states; expose by scrolling/focus, record foreground/adjacent background, alpha/overlays, ratio and correct criterion, aligned screenshot. Unknown stays unknown. |

IDs above use the unchanged R2- prefix in the gate/checklist. Full acceptance requirements and original criteria: [R2 checklist](wp7b-r2-manual-checklist.md), copied unchanged per group into [R3 gate](wp7b-r3-gate.json). No group is waived or merged.

Observation format: ID; route; action; actual utterance/visual observation or measured colors; browser/reader; witness/date; screenshot reference; PASS/FAIL/NOT VERIFIED with reason. Never copy expected speech into actual evidence. Screenshots must show only the synthetic QA surface; avoid other windows, credentials, cookies and real business data.

At native 400%, use an approximately 1280 CSS-pixel content starting width to assess 320 CSS-pixel reflow; outer physical window size is not the same measurement. Reset to native100% afterward. Applicable contrast: normal text4.5:1, qualifying large text3:1, essential authored UI/state indicators3:1 against actual adjacent colors. Use unrounded ratios and documented exceptions; do not exempt all disabled-looking or small controls. New demonstrated defects require separate implementation authority.
