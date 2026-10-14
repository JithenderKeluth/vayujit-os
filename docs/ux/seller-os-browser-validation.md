# Seller OS browser validation — PR-UX-01A.1

## Environment (PR-UX-01A.2)

The repository does not include Playwright, Puppeteer, or a browser-test
runner. Windows Chrome 154.0.8037.98 is installed, so PR-UX-01A.2 used its
headless DevTools Protocol in an isolated user-data directory. This is a real
Chrome render, not an HTTP-only check and not a mocked Angular test.

Generated screenshots and geometry output are kept temporarily under
`tmp/ux-browser/` and are intentionally ignored rather than committed.

## Scenarios exercised

| Scenario | Result | Evidence |
| --- | --- | --- |
| Angular application initialization | PASS | Chrome rendered `/login` at all five viewports |
| Login surface and error state | PASS | Login form, labels, disabled submit, and API error state rendered |
| Responsive breakpoints | PASS | 360, 390, 768, 1024, and 1440px captures |
| Horizontal overflow | PASS | `document.body.scrollWidth === innerWidth` at every viewport |
| Mobile clipping regression | FIXED | Auth panel changed to `width: 100%; max-width: 28rem`; 360px panel measured 328px inside a 360px viewport |
| Protected direct deep link | PASS | `/dashboard` without credentials resolved to `/login`; no shell or navigation rendered |
| Protected-route refresh boundary | PASS | A fresh isolated Chrome context reproduced the same `/login` boundary |
| Authenticated dashboard/navigation | PASS | Disposable owner created through the normal `/setup` form; dashboard, Business Agent, Product Opportunities, and Trend Intelligence rendered with the shared shell |
| Goal and opportunity context | PASS | Disposable goal created through Business Agent; Product Opportunities retained the goal context and truthful zero-product empty state with next-step links |
| Refresh and history | PASS | Authenticated refresh preserved the shell; app-link history back/forward returned between dashboard and Business Agent |
| Logout and protected deep-link boundary | PASS | Log out returned to `/login`; direct Business Agent navigation while unauthenticated resolved back to `/login` with no shell |
| Keyboard and skip-link interaction | PASS | Authenticated skip link and primary navigation received focus with a visible 3px outline; Angular accessibility tests cover shared state primitives |

## Historical auth-surface viewport measurements

The final Chrome run measured the following values:

| Viewport | Document width | Scroll width | Auth panel |
| ---: | ---: | ---: | ---: |
| 360 × 900 | 360 | 360 | 328px |
| 390 × 900 | 390 | 390 | 358px |
| 768 × 1000 | 768 | 768 | 448px |
| 1024 × 1000 | 1024 | 1024 | 448px |
| 1440 × 1000 | 1440 | 1440 | 448px |

## Authenticated shell measurements

The authenticated shell had no horizontal overflow at the five target sizes:

| Viewport | Inner width | Document/scroll width | Shell |
| ---: | ---: | ---: | --- |
| 360 x 900 | 360 | 345 | present |
| 390 x 900 | 390 | 375 | present |
| 768 x 1000 | 768 | 753 | present |
| 1024 x 1000 | 1024 | 1009 | present |
| 1440 x 1000 | 1440 | 1425 | present |

## Constraints and follow-up

- No supplier acquisition, supplier contact, RFQ, marketplace write, purchase,
  payment, golden-database change, commit, push, PR-UX-01B–F work, or PR-9C
  work was performed.
- The disposable database was `vayujit_ux_browser_test`, marked with the
  repository test-database marker, migrated to head, and dropped after the
  run. The golden database was not opened or modified.
- The local owner model intentionally supports one owner per workspace, so a
  second-owner browser comparison is not applicable. Owner-scoping remains
  covered by the existing backend authentication/authorization regression
  suite; no second identity was fabricated in the UI.
- Session-expiry was exercised at the protected-route boundary after logout;
  an in-session timeout timer is not exposed by the local UI, so no timer
  behavior is inferred.
- The existing API static-check baseline and 507.67 kB initial bundle warning
  remain tracked separately; neither was introduced by the browser fix.
# PR-UX-01A.2 authenticated browser certification
