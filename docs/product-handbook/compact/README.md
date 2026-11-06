# Compact product handbook

Output: `../VAYUJIT_OS_Product_Handbook_Compact.docx`

This separate practical edition has 45 short seller tasks, about 5,400 words of task guidance and all 19 reviewed historical screenshots. It omits the exhaustive route/field catalogue and technical QA ledger. The detailed edition and its unified source remain unchanged.

## Reading approach

- Use the two linked contents pages to open a numbered task.
- Follow Where to go, the steps, Before you proceed and Next.
- Screenshot pages follow their related task. Landscape pages preserve the full screenshot at a larger size; the source images are not cropped or fabricated.
- Screenshot names, quantities and financial amounts are synthetic examples, not business data to copy.

## Page budget and verification

Requested maximum: **110 pages**. The document has a **67-page designed layout**: one cover, two contents pages, 45 task pages and 19 screenshot pages. Body text is 11 pt; images retain aspect ratio. Page count is reduced through shorter content, not tiny text.

**Actual Word-rendered pagination is NOT VERIFIED.** Section count is not a substitute for rendering. The isolated document runtime/LibreOffice renderer is unavailable, and native Word automation remains disabled after the earlier preservation incident. No desktop Office session was touched and no renderer/package was installed. A 110-page compliance PASS or visual-layout PASS is not claimed. Open the new document in Word and check the actual page count before treating the limit as certified; any spillover must be reviewed, not hidden.

## Checks actually executed

- Six documentation self-tests passed, zero failed/skipped (`tests.xml`).
- XML/package validation passed: 67 designed page sections, 19 landscape screenshot sections, 19 embedded images with matching SHA-256 and alt text, 45 working internal navigation links, zero external relationships or XML errors (`validation.json`).
- Three JavaScript modules and two PowerShell scripts parsed without syntax errors.
- Detailed edition Word file and unified JSON/Markdown source hashes are unchanged (`retained-baseline.json`).
- No application tests, browser screenshot session, database lifecycle, provider request or development-process operation was performed.

## Safe regeneration from repository root

```powershell
node docs/product-handbook/tools/compose-compact.mjs
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File docs/product-handbook/tools/build-compact.ps1
node --test --test-reporter=junit --test-reporter-destination=docs/product-handbook/compact/tests.xml docs/product-handbook/tools/test-compact.mjs
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File docs/product-handbook/tools/validate-compact.ps1
```

Edit `../source/compact-guide.mjs` for the prose. Keep the detailed guide and screenshots unchanged. Do not reuse or re-enable the native Word renderer to obtain a page count.
