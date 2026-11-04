import { phase4CleanupComplete, phase4Status } from './phase4-report.mjs';
import { canonicalRoute } from './phase4-surface.mjs';
import { phase3ApiComplete, certificationStatus } from './safety.mjs';

export const focusedIds = ['QA-P4A-01', 'QA-P4A-02', 'QA-P4A-03'];
export const nodePassed = (node) =>
  node.text_horizontally_in_view === true &&
  node.violations.length === 0 &&
  node.incomplete.length === 0 &&
  node.passes.includes('color-contrast');

export function focusedComplete(report) {
  return (
    phase4CleanupComplete(report.cleanup) &&
    certificationStatus(report.reports, report.cleanup, 3) === 'PASS_BOUNDED_SMOKE' &&
    report.reports.every(
      (r) =>
        phase3ApiComplete(r.api_results) &&
        focusedIds.every(
          (id) => r.tests.filter((t) => t.id === id && t.status === 'passed').length === 1,
        ),
    )
  );
}

// This gate consumes actual executions, not the report's self-declared PASS label.
// No unreviewed finding, usability proposal or unrelated workflow can be closed.
export function resolutionDecisions({
  baseline,
  original,
  full,
  focused,
  routes,
  nodes,
  hashesVerified,
}) {
  const ready =
    hashesVerified === true &&
    focusedComplete(focused) &&
    phase4Status(full, routes) === 'PASS_BOUNDED_EXPLORATION';
  const scans = full.reports.flatMap((r) =>
    r.tests.flatMap((t) =>
      (t.axe || []).map((s) => ({ ...s, project: t.project, test_id: t.id, evidence: t.evidence })),
    ),
  );
  const captionNodes = nodes.filter(
    (n) => n.suite === 'focused' && /^node-review-(due|economics|stale|decision)-/.test(n.name),
  );
  const captionComplete =
    ready &&
    captionNodes.length === 48 &&
    ['desktop', 'mobile'].every((project) =>
      [360, 390, 768, 1440].every((width) => {
        const group = captionNodes.filter(
          (n) => n.project === project && n.viewport.width === width,
        );
        return (
          group.length === 6 &&
          new Set(group.map((n) => n.name)).size === 6 &&
          group.every(nodePassed)
        );
      }),
    );
  const financial = nodes.filter(
    (n) => n.suite === 'original' && n.name.startsWith('node-review-financial-'),
  );
  const financialComplete =
    ready &&
    financial.length === 8 &&
    ['desktop', 'mobile'].every((project) => {
      const group = financial.filter((n) => n.project === project);
      return (
        group.length === 4 &&
        new Set(group.map((n) => n.name)).size === 4 &&
        group.every(nodePassed)
      );
    });
  return baseline.findings.map((finding) => {
    const row = {
      id: finding.id,
      resolved: false,
      reason: 'Unrelated open finding retained',
      after: [],
    };
    if (!ready) return { ...row, reason: 'Independent execution, hash or cleanup gate incomplete' };
    if (finding.id.startsWith('QA-P4-AXE-')) {
      const rule = JSON.parse(finding.actual).id;
      const relevant = scans.filter((s) => canonicalRoute(s.route) === finding.route);
      row.resolved =
        ['desktop', 'mobile'].every((project) => relevant.some((s) => s.project === project)) &&
        relevant.every((s) => ![...s.violations, ...s.incomplete].some((v) => v.id === rule));
      if (rule === 'color-contrast' && finding.route === '/intelligence/websites') {
        const targeted = nodes.filter(
          (n) =>
            n.suite === 'focused' &&
            n.route === finding.route &&
            n.name.startsWith('node-review-state-contrast-'),
        );
        row.resolved =
          ['desktop', 'mobile'].every(
            (project) =>
              relevant.some((s) => s.project === project) &&
              ['state-high', 'state-expired'].every((state) => {
                const matches = targeted.filter(
                  (n) =>
                    n.project === project &&
                    n.name.startsWith(`node-review-state-contrast-${state}-`),
                );
                return matches.length > 0 && matches.every(nodePassed);
              }),
          ) && relevant.every((s) => !s.violations.some((v) => v.id === rule));
        row.targeted_after = targeted.map((n) => ({
          project: n.project,
          name: n.name,
          evidence: n.evidence,
        }));
      }
      if (rule === 'aria-prohibited-attr' && finding.route === '/ai/video') {
        const witnesses = focused.reports
          .flatMap((r) => r.tests)
          .filter(
            (t) =>
              t.id === 'QA-P4A-01' &&
              t.status === 'passed' &&
              t.evidence.some((e) => e.name === 'semantics-assertions') &&
              t.axe.some(
                (s) => s.route === '/ai/video' && !s.violations.some((v) => v.id === rule),
              ),
          );
        row.resolved =
          ['desktop', 'mobile'].every(
            (project) =>
              witnesses.some((t) => t.project === project) &&
              relevant.some((s) => s.project === project),
          ) &&
          relevant.every(
            (s) =>
              !s.violations.some((v) => v.id === rule) &&
              !s.incomplete.some(
                (v) => v.id === rule && v.nodes.some((n) => n.target.includes('.progress')),
              ),
          );
        row.targeted_after = witnesses.map((t) => ({
          project: t.project,
          test_id: t.id,
          evidence: t.evidence.filter(
            (e) => e.name === 'semantics-assertions' || e.name === 'axe-semantics--ai-video',
          ),
        }));
      }
      row.rule = rule;
      row.after = relevant.map((s) => ({
        project: s.project,
        route: s.route,
        state: s.state,
        test_id: s.test_id,
        evidence: s.evidence.filter(
          (e) => e.name === s.state || e.name === 'final-screen' || e.name === 'trace',
        ),
      }));
      row.reason = row.resolved
        ? row.targeted_after?.length
          ? 'Original affected selectors/semantics independently verified in both viewports; unrelated full-document incompletes retained'
          : 'Original route/rule independently clear in both isolated viewports'
        : 'Rule remains incomplete, violated or unexecuted in at least one viewport';
    } else if (
      finding.id === 'QA-P4-A11Y-CAPTION-CLIPPING' ||
      finding.id === 'QA-P3-A11Y-REVIEW-001'
    ) {
      row.resolved =
        captionComplete && (finding.id !== 'QA-P3-A11Y-REVIEW-001' || financialComplete);
      row.after = [
        ...captionNodes,
        ...(finding.id === 'QA-P3-A11Y-REVIEW-001' ? financial : []),
      ].map((n) => ({
        project: n.project,
        name: n.name,
        viewport: n.viewport,
        evidence: n.evidence,
      }));
      row.reason =
        'Exact six captions at four widths in both contexts; historical ticket additionally requires eight financial-header reviews. No global WCAG claim.';
    } else if (finding.id.startsWith('QA-P4-ASSERT-')) {
      const previous = original.reports
        .flatMap((r) => r.tests)
        .filter(
          (t) =>
            t.status !== 'passed' &&
            finding.evidence.some((e) => t.evidence.some((ref) => ref.path === e.path)),
        );
      row.resolved =
        previous.length === 1 &&
        full.reports.some((r) =>
          r.tests.some(
            (t) =>
              t.id === previous[0].id && t.project === previous[0].project && t.status === 'passed',
          ),
        );
      row.after = previous.map((t) => ({ project: t.project, test_id: t.id }));
      row.reason =
        'Overlapping failed-scenario record; original assertions rerun, not a separate business defect';
    }
    return row;
  });
}
