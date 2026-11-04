# WP6 — Quality debt and release risk

## WP6B follow-up — 2026-10-30

[WP6B remediation](wp6b-remediation.md), [precision/history decision](wp6b-financial-precision-policy.md)
and [manual accessibility review](wp6b-accessibility-review.md) classify the remaining
risks and record bounded financial/caption/semantic fixes. The isolated Ads502 is
still unreproduced/cause unclassified, not silently closed. Original entries below
remain historical. Follow `wp6b-quality-gate.json` for the final WP7 testing-only
recommendation and actual cleanup/test results. Application certification INCOMPLETE;
no business launch, provider permission or WP7 execution is inferred.

2026-10-30. **Application certification INCOMPLETE.** Passing UI assertions do not
override actual API failures, monetary/history gaps or incomplete accessibility.
No owner acceptance of these risks is inferred. Stop before WP7.

## WP6A follow-up disposition — 2026-10-30

The service blocker table below records the original WP6 state. It is preserved
as history, not the current status of the two schema defects. **SE-WP6-VIDEO-001
and SE-WP6-ADS-001 are now locally resolved** by new revisions148/149 and fresh,
populated-upgrade, rollback, persisted API and Chrome/Edge evidence in
[WP6A remediation](wp6a-schema-remediation.md). The isolated502 was not reproduced;
its cause remains unclassified. No production or provider execution certification.
Remaining schema/index inventory debt, monetary/history gaps and manual axe
incompletes are explicit in that report. Application certification stays INCOMPLETE.

## High-priority service blockers

| ID / priority | Actual evidence and impact | Required bounded follow-up |
| --- | --- | --- |
| SE-WP6-VIDEO-001, HIGH/P1, OPEN | Actual `/api/v1/ai/video/generations`500 in Chrome/Edge; Video unavailable, Social video read also unavailable. Signed fresh migration-backed schema has storyboardversion/styleversion while ORM selects storyboard_version/style_version. | Reviewed data-preserving corrective migration, populated historical-data upgrade/rollback and canonical list/owner-isolation tests. Do not simply edit old migration, recreate tables or return[] on SQL failure. No video generation was certified. |
| SE-WP6-ADS-001, HIGH/P1, OPEN | Actual Ads overview500. AdCampaign ORM selects correlation_id/failure_category/next_retry_at/retry_after_seconds absent from migrated ad_campaigns. Ads optimization/anomalies/comparison also failed. | Inventory migration/model history, choose safe nullable/default semantics for historical rows, test upgrades/downgrades and supported owner-scoped reads. Missing columns directly block ORM campaign reads; full causality of every optimization endpoint not established. |
| SE-WP6-ADS-502-001, MODERATE/P2, OBSERVED_UNCLASSIFIED | Final Edge comparison request returned502 once in addition to500s. | Correlate a fresh bounded API/proxy failure without secrets. Do not assume schema correction alone proves proxy recovery. No raw subprocess output retained. |

Exact safe column diagnostic: `tmp/qa-seller-browser/4e7c1b34606df874/wp6-schema-drift.json`.
It verifies instance, signed ACTIVE lifecycle, owner/OID, marker and READ ONLY transaction;
only known column names, no customer records/credentials. A first attempted probe after
the broad run had already cleaned correctly refused non-ACTIVE state, before connecting
to the removed target. The successful final probe ran before cleanup.

Video migration root: `20260904_0048_ai_video_slice2.py` uses
`f"{name[:-3]}version"` for names storyboard_id/style_id, omitting the separator.
This was historically recorded in PR-SOS-01.4; WP6 confirms both affected columns.
Shared startup/Catalog do not require this table. These schema changes require
reviewed migration/data compatibility, not an unexamined UX patch to force green.

## Monetary correctness and history

**SE-WP5-PRICE-001 — MEDIUM/P2, display mitigated / precision contract OPEN.**
Input Decimal precision exceeds the two-decimal order-item model. Source100.125×2
becomes200.25 recorded total; stored unit100.13×2 would be200.26. This is not FX.
No new amount was invented; canonical Decimal arithmetic unchanged. UI warning and
new persisted regression prevent pretending rounded projection reconstructs total.
Before changing persisted semantics, approve currency/source precision rules,
rounding stage, source-line correlation, historical compatibility and migration.
It remains unsuitable to claim complete accounting reconciliation from unit display.

**QA-P3-GAP-001 — OPEN capability gap.** FinancialCalculationSnapshot is a mutable
current projection per scope/calculation version. Recalculation replaces its metrics/
lineage; source event immutability does not make snapshots an accounting journal.
UI explicitly differentiates this. A full journal/history architecture is outside
WP6 and requires separate approval. Do not reinterpret missing cost/fee/GST as zero.

**QA-P3-GAP-002 — OPEN.** Action Center remains advisory/local notice lifecycle;
there is no new generic execution engine. Canonical artifact-specific HUMAN approval,
stale/version/authorization controls continue to own consequential actions.

## Accessibility / usability

- Broad96 and final30 real axe scans have zero violations but45 and21 incomplete
  node occurrences respectively. Retain exact conditional ARIA, empty tables,
  calendar children and obscured contrast nodes in browser evidence. Repeated states
  are not unique bugs. No rule suppression, narrowed WCAG threshold or fake PASS.
- Six focused Catalog textarea pairs measured14.80:1 with unobscured centers and
  focus outlines. This improves the prior manual gap but does not replay the old
  inline mutation-error occurrence or clear every historical manual-review item.
- Shared mobile/Advanced representative link measured12.37:1; corresponding dark
  palette is reused across menu links. Full dark/light-theme/high-contrast/hover/
  focus/screen-reader and low-vision task review remains unexecuted.
- Long economics/research/creative pages, technical IDs and compliance JSON remain
  first-time-seller friction. Current WP6 fixes spacing, precise prerequisites and
  route continuity; no unrestricted redesign or new workflow was authorized.
- Read-only route review is not end-to-end testing of every conditional form,
  populated campaign, provider failure, dialog or approval/revocation transition.
- Autonomous and Video overflow fixes retain all controls and table content; no
  hidden-offscreen-content shortcut or mission/provider execution was used.

## Technical warnings

Resolved locally: unsupported inventory `Field(ne=0)` replaced with explicit
nonzero validator; old in-memory contract demonstrably accepted0, new API422 does
not change stock/version. Strict schema mypy passes without suppression.

Resolved initial bundle warning: lazy-load existing Advertising components instead
of eager imports; **422.71kB** versus prior519.17kB, unchanged500kB budget. No
dependency upgrade or disabled budget. Ads data failures are independent of route
loading and remain blockers, not proof the lazy-loading change lost routes.

Older sourcing-service29 diagnostics and economics-router42/43 historical baselines
from WP3/4 are not reclassified clean by a focused schema check. Full repository lint,
typing, performance/load and all migrations' existing-data compatibility were not
recertified. Existing FastAPI on_event/duplicate operation-ID warnings remain.

One earlier WP6 cleanup was interrupted; existing exact-token signed DROPPING
recovery at90seconds succeeded. Engine-level cause not established from retained
diagnostics. All6 WP6 DBs subsequently independently absent; final backend/broad/
focused runs cleaned normally. Harness reliability under host stalls is a limitation,
not permission to drop a guessed prefix or terminate unrelated sessions.

## Stop / owner decisions

Scoped original009/017/020 are browser-resolved. Release/quality closure still needs
safe Video/Ads migration repair and retest, precise treatment of the monetary/history
limitations, remaining manual accessibility scope and the separately parked PC-first
backup/activation gates. No production activation, live provider authorization,
marketplace write or WP7 is authorized by this report. No branches, commits or pushes.
