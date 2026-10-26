import { certificationStatus } from './safety.mjs';
import { phase4CleanupComplete } from './phase4-report.mjs';

export const stockIds = Array.from({ length: 8 }, (_, n) => `QA-P4B-0${n + 1}`);
export const stockStates = [
  'genuine-empty',
  'no-products',
  'entry',
  'review',
  'saved',
  'ledger',
  'invalid',
  'restored-review',
  'uncertain-save',
  'conflict',
  'search-error',
  'saved-deep-link',
  'unknown-item',
];
export function openingStockComplete(report) {
  return (
    phase4CleanupComplete(report.cleanup) &&
    certificationStatus(report.reports, report.cleanup, 8) === 'PASS_BOUNDED_SMOKE' &&
    ['desktop', 'mobile'].every((project) => {
      const group = report.reports.filter((r) => r.tests.every((t) => t.project === project));
      if (group.length !== 1) return false;
      const tests = group[0].tests;
      const scans = tests.flatMap((t) => t.axe || []);
      return (
        stockIds.every(
          (id) => tests.filter((t) => t.id === id && t.status === 'passed').length === 1,
        ) &&
        scans.length === stockStates.length &&
        stockStates.every(
          (state) =>
            scans.filter(
              (s) => s.state === 'axe-' + state && s.violations.length === 0 && s.passes > 0,
            ).length === 1,
        )
      );
    })
  );
}
