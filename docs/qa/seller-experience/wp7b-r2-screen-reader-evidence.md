# WP7B-R2 — screen-reader evidence

Date: 2026-11-05, Asia/Calcutta. **Required speech verification: NOT VERIFIED.**

## Observed environment, not speech

Read-only Windows inventory returned no window tagged as the historical isolated WP7B/R1 QA session, no Narrator window and no running Narrator process. The installed Narrator file version is `10.0.26100.8972 (WinBuild.160101.0800)`; installed Chrome is `156.0.8078.76`, Edge `156.0.4314.58`. These are installed candidates, **not a reader/browser pair exercised in R2**.

All R1 synthetic databases are recorded removed in the retained signed cleanup report, and its native bridge is COMPLETED. R2 grants no new database lifecycle authorization. No replacement session, application request, login, reader launch, keyboard action, process pause or application code change was performed. Ordinary business-app windows were not selected for testing.

The prior owner statements “I can listen and report announcements” and “QA window restored; Narrator audible” belong to R1. They established audibility then, not semantic speech then or now. No transcript for the requested Ads opening was obtained. No R2 utterance was supplied or heard. Do not report silence as a demonstrated application failure when the action was never exercised.

## Per-check evidence

**Shared metadata applying to every row:** actual executed browser/version = none; actual reader/version used = none; installed candidates/version as above; witness = none; fresh screenshot/trace = none. Each machine-readable row repeats null actual execution fields. Expected semantics are a test oracle, never a transcript.

| ID | Element/interaction | Expected spoken behavior | Actual observed speech | Result |
| --- | --- | --- | --- | --- |
| R2-SR-01 | Sign-in labels | Email/password controls, required/secure-field information and show-password state are intelligible; no credentials spoken or recorded. | NOT OBSERVED — action not executed | NOT VERIFIED |
| R2-SR-02 | Navigation, landmarks and headings | Skip link, primary navigation, current page and heading/landmark sequence are understandable; focus moves predictably. | NOT OBSERVED — action not executed | NOT VERIFIED |
| R2-SR-03 | Goal disclosure | Disclosure name and expanded/collapsed state are spoken before/after Enter and Space; no lost draft/focus. | NOT OBSERVED — action not executed | NOT VERIFIED |
| R2-SR-04 | Goal fields | Textarea label, required state and relevant help are spoken on focus; do not require one exact wording. | NOT OBSERVED — action not executed | NOT VERIFIED |
| R2-SR-05 | Form errors and recovery | Actual invalid field and explanatory error are conveyed, with recovery feedback; never submit a valid business artifact. | NOT OBSERVED — action not executed | NOT VERIFIED |
| R2-SR-06 | Marketplace import controls | Read-only imports group and each control name/state are identifiable; focusing is allowed, executing an import is not. | NOT OBSERVED — action not executed | NOT VERIFIED |
| R2-SR-07 | Meesho editor controls | Listing editor sections group, button names and resulting local panel are understandable; do not assert invented tablist semantics. | NOT OBSERVED — action not executed | NOT VERIFIED |
| R2-SR-08 | Ads dialog entry | Read-only Preview opens with meaningful dialog/title context and focus inside. | NOT OBSERVED — action not executed | NOT VERIFIED |
| R2-SR-09 | Ads containment, dismissal and return | Tab/Shift+Tab remain in the dialog; Space on Close and Escape dismiss; returned Preview focus is spoken. | NOT OBSERVED — action not executed | NOT VERIFIED |
| R2-SR-10 | Dynamic loading/status/retry | Relevant waiting/error/result messages without focus changes are actually announced; distinguish silence from an unexercised state. | NOT OBSERVED — action not executed | NOT VERIFIED |
| R2-SR-11 | Review/approval controls | Read labels, checkbox/disabled states and unmet prerequisites without activating approval/execution. | NOT OBSERVED — action not executed | NOT VERIFIED |
| R2-SR-12 | Research and selection context | Current goal/product, synthetic/unknown evidence and existing selection state remain comprehensible; do not select/reject or research. | NOT OBSERVED — action not executed | NOT VERIFIED |
| R2-SR-13 | Tables and lists | Relevant captions, headers, row relationships and list order are intelligible with actual reader navigation. | NOT OBSERVED — action not executed | NOT VERIFIED |

These are the inherited requirements, not new workflows or an assumption of full WCAG coverage. Existing R1 keyboard PASS and the unchanged DOM/source do not replace actual speech evidence. Correct group names do not require one particular Narrator wording at one specific Tab stop; record the listener's words, action, relevant verbosity/language and context before judging.

## Human recording procedure

Use the [manual checklist](wp7b-r2-manual-checklist.md) only after an independently authorized synthetic test session exists. In that session, the human controls authentication and listens while the verifier performs only non-destructive permitted interactions. Never report passwords, cookies, tokens or personal/business data in a transcript.

For each ID record browser/version, reader/version, fixture route, exact action, actual words (or “nothing announced after action”), focus before/after, witness/date, evidence and verdict. Include disclosure state, required/help/error context, disabled/review prerequisites, dialog entry/exit and dynamic feedback. Reader verbosity/configuration can affect delivery; do not automatically attribute absent words to application code without reproducing the conditions.

No approval/import/research/publishing command may be used merely to produce speech. Use supported existing synthetic loading/error/review states, or retain NOT VERIFIED. If URL/window identity is uncertain, stop that automation path; do not bypass protection or substitute a different browser.

## Certification effect

Thirteen required speech groups remain NOT VERIFIED. No VERIFIED PASS or VERIFIED FAIL speech result is asserted. No application defect is newly demonstrated, no R1 fix is reopened, and no implementation authorization is inferred. Gate A remains the preserved R1 PASS; Gate B and overall WP7B remain INCOMPLETE.
