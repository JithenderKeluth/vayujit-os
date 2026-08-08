# VAYUJIT OS Product Experience Acceptance

Date: 2026-08-08
Branch: `feature/KAN-product-experience-acceptance`

## Journey tested

The disposable performance/acceptance harness exercised owner setup, brand and product creation,
product activation, deterministic AI generation, artifact approval, mock destination creation,
Campaign/activity creation, health checks, rescheduling previews, catch-up previews, scheduler
materialization, and one-shot worker claiming. Local startup also verified PostgreSQL, migrations,
FastAPI, Angular, and Electron renderer readiness. No real external connector calls were made.

## UX issues found and fixed

- Settings described available provider/connector choices as “Unsupported controls”. This was
  replaced with user-facing guidance to use the dedicated provider and connector settings pages.
- Release readiness documentation still described Recovery as 19 implemented plus 2 unsupported. It
  now records 21 implemented actions and 0 unsupported actions, with no legacy dispatch.

## Acceptance results

- Launch/first use: PASS. PostgreSQL, migrations, API health, Angular origin, and Electron smoke all
  succeeded. Existing owner state correctly reports setup complete.
- Navigation: PASS by route and shell inspection. The authenticated shell exposes Dashboard, Brands,
  Products, Campaigns, Calendar, AI, Media, Publishing, Workflows, Approvals, Operations, History,
  and Settings with active-route styling and mobile navigation.
- Dashboard: PASS. Operational metrics and quick actions cover approvals, executions, workflows,
  products, content generation, publishing, and history.
- Empty states: PASS by component inspection. Brands, Products, Media, AI, Campaigns, destinations,
  approvals, schedules, jobs, workers, recovery, and backups provide next-step or safe empty copy.
- Brand/Product/Media/AI/Artifact/Approval/Publishing/Workflow/Campaign/Calendar/Recovery/Settings:
  PASS through existing unit, integration, E2E, and component coverage plus route/template review.
- Error and confirmation behavior: PASS in covered flows. Reschedule and catch-up dialogs preserve
  input, refresh stale previews, expose safe errors, and require confirmation; destructive publishing,
  approval, archive, and recovery actions retain guarded paths.
- Loading and duplicate-submit protection: PASS in covered Angular services/components and API tests.
- Search/filter/pagination: PASS by component review and existing list tests across core tables.
- Responsive/theme/accessibility: PASS for existing Angular template lint rules, focus styles, mobile
  navigation, dark/light tokens, and keyboard file-picker coverage. Manual visual and assistive-tech
  verification was not available in this environment.
- State persistence: PASS through server-backed auth/preferences and database integration coverage;
  authoritative business state is not stored in localStorage.
- Performance: PASS. `performance:baseline` completed with reschedule preview median 37.9 ms (p95
  44.6 ms), catch-up preview median 36.2 ms (p95 37.8 ms), scheduler materialization median 5.7 ms
  (p95 11.8 ms), and worker claim median 5.9 ms (p95 14.8 ms).

## Remaining limitations

- Browser-control runtime could not be started, so a live browser screenshot/session walkthrough at
  390px, 768px, and 1280px and screen-reader verification remain manual follow-up work.
- Two Angular lint warnings remain for missing `OnInit` interface declarations in catch-up and
  reschedule dialogs; they are non-blocking.
- System Doctor warns that AI and Publishing credential encryption keys are not configured, so real
  provider/connector credentials remain intentionally disabled on this personal machine.
- License visibility reports unknown internal/runtime licenses; no GPL/AGPL flags were found.
- Public Windows signing remains deferred to external distribution and is outside this milestone.

## Regression result

- Web: 18 files, 62 tests passed.
- Desktop: 4 tests passed; Electron smoke passed with sandbox enabled and `app://vayujit` renderer.
- API unit: 111 passed.
- Campaign rescheduling: 18 passed.
- Campaign catch-up: 8 passed, 1 skipped.
- Campaign Recovery: 6 passed.
- Campaign connector E2E: 2 passed.
- Campaign workflow: 6 passed.
- Scheduler integration: 7 passed.
- Worker tests: 2 passed.
- Migration cycle: passed through revision `20260812_0022` with downgrade/re-upgrade checks.
- Ruff, Black, mypy, ESLint, build, format check, security audit, and `git diff --check`: passed.
- The first combined `npm.cmd run test:all` attempt exceeded its five-minute timeout while the
  development stack was running; the complete focused matrix above passed after stopping only the
  acceptance-launched processes.

## Personal-machine decision

**PERSONAL MVP GO**, with the manual browser/assistive-tech limitations above. The core local journey,
safe operational flows, persistence, packaging smoke test, and regression gates are green. Public
Windows signing remains **DEFERRED UNTIL EXTERNAL DISTRIBUTION**.