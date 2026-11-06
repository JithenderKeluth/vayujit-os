# Handbook maintenance: WP7B-R5 follow-up

Date: 6 November 2026. Documentation edition: **0.9.1 reference draft**.

## Target and evidence boundary

WP7B-R5 is the latest completed application implementation package supported by the available repository reports. It predates the handbook's 0.9 source census (2026-11-06T04:49:54.237Z). All 131 recorded component sources still match that baseline; route and lockfile comparisons found no change. A supplementary source-file modification-time scan found no later application source edits. This is a targeted page-reference clarification, not evidence of a new application release. If another package was intended, its identifier/completion evidence is still needed.

Reviewed sources: `apps/web/src/app/campaigns/reschedule-dialog.component.ts`, the scoped focus rule in `campaigns.css`, `docs/qa/seller-experience/wp7b-r5-campaign-focus-remediation.md` and `wp7b-r5-gate.json`. No application runtime was invoked.

## Changed handbook chapters

| Chapter | Bounded change |
| --- | --- |
| 12 — Page by page reference | P032 Campaign detail only: inline section, required date/time/timezone, optional reason, Preview change versus Confirm reschedule, warnings/DST branches, safe retry guidance, illustrative India-timezone preview, scoped focus evidence and limitations. |
| 13 — Shared controls and field reference | Five source-reviewed fields: Local date, Local time, IANA timezone, optional Reason (500 characters), conditional Choose DST interpretation. Shared IDs F001–F005 remain stable. |
| 20 — Edition evidence and maintenance | Edition 0.9.1, reviewed-field count and maintenance history; no current-UI or release-certification upgrade. |

The preservation comparison reports **no other changed body sections or field records**. Cover/header edition metadata was regenerated. Changelog, feature-status row P032, coverage, README and generated source files were updated accordingly. Generator changes are confined to documentation tools: scoped additions, preserving changelog history, current field-count reporting and the versioned output filename.

## Screenshots

- **0 replaced; 0 fresh captures.** All 19 previously reviewed historical synthetic screenshots remain byte-identical, in the same figure order.
- Campaign detail P032 still lacks a reviewed screenshot. No expired QA origin was reopened and no database/session authorization was inferred.
- Historical images are not described as current screenshots. No image was fabricated, redrawn or generated.

## Functional and accessibility status preserved

R5's historical 24 passing authenticated synthetic Campaign tests and zero confirmations are cited only for their recorded focus/keyboard/error/reload/navigation scope. They were **not rerun** during this task. Its authored focus cue measured 8.56:1 against white. R5 changed no schedule, authorization, persistence or preview/confirmation contract.

Gate A remains PASS; Gate B remains NOT PASSED; WP7B remains INCOMPLETE. Empty login border contrast (2.09:1), outstanding spoken Narrator observations, native zoom and contrast-applicability evidence remain unresolved. Historical Ads 502, PostgreSQL timestamp attribution, financial-history limits, unverified live-provider certification and parked PC-first backup remain unchanged.

All 510 frozen R5 evidence/report files remain identical to the retained aggregate SHA-256: `4842ea9e3c7511fc72e4d143819a17b25a94e60a54ee169d8a1829f9b3002df8`. This is evidence-file preservation, not a new database/process-cleanup audit.

## Actual validation

| Check | Actual result |
| --- | --- |
| Documentation self-tests | **11 passed, 0 failed, 0 skipped**, JUnit in `handbook-tests.xml`. Includes field/source contracts, separate confirmation, scoped historical claims and changelog preservation. |
| Documentation structural checks | **17 passed, 0 failed**, `validation.json`. |
| Source syntax | **8 JavaScript modules and 3 PowerShell scripts parsed, 0 syntax failures**. No rendering script executed. |
| OOXML structure | 0 XML parse errors; 19 images with alt text; 189 tables with repeating headers; 20 chapter headings; no macros/OLE/remote external relationships. |
| Preservation | PASS: only three intended body sections and five field records changed; source inventory, all images and previous Word bytes unchanged. See `r5-update-preservation.json` and baseline receipt. |
| Changed-directory whitespace | `git diff --check -- docs/product-handbook`: exit 0. This is not a check of unrelated repository work. |
| Application/API/browser tests | **0 executed**; documentation-only authorization. |
| Fresh screens / visual layout / Word open / TOC | **NOT VERIFIED**. Existing render safety hold preserved. |

Reproduction from repository root with the already installed local documentation tooling:

```powershell
node docs/product-handbook/tools/compose.mjs
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File docs/product-handbook/tools/build-handbook.ps1
node --test --test-reporter=junit --test-reporter-destination=docs/product-handbook/quality/handbook-tests.xml docs/product-handbook/tools/test-handbook.mjs
node docs/product-handbook/tools/validate.mjs
node docs/product-handbook/tools/check-r5-update.mjs verify
git diff --check -- docs/product-handbook
```

Do not rerun the one-time `baseline` command: its exclusive-create guard preserves the original comparison. No package installation, dependency lockfile change or Word automation is part of these commands.

## Output and remaining gaps

Updated master reference draft:

`docs/product-handbook/VAYUJIT_OS_Complete_Product_Handbook_Reference_Draft_0_9_1.docx`

The earlier `Reference_Draft.docx` was locked by another process. The first overwrite attempt failed; no lock was released or process interrupted. A new versioned output was generated instead, and a hash comparison confirms the previous file is unchanged.

The document dependency loader/isolated LibreOffice rendering environment is unavailable in this session. Existing native OOXML packaging was reused; native Word automation remains disabled after the historical preservation incident. The old render receipt is retained as historical evidence, **not a fresh render attempt**. No renderer, current Word-open, total page count, cached TOC/page values or visual layout PASS is claimed. The TOC still contains its unupdated placeholder.

Detailed dynamic/API contracts and screenshot coverage remain incomplete (0/150 freshly exercised page routes; 19 historical images across 15/104 families; 26/693 manually reviewed semantic field overrides). Automated documentation checks do not establish application correctness or full handbook verification.

No application code, database, development process, Docker resource, provider, branch, commit or push operation was performed. No old certification workstream was reopened.

**Decision: handbook source update and versioned Word generation complete; CURRENT UI / VISUAL DOCUMENT CERTIFICATION PENDING.**
