# Real browser-based seller experience QA

Date: **2026-10-28** · Run `28be28cb826accab`.

**Outcome: real browser exploration completed; application certification remains
INCOMPLETE. No production fixes were made.**

The actual production-built Angular application rendered in installed Chrome
155.0.8059.40 and Edge 156.0.4314.42, using Playwright and a fresh authenticated,
persisted disposable PostgreSQL environment. Desktop was **1440 × 900**; mobile
was a **390 × 844 responsive viewport**, not a physical-device certification.
Both installed browsers use Chromium. Bundled Firefox/WebKit/Chromium executables
were absent; nothing was downloaded to manufacture additional browser coverage.

## Executive result

| Measure | Actual result |
| --- | --- |
| Priority seller journeys attempted | 12; mixed complete segments, partial and blocked workflows, not 12 end-to-end passes |
| Valid application URL paths rendered | 64, normalized to 63 screen types |
| State captures | 162, including one invalid investigator route probe; not 162 unique pages |
| Evidence images | 224 viewport/full-page PNGs |
| Finalized Playwright traces | 4 |
| Ranked browser-confirmed findings | 20: 11 defects, 2 workflow gaps, 7 usability findings |
| Additional suspected finding | 1 active-Advanced-navigation contrast issue requiring state verification |
| Axe executions | 26; incomplete results remain; no WCAG certification |
| Console error events / uncaught page errors | 36 / 0 |
| HTTP error responses / HTTP 5xx | 20 / 0 observed in browser instrumentation |
| Safety-blocked browser mutations | 3, plus 1 proxy refusal of an incorrectly requested live supplier mode |
| Disposable database cleanup | PASS, independently rechecked in a fresh process |
| Production application files changed | None for this mission |

This was human-directed exploratory Playwright work, not a newly passing
comprehensive automated suite. Counts of screens, assertions, axe executions,
self-tests and findings are deliberately separate.

## Highest-priority seller problems

Detailed expected/actual behavior, reproduction, business impact, evidence and
suggested correction for every item are in [browser-findings.json](browser-findings.json).
All are open; this request authorized investigation, not production remediation.

| ID | Priority / kind | Browser-observed problem |
| --- | --- | --- |
| SE-BROWSER-001 | P1 defect | Supplier workspace displays LOCAL_FIXTURE but its primary discovery CTA submits LIVE_READ_ONLY. Safety proxy denied it before acquisition. |
| SE-BROWSER-002 | P1 defect | Economics context creation loses the selected product/opportunity/supplier references and persists all three as null. |
| SE-BROWSER-004 | P1 defect | NOT_ASSESSED verification shows zero recorded gaps without a discoverable initial assessment action. API assessment later reveals three missing-evidence gaps. |
| SE-BROWSER-011 | P1 workflow gap | Selected opportunity has no discoverable Catalog conversion action in the inspected surfaces, despite a working canonical API. |
| SE-BROWSER-015 | P1 usability | Economics renders raw dictionary warnings and a 42,933px mobile page, obscuring the decision brief. |
| SE-BROWSER-003 | P2 defect | Supplier Compare link encodes its fragment into the route and sends the seller to Dashboard. |
| SE-BROWSER-005 | P2 defect | Six research-card 404/no-projection outcomes lack useful visible result feedback; score loading itself works. |
| SE-BROWSER-006 | P2 defect | Catalog reports Currency UNKNOWN for canonical economics whose base currency is INR. |
| SE-BROWSER-007 | P2 defect | Shortlists counter stays 0 after successful creation/HUMAN transition, then becomes 1 on reload. |
| SE-BROWSER-008 | P2 defect | Product Opportunities says RESEARCH COMPLETE before any research run has executed. |
| SE-BROWSER-009 | P2 defect | Video page is 851px wide at a 390px viewport. |
| SE-BROWSER-010 | P2 defect | Failed draft mutation discards loaded Catalog context and renders an error screen without an h1. Retry recovers. Trigger was the QA guard. |
| SE-BROWSER-020 | P2 defect | Correct authentication protects a Catalog deep link, but sign-in loses the destination and opens Dashboard. |
| SE-BROWSER-012 | P2 usability | Mobile menu remains open after destination selection, hiding the destination below navigation. Escape recovery works. |
| SE-BROWSER-013 | P2 usability | Primary Suppliers enters a later-stage sourcing decision workspace rather than an obvious supplier overview/discovery path. |
| SE-BROWSER-014 | P2 usability | My Research opens a broad technical workspace rather than focused current/saved research; mobile height 10,886px. |
| SE-BROWSER-016 | P2 usability | Eight-decimal money and an unformatted margin ratio make correct financial results hard to interpret. |
| SE-BROWSER-017 | P2 usability | Creative tools say No products yet when products exist but are draft/ineligible; active-only eligibility is not explained. |
| SE-BROWSER-018 | P2 workflow gap | Empty Catalog image picker lacks an obvious secure upload/media-library handoff at the point of need. |
| SE-BROWSER-019 | P2 usability | Product-entry Quantity does not clearly explain its separation from canonical opening stock; the stock workflow itself works. |

Other observed friction, not inflated into additional ranked defects: repeated
journey banners displace task controls below the fold; duplicate breadcrumbs and
raw UUIDs/internal milestone names increase cognitive load; product creation
defaults to USD before an explicit INR choice; some displayed text contains
encoding artifacts. None justifies changing canonical approval or financial rules.

## What genuinely worked

- First-owner setup, mismatched-password feedback, real sign-in and session-based
  protected routes. Logout restored 401 protection.
- Kids category and INR 300000 goal/plan persistence. A manual Home & Kitchen
  control was excluded under the Kids goal. Live category discovery remains
  unverified; this narrow success must not be presented as a fix to it.
- Authoritative opportunity score retrieval, explicit HUMAN selection and
  identical product-decision replay using the same persisted identity.
- Brand prerequisite guidance and UI creation; product creation, INR price/cost,
  price editing and reload; Catalog Back/Forward/refresh navigation.
- Opening-stock negative validation, review, explicit HUMAN count confirmation,
  canonical quantity 12 and reload consistency.
- Supplier detail shows provenance and unknown commercial fields; one-supplier
  comparison correctly refuses to invent a second candidate or winner.
- HUMAN shortlist for verification and explicit Keep under review business
  decision persistence. Proceed stayed disabled while required evidence was
  incomplete. No confirmation dialog appeared for Keep under review; cancellation
  was not tested despite an early exploratory screenshot's filename.
- Action Center generated one critical shortage from an explicit synthetic
  known-zero inventory fact; evidence, acknowledgement, filter/reload and Inventory
  source link worked. An ongoing shortage was not falsely resolved.

### Financial verification (synthetic assumptions only)

Supplemental canonical APIs prepared a reproducible scenario; the browser then
loaded and displayed the resulting economics. These are hypothetical assumptions,
not supplier quotes or Amazon fee schedules:

- Quantity 500; assumed unit acquisition cost INR 100.125; freight INR 2500/shipment.
- Included landed total: `100.125 × 500 + 2500 = 52562.50`.
- Landed cost/unit: `105.125`.
- Hypothetical selling price 250; hypothetical 10% selling fee gives 25/unit;
  hypothetical PER_ORDER 50 allocated across 500 gives 0.1/unit.
- Contribution/unit: `250 − 105.125 − 25.1 = 119.775`.
- Contribution margin: `119.775 / 250 = 0.4791`, or **47.91%**.
- Capital available 300000; acquisition funding 52562.50; headroom 247437.50.

Five independent exact-value checks passed for landed/unit selling cost,
contribution, margin and capital required. The values persisted to eight fractional
places. An initial exploratory expected contribution incorrectly treated PER_ORDER
50 as a per-unit charge; that expectation was corrected and was not reported as an
application defect.

Landed cost was PARTIAL with ten excluded unknown cost categories. Unit economics
READY meant calculable for the included model, not launch readiness or net profit.
Tax/GST, returns, advertising, storage and overhead remained UNKNOWN_EXCLUDED, not
zero. This run does not establish official fees, tax correctness, negative-profit
coverage, stale-input coverage or full financial certification.

## Safety, authorization and database evidence

The preceding WP0A request explicitly approved the dedicated disposable instance.
It was re-attested before use, not inferred from an arbitrary connection string:

- Exact container `vayujit-qa-postgres`, full ID
  `a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23`.
- Instance `389b97d2-a4cd-4d9b-972e-6bb2bf5785eb`, PostgreSQL 17.10,
  loopback endpoint `127.0.0.1:55432`.
- Dedicated `vayujit_qa_admin`, non-superuser CREATEDB role; no CREATEROLE,
  REPLICATION, BYPASSRLS or role memberships. Secrets stayed in the ignored,
  current-owner/SYSTEM ACL-protected QA profile, not production `.env`.
- Exact database `vayujit_qa28be28cb826accab_test`, harness-issued token,
  signed instance/lifecycle, expected owner/OID and disposable marker verified.
- API used explicit LOCAL_FIXTURE configuration, external emergency stops and
  the existing TCP egress guard. Real Angular/API requests went through the
  existing same-origin QA proxy. Live-mode supplier request was refused.
- Synthetic owner, brand, products, hypotheses, opportunity constraints, supplier
  fixture, assumed economics, inventory and decisions were created through UI or
  normal canonical APIs. No rows were manually copied from permanent data.
- This browser fixture uses `Base.metadata.create_all`: it is **not** a fresh
  migration certificate. WP0A migration evidence remains separate and unmodified.

On completion, the owned fixture server exited **0** and reported marker-verified,
signed cleanup with `database_absent: true`. A separate fresh Python process then
verified server identity, database absence and signed lifecycle **DROPPED**.
All **10 original Docker containers** matched their preflight identity/state,
image, timestamps, mounts and network attachments; original network and volume
sets were preserved. The dedicated QA PostgreSQL instance remains available;
only the token-owned disposable database was dropped. No forced session termination
or unrelated resource deletion was used.

The original instance-secret scan found zero credential/signing-key matches in
generated report documents or captured container logs. Raw container logs were
not persisted. A separate scan of this mission's JSON evidence and all four
decompressed trace archives also found zero actual instance-secret matches.
Local Playwright traces can contain **synthetic** auth/session data:
keep the ignored evidence directory private and do not commit/upload traces
without review. No real marketplace credentials were entered.

No database-authorization blocker remains for this run. Outstanding workflow
blocks are explicitly identified in the [coverage matrix](browser-journey-coverage.md).
The golden/permanent databases were not opened or modified, and backup certification
remained parked. No marketplace/supplier calls, messages, RFQs, payments, deployment,
commits, pushes or branches were performed.

## Console and network disposition

36 console error events are not 36 defects; repeated navigation and expected
HTTP failures contribute. Across the recorded browser contexts:

| Observation | Count / interpretation |
| --- | --- |
| HTTP 401 | 6, expected unauthenticated/session-boundary checks |
| HTTP 404 | 11: absent goal plan/latest run before execution and absent research projections; the projection feedback defect is SE-005 |
| HTTP 403 | 1, QA proxy refused the UI's LIVE_READ_ONLY supplier request |
| HTTP 422 | 2, investigator accidentally probed `/catalog/products`; excluded from application findings and valid screen count |
| Failed requests | 3, browser guard intentionally aborted run creation, listing-draft creation and sourcing-scenario creation |
| HTTP 5xx / uncaught page errors | 0 / 0 observed; not proof every backend path is healthy |

No raw request headers, cookies, response bodies or query-string credentials are
in the finding ledger. Supplemental API fixture calls are not counted as browser
request coverage. No general performance SLA was tested; capture navigation
timings include deliberate settling and cannot support a speed certification.

## Accessibility outcome

26 actual axe executions recorded rule/impact/target information. Confirmed:
`page-has-heading-one` (moderate) on the Catalog context-error state.

Five scans also reported serious `color-contrast` failures on the active Advanced
navigation link: reported ratio **1.07**, white over `#f4f8f7`, required **4.5**.
The screenshot shows a dark selected-link background, so this evidence is retained
as **SE-SUSPECTED-001**, requiring independent hover/focus/scroll/stacking-state
verification. It is neither a clean accessibility pass nor an established visual
root cause. No rule was suppressed.

Mobile video, opportunity, verification and economics states retain incomplete
ARIA/contrast results. The six video contrast targets were individually scrolled
into view, with focus on textareas, and rescanned; all remained incomplete. The
known generic-div ARIA targets and exact obstructed contrast elements are listed
in the local axe records. Full details and manual-review limits are in the
[coverage matrix](browser-journey-coverage.md#accessibility-and-interaction-coverage).

Mobile menu Enter/Tab/Shift+Tab/Escape and visible focus checks passed in the
tested sequence. This is not a full keyboard/screen-reader/WCAG certification.

## Evidence and reproducibility

Evidence root:
`tmp/qa-seller-browser/28be28cb826accab/` (ignored, retained after database cleanup).

| Context | State captures | Trace |
| --- | --- | --- |
| Original Chrome desktop | 31 | Not finalized: Node REPL timeout/reset; PNG/JSON survives |
| Original mobile | 1 | Not finalized for the same reason |
| Resumed Chrome desktop | 86 | `desktop-resumed/trace.zip` |
| Resumed mobile viewport | 37 | `mobile-resumed/trace.zip` |
| Edge | 5, including one invalid-route probe | `edge/trace.zip` |
| Fresh Chrome auth boundary | 2 | `auth-boundary/trace.zip` |

Each context has `browser-evidence.json`: observed state, rendered text, controls,
dimensions, action records, axe results and sanitized network paths/statuses.
Per-state JSON and PNG filenames are cross-referenced in the finding ledger.
`execution-summary.json` holds the generated route index, context counts, HTTP
status totals and per-state axe summary alongside the cleanup report.
Some early loading/race captures briefly associate an old route with a new body;
settled follow-up captures, actual URL waits and traces were used for findings.
The helper's generic visibility inventory is not a substitute for Playwright
`isVisible()` or rendered screenshot evidence.

Useful visual references:

- [Supplier mode refusal](../../../tmp/qa-seller-browser/28be28cb826accab/desktop-resumed/026-supplier-research-proxy-refusal.png).
- [Economics context](../../../tmp/qa-seller-browser/28be28cb826accab/desktop-resumed/039-economics-context-created.png).
- [Unassessed verification](../../../tmp/qa-seller-browser/28be28cb826accab/desktop-resumed/034-due-diligence-context.png).
- [Mobile video overflow](../../../tmp/qa-seller-browser/28be28cb826accab/mobile-resumed/029-mobile-video-overflow-exposed.png).
- [Stock HUMAN gate](../../../tmp/qa-seller-browser/28be28cb826accab/desktop-resumed/011-opening-stock-human-gate.png).
- [Action Center populated signal](../../../tmp/qa-seller-browser/28be28cb826accab/desktop-resumed/078-action-center-known-zero-stock.png).

### Exact local commands

From the repository root in Windows PowerShell, start only the already-approved
QA instance and attest it; do not use `-Action Create` against existing resources:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\qa-postgres.ps1 -Action Status
```

Build the actual application (working directory `apps/web`):

```powershell
& 'C:\Program Files\nodejs\node.exe' 'C:\Users\jithe\Documents\vayujit-os\node_modules\@angular\cli\bin\ng.js' build
```

Start a new owned disposable browser runtime (repo root; this generates a new
token/ports, not this run's deleted database):

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command '& .\scripts\qa-postgres.ps1 -Action Environment; & node qa/seller-browser-session.mjs'
```

The emitted `session.json` identifies only that run. Use Playwright through the
existing Node tool, import `qa/seller-browser-explore.mjs`, launch the installed
Chrome executable explicitly, call `start` with the stated viewport, and follow
the ledger's reproduction steps. Onboarding and sign-in must use the real forms.
Canonical fixture preparation steps are documented as API-assisted above; the
helper is **not** a fully automated replay of all exploratory actions.

Call `finish(run)` to finalize each context's trace and close owned browsers,
then create that exact run directory's `stop.request`. The session host requests
normal child shutdown and reports cleanup. Verify `session-final.json`, signed
DROPPED state and database absence before calling the run cleaned. Never use
generic Docker pruning or kill unrelated browser/database processes.

Open an existing trace locally:

```powershell
npx.cmd playwright show-trace .\tmp\qa-seller-browser\28be28cb826accab\desktop-resumed\trace.zip
```

Self-tests and syntax checks actually executed:

```powershell
node --test qa/unit/*.test.mjs
& .\apps\api\.venv\Scripts\python.exe -m pytest qa/unit -q
& 'C:\Program Files\nodejs\node.exe' --check qa/seller-browser-session.mjs
& 'C:\Program Files\nodejs\node.exe' --check qa/seller-browser-explore.mjs
git -c safe.directory=C:/Users/jithe/Documents/vayujit-os diff --check
```

### Actual check results

| Check | Result |
| --- | --- |
| Fresh production Angular build | PASS, 24.708s; existing 517.89kB initial bundle versus 500kB warning budget |
| Node QA harness self-tests | 49 passed, 0 failed, 0 skipped |
| Python QA guard/oracle self-tests | 48 passed, 0 failed |
| Two QA-only helper syntax checks | PASS using installed Node in the host execution environment |
| Five independent financial-value checks | PASS; bounded synthetic scenario only |
| Fresh-process signed cleanup/DB absence | PASS |
| Ten original containers and original networks/volumes unchanged | PASS |
| Instance secrets absent from documents/container-log capture | PASS, zero matches |
| Mission evidence and four trace archives checked for instance secrets | PASS, zero matches |
| Report JSON, 20 unique finding IDs, linked evidence/files and whitespace | PASS; no missing evidence references or broken file links |
| `git diff --check` | PASS; existing LF/CRLF notices, no whitespace errors |
| Full Angular suite / full historical API matrices | NOT RUN for this read-only application exploration; historical counts are not presented as current results |

Initial sandbox syntax-check attempts could not resolve the installed Node binary;
the explicit host-environment rerun passed. An initial guessed relative Angular
CLI path was absent; the actual installed root CLI built successfully. These are
tooling attempts, not application defects. Existing unit-test output includes a
deliberately induced `desktop: FAILED QA-TEST failure` while testing the reporter;
the Node runner's final result was 49/49, not an actual failing browser run.

## Files changed for this mission

- `qa/seller-browser-session.mjs`: owned, token-scoped fixture/API/web session,
  explicit shutdown and cleanup reporting, no raw subprocess output persistence.
- `qa/seller-browser-explore.mjs`: human-directed Playwright capture, axe, network
  safety, viewport records and local traces.
- The three documents/ledger in this report set.

Pre-existing changes to backup scripts, instance infrastructure, fixture guards
and other reports belong to previous work and were preserved. They were not
reimplemented or counted as this mission's production changes.

## Recommended implementation order — not implemented here

1. **Execution/context integrity:** fix SE-001 and SE-002 with canonical-mode and
   scoped-context regressions. Keep live authorization and default-deny protections.
2. **Complete the visible journey:** repair Compare fragment routing, initial DD
   assessment, and selected-opportunity conversion using existing authorities.
3. **Truthful state and recovery:** fix absent-projection messages, unexecuted
   research labels, stale shortlist count, Catalog currency/error recovery and
   authentication return routes.
4. **Seller comprehension:** prioritize economics summary, plain-language unknowns,
   rupee/percentage formatting, quantity and active-product prerequisites, secure
   image onboarding and progressive disclosure.
5. **Navigation/mobile/accessibility:** align Suppliers/My Research labels, close
   the menu on navigation, contain video overflow, fix confirmed heading semantics,
   and independently resolve all suspected/incomplete axe targets.
6. **Independent bounded retest:** extend only the reviewed synthetic QA allowlist
   as needed for blocked local workflows; never enable live acquisition to force a
   pass. Then rerun the affected persisted browser chains and negative boundaries.

**STOP:** findings reported; no seller-facing fixes, production activation or
complete application certification is authorized or claimed by this report.
