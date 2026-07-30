# Shopify final acceptance

This slice completes the local acceptance design for bounded media processing, verified reuse,
managed assignment removal, and a three-option variant matrix. It does not add inventory quantity
writes, remote Product deletion, automatic variant deletion, automatic collection removal, or
automatic publication removal.

## Media lifecycle

Remote mappings are persisted as soon as Shopify returns a media ID. The API then uses the
predefined `VayujitMediaStatus` operation and records each observation. Polling defaults to 60
seconds, 12 attempts, a one-second initial interval, and a five-second maximum interval. The clock,
delay, cancellation predicate, and observation sink are injectable so tests never sleep.

Only a mapping verified against the owner, destination, shop fingerprint, local checksum, expected
remote Product, remote existence, and a `READY` state is reusable. Other typed decisions are
`stale`, `missing`, `processing`, `failed`, `inaccessible`, and `unknown`. A local cancellation
stops polling but is not a remote cancellation and never deletes remote media.

Recovery may offer polling, verification, re-upload, continue-without-media, or preservation of a
degraded draft according to the destination policy. No fabricated percentage progress is shown.

## Assignments

Collection and publication assignments carry owner, destination, local Product, remote Product,
target, management attribution, status, and verification timestamps. Removal always refreshes
remote state, previews managed candidates, requires an explicit confirmed selection, and preserves
unrelated assignments. Removing a required publication records a partial-publication state. It is
an unpublish operation, never Product deletion.

## Variant matrix

The Angular editor supports one to three named dimensions and a maximum of 100 combinations.
Blank/duplicate names, blank/duplicate values, and over-limit matrices are blocked. Regeneration
preserves entered commerce data and stable keys for equivalent combinations. The user must confirm
when combinations would be removed. Inventory tracking metadata is supported; quantities are not.

## Local acceptance

The standalone fake binds only to loopback, rejects unknown operations, and models media state,
collection membership, and publication membership. Run the guarded Shopify tests independently:

```powershell
cd apps\api
.\.venv\Scripts\pytest.exe tests\test_shopify_completion.py tests\test_shopify_final_acceptance.py
```

Manual browser and actual-window Electron validation remain separate activities. Automated checks
must never be reported as manual visual validation. A real Shopify store is optional and is never
contacted by automated acceptance.

The current Electron harness validates production startup, renderer loading, sandboxing, context
isolation, and disabled Node integration. It does not expose a renderer automation driver or a
test-only IPC bridge, so it cannot safely click through the 20-step Shopify UI journey. Adding a
generic network/filesystem bridge would weaken the security model. Until a narrowly scoped
Playwright Electron fixture is adopted, the actual-window Shopify interaction flow remains a
documented manual acceptance step rather than a claimed automated pass.

## Incident response

For timed-out or ambiguous media, do not repeat creation blindly. Reconcile the remote Product,
verify the mapped ID, and then either reuse a verified-ready mapping or explicitly re-upload.
For assignment drift, preserve remote-only membership, preview the selected VAYUJIT-managed
removal, confirm it, reconcile, and repair any required publication before activation.

Safe audit events contain status/count metadata only. Tokens, staged-upload credentials, raw
multipart fields, GraphQL text, descriptions, bytes, and local paths are prohibited.
