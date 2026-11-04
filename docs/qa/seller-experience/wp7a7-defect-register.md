# WP7A-7 defect register

This is an additive record. Earlier failures, acceptance requirements and WP7A-6
recovery evidence are retained. Completion is controlled by the coverage ledger
and gate, not by the presence of a fix in this table.

| ID | Confirmed root cause | Bounded correction | Required independent retest |
|---|---|---|---|
| A7-SOCIAL | Image-only approval was not exposed as an explicit exact-preview HUMAN action. Concurrent edits/replays were not serialized consistently. | Existing approval authority receives the reviewed fingerprint; UI requires explicit review and does not schedule/publish. Owner/post locks preserve identity. | Chrome/Edge 1440/390, stale caption, failed save/retry, concurrent replay, reload, no publication. |
| A7-AMAZON | Generic listing creation called the connector and presented an active remote result; local variant/price preparation was not supported. First local price insert omitted required timestamps. Price/media/variant changes were absent from review identity. | Opt-in `prepare_only` uses the same listing authority without a connector; local PUT writers persist canonical inputs; UNKNOWN prices remain null; the existing fingerprint includes preparation inputs. | Actual create/editor, missing prerequisites, legitimate correction, exact review/auth, expiry/revocation/staleness, replay and no submission. |
| A7-MEESHO | Pricing required a remote listing before the missing-price prerequisite could be resolved. | Existing pricing authority accepts an unpublished local draft without connector execution; manual/unavailable-live state stays truthful. | Actual editor pricing, readiness, reload, validation and no dispatch. |
| A7-CONTEXT | Listing editors could retain an account selected from the list rather than the exact listing's account. Saved prices/variants and readiness were not consistently reloaded after writes. | Pin the existing listing's account/product/artifact and reload the authoritative preparation state. | All three editors, reload, exact identifiers, invalid/anonymous resources. |
| A7-HYDRATION | The asynchronous local-price load could finish after a seller began editing, clearing values, or overwrite the price of a newer selection. The four-context browser run reproduced Meesho HTTP 422; two deterministic Angular tests reproduced premature PUT and wrong-context overwrite. | Keep pricing controls and submission blocked until hydration finishes; discard old selection responses. Apply the equivalent guard to Flipkart; preserve null UNKNOWNs. | Both original Meesho regressions now pass (6/6 focused tests). Final full Angular and browser retests are recorded in the closure report. |
| A7-FLIPKART | Authorization issuance did not re-evaluate readiness after account disable. Expired issued rows were displayed as issued. Conflicting replay keys could reuse a different review. | Recheck canonical readiness; derive expired display from the existing expiry timestamp without rewriting history; reject conflicting replay. Same expiry/replay projection correction applies to Amazon. | Disable-after-review regression plus browser revocation, renewal, expiry, stale review and concurrency. |
| A7-CAMPAIGN | Existing reschedule fingerprint omitted persisted dependency edges. | Include sorted owned dependency identities/types/release state in the existing fingerprint; no new approval authority. | Dependency change must change fingerprint and reject old confirmation; explicit fresh confirmation, recovery and durable no-release proof. |
| A7-ADS | Wizard readiness used an all-zero campaign ID without prospective account context. Campaign preview/confirmation omitted the selected creative. | Reuse the existing creative validator with an owned prospective account; bind selected creative and credential version into preview. Persist creative, budget, campaign and queued intent atomically through existing authorities after HUMAN confirmation. | Content/image identity, missing/disabled account, changed creative, explicit confirmation, concurrent replay, recovery, reload and no spend. |

## Harness defects are not application defects

- A wrapped select's accessible name includes option text; exact-label selection
  can time out despite a usable control. Use its existing stable form-control name.
- Legacy product-content fixtures must use their matching generation authority;
  Studio's typed regeneration contract is not interchangeable with legacy types.
- Interrupted synthetic state must be explicitly labelled and marker/token/owner
  guarded. It is not evidence that a real worker or provider previously executed.
- API assertions must follow the actual `lineage` response contract, not invented
  top-level creative fields.
- Router/dialog interception must not register two handlers for the same event.
- Fixture destination names must include the browser context; a name reused across
  four contexts correctly causes the canonical unique-name conflict.
- Generic Campaign recovery exposes rescheduling for the represented `missed`
  state, not arbitrary failed intents. The synthetic missed fixture uses a past
  schedule in a matching Campaign window, with no claimed worker execution.

## Boundaries and retained observations

Image identity is the approved immutable Output UUID and matching Media UUID,
checksum, dimensions and size. The existing consumer `image_version` field is not
a new authoritative source version counter. Real provider token expiry remains
UNVERIFIED under the explicitly approved L-17 clarification.

The legacy product-content/Studio regeneration request returned 500 in an earlier
attempt. The fixture now uses its matching legacy authority; that does **not**
certify the incompatible Studio route as repaired. Historical Ads 502, PostgreSQL
lifecycle timestamps, manual accessibility, repository-wide typing/lint debt,
financial history/reconciliation limits and parked backup certification are not
resolved by this package.
