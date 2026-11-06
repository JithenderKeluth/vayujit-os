# WP7B-R4 — login focus remediation

R4-A VERIFIED_PASS. Original R3A password-toggle focus RGB224,154,54 on opaque white measured2.374231440911746:1, below3 under SC1.4.11. Text was not the failure. Root cause: global authored focus color with no auth-local override (styles.css99–107).

Only production change: apps/web/src/app/auth/auth-page.component.ts, .auth { --vj-focus: var(--vj-color-brand-strong); }. Global token and3px solid outline/3px offset unchanged. Removing precisely this line reproduces preflight source hash; global stylesheet hash unchanged. No auth/API/validation/layout contract changes.

Chrome156.0.8078.76 and Edge156.0.4314.58 at1440/390 widths:40 active auth focus samples PASS, RGB7,84,98 on white,8.559089262681107:1. Email, Password, toggle and enabled Submit; hover/wrong-password401/disabled-submit behavior exercised. Disabled Submit is not keyboard-focusable, not fabricated as an active focus state. Full keyboard UI login passed in four contexts; Space toggle and focus restoration passed. Full viewport focus PNGs and clipping geometry accompany samples, e.g. tmp/qa-wp7br4/browser/wp7br1-r4-chrome-390/focus-64.png. Evidence: tmp/qa-wp7br4/browser/results.json, tmp/qa-wp7br4/followup/results.json, tmp/qa-wp7br4/auth-states/results.json, tmp/qa-wp7br4/fields/results.json.

Angular auth22PASS (four files; includes two new regressions). Focused18 and later22 are overlapping scopes, not40 unique cases. Node14PASS. Production build/ESLint/TS app/spec/Prettier PASS. Initial formatting failure/new-test regex failure retained; corrected and rerun, no assertions weakened. Full historical442 suite not rerun.

