# WP6 — Actual browser and regression evidence

Date: 2026-10-30. **Scoped corrections verified; quality closure pending.**
Application certification INCOMPLETE. Full evidence and debt must accompany counts.

## Isolation and execution history

Reused approved `vayujit-qa-postgres`, PostgreSQL17.10, loopback127.0.0.1:55432,
non-superuser `vayujit_qa_admin`, instance389b97d2-a4cd-4d9b-972e-6bb2bf5785eb.
Harness validates exact instance/container/role, marker, owner/OID and signed lifecycle.
Only synthetic `vayujit_qa<16hex>_test` state. Fresh migrations reached20261204_0147.
Actual production Angular, installed Chrome and Edge, real UI owner setup/sign-in.
Viewport1440×900 and390×844; additional responsive360/768 for Video,360 for Autonomous.
Chrome/Edge share Chromium; not physical-device, Firefox/WebKit or live-provider certification.

| Token | Actual outcome |
| --- | --- |
| c23dd3b07a3c442f | Fresh before reproduction: draft-only SEO/Images/Video say No products; Video851px at390; actual deep-link sign-in goes Dashboard. Three finalized traces, normal cleanup. |
| 9c82d601b7f538ca | Four functional groups passed, then local activation403 from QA allowlist. This is a harness block, not failed backend activation. Child cleanup failed, exact signed DROPPING recovery later succeeded. Original failure retained. |
| 7d482ecf59de671f | Four groups passed, then legitimate activation409 because fixture lacked required description. No production rule relaxed. Normal cleanup. |
| **6a6ac4c54803a8dc** | **Broad review COMPLETE:7 grouped checks PASS,92 screen visits,132 PNGs,6 traces,96 axe scans.** Found service failures and Autonomous468px overflow at390. Missing conditional listing textareas explicitly not measured. Normal cleanup. |
| **4e7c1b34606df874** | **Final focused follow-up COMPLETE:8 grouped checks PASS,26 screen visits,76 PNGs,6 traces,30 axe scans.** CSS fix and all three textarea types actually exposed; readonly schema diagnostic retained. Normal cleanup. |
| 9b7b166b93fb4753 | Migration-backed28 backend cases passed,0 failed/error/skip; normal cleanup. |

Roots: `tmp/qa-seller-browser/<token>/wp6-retest.json`, each context's
`browser-evidence.json`, PNG and `trace.zip`; `session-final.json` proves runtime
cleanup. Backend: `tmp/qa-wp6-backend/9b7b166b93fb4753/backend-results.xml` and
`cleanup.json`. Traces contain synthetic authentication sessions: keep local/private,
review and redact before any sharing. They are not production fixtures for promotion.

## Scoped functional checks (final replay)

| # | Real UI/API assertion | Result |
| --- | --- | --- |
| 1 | Draft-only persisted products: SEO/Images/Video explain active eligibility, do not say no products, link Catalog. | PASS |
| 2 | Video360/390/768/1440 document fits; full table remains inside named focusable horizontal-scroll region, keyboard ArrowRight works, diagnostics wrap. Edge390/1440 and reload independently exercised. | PASS for layout, **generation data blocked** |
| 3 | Anonymous exact Catalog product/query/fragment redirects Login; real sign-in restores it and refresh preserves identity. Malicious //evil return falls back Dashboard with no outbound request. Edge desktop/mobile independently sign in. | PASS |
| 4 | Exact GET products503 seam: visible unavailable state, no false empty eligibility; Retry restores canonical read. | PASS |
| 5 | Add legitimate synthetic description, normal Product Activate UI succeeds, same identity becomes selectable; product count unchanged, no generated artifact/publishing. | PASS |
| 6 | Expanded mobile Advanced readable; Enter/Escape and destination focus/menu-close behavior. | PASS |
| 7 | Stored unit100.13 versus recorded line200.25 visibly qualified; Finance says mutable projection/not ledger and missing costs remain UNKNOWN across reload. | PASS for honest presentation, **precision/history gaps open** |
| 8 | Corrected Autonomous controls/policy fit360/390/1440; no mission execution. | PASS |

These are eight assertion groups, not a claim every screen action was exercised.
Persisted backend adds zero-adjustment422/no stock/version mutation, signed bounds,
provenance and replay/reservation regressions. HUMAN listing approvals/execution,
provider calls, worker actions and synthetic-to-production promotion were not bypassed.

## Broad screen review / seller usability

Actual broad route list (Chrome desktop and mobile unless noted):

| Area | Routes actually reviewed | Seller assessment / limitations |
| --- | --- | --- |
| Home | `/dashboard`, `/intelligence/business-agent`, `/operations/action-center`, `/operations/launch-readiness` | Purpose/source links and blocked/read-only distinctions visible; signals not source repairs. Evidence-dense Agent page remains a usability concern, not a promise of live successful discovery. |
| Research | `/intelligence/product-opportunities`, `/intelligence/research` | Saved synthetic goal/opportunity context and next-step guidance rendered. No real discovery/source approval executed. |
| Source | `/intelligence/cross-marketplace`, `/intelligence/sourcing`, `/intelligence/supplier-engagement`, `/intelligence/sourcing-scenarios`, `/intelligence/sourcing-economics`, `/intelligence/due-diligence`, `/intelligence/supplier-shortlisting` | Distinct discovery/quotes/verification/economics purposes reviewed. Missing scoped context remains blocked; no fabricated supplier or assessed status. Long pages and technical IDs remain follow-up UX debt. |
| Sell | `/catalog`, `/products`, `/marketplaces/listings`, `/marketplaces/inventory`, `/marketplaces/orders`, `/marketplaces/financials` | Persisted synthetic stock/order/finance read models and exact product deep link reviewed; UNKNOWN costs/profitability explicit. Generic list visit is not marketplace listing certification. |
| Create | `/ai/studio`, `/ai/studio/seo`, `/ai/images`, `/ai/video` | Active-only guidance fixed; no generation calls. Video data read returns500, accurately shown unavailable. Data-health blocker remains. |
| Grow | `/campaigns`, `/social`, `/ads`, `/ads/optimization`, `/ads/marketing` | Optional marketing, not seller prerequisites. Video-dependent Social and Ads data unavailable; no external marketing action. Optimization/marketing routes additionally reviewed in Edge. |
| Manage | `/calendar`, `/operations`, `/workflows`, `/approvals`, `/execution-history`, `/settings` | Existing views render; no jobs/executions/settings mutations. Conditional calendar/empty-table ARIA checks remain manual review. |
| Marketplaces | `/marketplaces`, `/marketplaces/accounts`, `/marketplaces/amazon`, `/marketplaces/flipkart` | Missing accounts/authorization remain genuine external prerequisites. No fabricated connection, publication or provider certification. |
| Advanced | `/intelligence/autonomous` | Historical narrow overflow reproduced468px and fixed; policy and mission controls retained, no execution. |

**39 distinct planned routes**,92 broad review visits including Edge repetitions;
26 final focused visits are additional retests, not26 new features. Edge desktop
and mobile independently reviewed Dashboard, SEO, Images, Video, Ads, Ads optimization,
Ads marketing, Orders and Finance and signed in to the Catalog deep link. Not all
Chrome actions were repeated in Edge. Before/focused PNGs and full surface JSON
retain visible headings, controls, blockers, viewport/document widths and routes.
Broad `review.layout` was absent due to a helper-return mismatch; original surface
JSON has the actual dimensions. Final focused review records dimensions directly.

## Accessibility and manual review

Unmodified axe-core document rules, no excluded difficult nodes:

| Run | Scans | Violations | Incomplete rule occurrences / node occurrences |
| --- | ---: | ---: | ---: |
| Broad | 96 | 0 | 31 /45 |
| Final focused | 30 | 0 | 11 /21 |

These are repeated state occurrences, not unique defects or complete WCAG PASS.
Remaining checks include conditional ARIA on supplier/account/video metrics, empty
table headers, calendar children and partially obscured contrast nodes. Exact
targets/HTML/rules are in each `browser-evidence.json`; none are silently closed.

Final Catalog local Amazon draft genuinely lacks category/image and remains
**incomplete**. It was created through the existing UI, not an invented validation
rule. Scrolling/focusing exposed `textarea[name="estimate-reason"]`,
`textarea[maxlength="20000"]` and `textarea[spellcheck="false"]` at both widths.
All six actual measurements: ink RGB18,43,51 against white, **14.80:1**, center
unobscured and visible solid focus outline. Final mobile Advanced representative
link **12.37:1** (broad13.16:1 during color transition). These computed-style/occlusion
measurements supplement real axe; they are not a replacement engine or all-theme
proof. Historical inline mutation-error textarea state was not re-executed, so the
old seven occurrences are only partially addressed, not globally closed.

Visual image review inspected final mobile Video scroll region and Autonomous
layout, desktop populated draft textarea/focus and shared Catalog actions. Full
screen-reader, high-contrast, zoom, every dialog/error state and touch-target audit
remain incomplete. Some technical inputs remain developer-oriented; do not call
the complete Seller OS professionally finished merely from these screen visits.

## Unmasked errors

Broad: Video generations500×14, Ads overview500×8, optimization overview500×2,
anomalies500×2, comparison500×2. Final focused: generations500×12, Ads overview500×4,
optimization500×2, anomalies500×2, comparison500×1 and comparison502×1.
Each run also has one exact injected products503. Zero uncaught page errors and
zero guard-denied requests in the accepted runs does **not** mean zero console or
server errors. No broad allowlist suppressed these failures.

`4e7c1b34606df874/wp6-schema-drift.json` independently confirms readonly schema
drift for Video and AdCampaign, without row data or raw exception logs. See
[quality debt](wp6-quality-debt.md); no service success is certified.

## Regression / quality / cleanup

- Backend28 PASS:9 WP6 +11 WP5 +8 inventory/orders, no skipped/failed cases.
- Angular370 PASS /81 files; Node61 and Python54 QA self-tests PASS.
- Production build422.71kB below unchanged500kB warning budget.
- Focused ESLint, app/spec tsc, Ruff/Black, compileall, strict commerce schema mypy,
  PowerShell5.1 parser and git diff whitespace checks PASS. Not repository-wide debt closure.
- Independent `tmp/qa-wp6-final-audit.json`:6 signed DROPPED/absent DBs,23 traces CRC
  PASS, original10 containers/networks/volumes preserved, approved credentials0.
  One earlier guarded interrupted-drop recovery, no FORCE/unrelated session termination.
  Final backend/broad/focused cleanup normal, exit0; historical failures retained.

## Windows reproduction

Existing approved QA instance only; no arbitrary URL/alternate database substitution:

```powershell
.\scripts\qa-postgres.ps1 -Action Status
npm.cmd run build --workspace @vayujit/web -- --configuration production
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp6.ps1 -Action Backend
# Terminal 1, keep open; wait for signed READY token and session.json.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test-seller-wp6.ps1 -Action Browser
# Terminal 2, use that fresh token only, never a historical cleaned run.
.\apps\api\.venv\Scripts\python.exe -m qa.wp6_schema_probe <READY_TOKEN>
node qa/wp6-browser-retest.mjs tmp/qa-seller-browser/<READY_TOKEN>/session.json
# Optional smaller follow-up on a NEW fresh runtime: append --focused.
# Replay requests owned shutdown; wait for Terminal 1 CLEANED.
.\apps\api\.venv\Scripts\python.exe -m qa.wp6_final_audit
npm.cmd run qa:unit
.\apps\api\.venv\Scripts\python.exe -m unittest discover -s qa/unit -p 'test_*.py'
npm.cmd test --workspace @vayujit/web -- --watch=false
git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check
```

Do not run a new build during browser execution. Report generation keeps original
failure records, not manufactured passes. No permanent/golden DB, live calls,
backup work, branches, commits or pushes. Stop before WP7.
