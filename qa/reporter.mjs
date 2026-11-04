import fs from 'node:fs';
import path from 'node:path';
import { stripVTControlCharacters } from 'node:util';
import { finding } from './safety.mjs';

export default class QaReporter {
  rows = [];
  onBegin(_config, suite) {
    console.log(`QA collected ${suite.allTests().length} browser scenarios.`);
  }
  onTestEnd(test, result) {
    const project = test.parent.project().name;
    const persisted = result.attachments.map((attachment, index) => {
      if (attachment.path || !attachment.body) return attachment;
      const extension =
        attachment.contentType === 'application/json'
          ? 'json'
          : attachment.contentType === 'image/png'
            ? 'png'
            : 'txt';
      const folder = path.join(
        path.dirname(process.env.QA_REPORT_PATH),
        'evidence',
        `${project}-${test.title.split(' ')[0]}`,
      );
      fs.mkdirSync(folder, { recursive: true });
      const file = path.join(
        folder,
        `${index}-${attachment.name.replaceAll(/[^a-zA-Z0-9-]/g, '-')}.${extension}`,
      );
      fs.writeFileSync(file, attachment.body);
      return { ...attachment, path: file };
    });
    const evidence = persisted
      .filter((a) => a.path)
      .map((a) => ({
        name: a.name,
        path: path.relative(process.cwd(), a.path).replaceAll('\\', '/'),
      }));
    const telemetry = persisted.find((a) => a.name === 'network-and-console');
    const signals = telemetry?.path ? JSON.parse(fs.readFileSync(telemetry.path, 'utf8')) : null;
    const axe = persisted
      .filter((a) => a.name.startsWith('axe-') && a.path)
      .map((a) => ({ state: a.name, ...JSON.parse(fs.readFileSync(a.path, 'utf8')) }));
    const usability = persisted
      .filter((a) => a.name === 'ux-observations' && a.path)
      .flatMap((a) => JSON.parse(fs.readFileSync(a.path, 'utf8')));
    this.rows.push({
      id: test.title.split(' ')[0],
      title: test.title,
      project,
      status: result.status,
      duration_ms: result.duration,
      steps: result.steps
        .filter((s) => s.category === 'test.step')
        .map((s) => ({ title: s.title, status: s.error ? 'FAIL' : 'PASS' })),
      error: result.errors.map((e) =>
        stripVTControlCharacters(e.message || 'Assertion failure').slice(0, 1800),
      ),
      evidence,
      signals,
      axe,
      usability,
    });
    console.log(`${project}: ${result.status.toUpperCase()} ${test.title}`);
  }
  onEnd(result) {
    const findings = this.rows
      .filter((r) => !['passed', 'skipped'].includes(r.status))
      .map((r, i) =>
        finding(`QA-RUN-${r.project.toUpperCase()}-${String(i + 1).padStart(3, '0')}`, {
          feature: r.title,
          route: 'See screenshot/trace; failure may be in test harness',
          type: 'SUSPECTED_DEFECT',
          severity: 'MAJOR',
          priority: 'P1',
          expected: 'Scenario assertions pass using canonical disposable data.',
          actual: r.error.join('\n'),
          reproduction_steps: [`npm.cmd run qa:smoke`, `Inspect ${r.id} (${r.project})`],
          evidence: r.evidence,
          confidence: 'SUSPECTED',
          suggested_fix:
            'Triage assertion, locator and application evidence before requesting a production fix.',
          retest_status: 'NOT_RETESTED',
        }),
      );
    const confirmed = this.rows.flatMap((r) =>
      r.axe.flatMap((state) =>
        state.violations.map((violation) =>
          finding(
            `QA-AXE-${r.project.toUpperCase()}-${state.state.toUpperCase()}-${violation.id.toUpperCase()}`,
            {
              feature: state.state,
              route: state.route,
              type: 'ACCESSIBILITY',
              severity: ['critical', 'serious'].includes(violation.impact) ? 'MAJOR' : 'MODERATE',
              priority: 'P1',
              expected: `No axe ${violation.id} violation in this state.`,
              actual: JSON.stringify(violation),
              reproduction_steps: [
                'npm.cmd run qa:smoke',
                `${r.id}: ${state.state} (${r.project})`,
              ],
              evidence: r.evidence,
              confidence: 'CONFIRMED',
              suggested_fix:
                'Review the recorded axe targets and remediation; authorize an application fix separately. Automated rule finding is not complete WCAG certification.',
              retest_status: 'NOT_RETESTED',
            },
          ),
        ),
      ),
    );
    const report = {
      schema_version: 1,
      generated_at: new Date().toISOString(),
      mode: 'DISPOSABLE_SYNTHETIC_NO_PROVIDER_CALLS',
      status: result.status,
      executive_summary: {
        passed: this.rows.filter((r) => r.status === 'passed').length,
        failed: findings.length,
        skipped: this.rows.filter((r) => r.status === 'skipped').length,
        complete_application_coverage: false,
      },
      tests: this.rows,
      findings,
      confirmed_bugs: confirmed,
      usability_findings: this.rows.flatMap((r) =>
        r.usability.map((item) => finding(item.id, { ...item, evidence: r.evidence })),
      ),
      missing_flows: [
        'Full product discovery → HUMAN selection → supplier → due diligence → economics',
        'Inventory/orders/settlements deterministic calculation matrix',
        'Media/private preview and marketplace authorization browser matrix',
      ],
      blocked_tests: [
        'Real-provider and external execution intentionally forbidden',
        'Cross-installation foreign-ID and full migration certification not in initial smoke suite',
      ],
      limitations: [
        'Existing tests inventoried, not rerun by this report.',
        'Axe only covers scanned states and does not establish WCAG conformance.',
        'ORM schema fixtures do not certify the migration chain.',
      ],
    };
    const target = process.env.QA_REPORT_PATH;
    if (!target && this.rows.length === 0) return; // Offline --list only.
    if (!target) throw new Error('QA_REPORT_PATH_REQUIRED');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, JSON.stringify(report, null, 2));
  }
}
