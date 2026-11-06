# VAYUJIT product handbook

Primary artifact: VAYUJIT_OS_Complete_Product_Handbook_Reference_Draft_0_9_1.docx. Edition 0.9.1 is an evidence-backed reference edition, not fully verified current UI coverage.

## Editable sources

- source/editorial.mjs: beginner chapters, prompts, tutorials, terminology and routines.
- source/page-guidance.mjs: page purposes, safe next steps and manually reviewed field rules.
- source/screenshots.mjs: only individually reviewed genuine capture selections.
- source/ui-inventory.json: generated static source census with hashes.
- source/book.json and source/handbook.md: generated unified content.
- inventory/: routes, fields, feature states and screenshot provenance/hash registers.
- quality/: missing coverage, metrics, generation/render evidence.

## Safe local regeneration

Run from the repository root, using already installed project tools; no network install is required by these documentation scripts.

1. node docs/product-handbook/tools/discover.mjs
2. Review the source diff and all dynamic/conditional gaps. Edit the editorial/page guidance through normal file review; do not change application code to match a manual.
3. Review any new screenshot visually for secrets/PII and correct synthetic/real provenance, then update source/screenshots.mjs. Do not reopen retired origins or create a QA database without fresh approval.
4. node docs/product-handbook/tools/compose.mjs
5. powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File docs/product-handbook/tools/build-handbook.ps1
6. Validate the DOCX, update TOC/page fields using the explicitly controlled local rendering step, render and inspect all affected pages. Record what was and was not inspected.
7. node docs/product-handbook/tools/validate.mjs
8. Run git diff --check and update changes/handbook-changelog.md. No commit/push is implied.

The Word builder uses native OOXML packaging as a fallback because the document workspace dependency loader is unavailable. It must not silently install packages or modify the app dependency lockfile. Rendering is a separate explicit local operation; do not automate an existing user document or change Office security settings.

Keep sufficient unchanged screenshots rather than recapturing them all. SHA-256 and captured-build/current component comparisons help identify replacement needs; a matching component alone does not prove unchanged backend/runtime behavior.

A later fully verified edition requires genuine safe current rendering, detailed dynamic choices/API validation and action-effect review, screenshots for missing states, privacy/layout/TOC review and a recorded coverage decision. Never relabel edition 0.9.1 as complete merely because the file generates.

## Rendering safety hold

The native Word fallback is DISABLED after an Office window-preservation check failed. Do not run or re-enable it. Its prior self-reported isolation flags do not establish preservation of the pre-existing user window. See quality/render-and-environment-limitations.md. Use a separately approved isolated renderer; until then page count, TOC cached values, successful Word open and layout remain NOT VERIFIED. No global PowerShell policy change is needed or authorized.

The two older base/Edition_0_9 Word filenames are intermediate attempts, not deliverables; a file lock prevented moving them. Do not release the lock by terminating an unrelated Word process. Use only the Reference_Draft filename above. The owner should manually check/restore the document previously open in Word.

## Edition 0.9.1 maintenance

Latest completed source evidence: WP7B-R5. Only Campaign detail, five shared rescheduling fields and related evidence/maintenance metadata were changed. No later application source delta was found. See quality/r5-update-report.md and quality/r5-update-preservation.json. The previous Reference_Draft.docx is locked and was left untouched; use the versioned 0_9_1 artifact above. No fresh screenshots or current UI/layout certification are claimed.
