import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Do not parse persisted Python/dictionary diagnostics into business facts.
 * Preserve their exact text as audit evidence, with a separate presentation label.
 * This cannot change readiness fingerprints or invalidate HUMAN decisions.
 */
@Component({
  selector: 'app-economic-evidence-note',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (isStructured()) {
      <span>{{ explanation() }}</span>
      <details>
        <summary>Original evidence detail</summary>
        <pre>{{ message() }}</pre>
      </details>
    } @else {
      <span>{{ message() || 'Evidence needs review.' }}</span>
    }
  `,
  styles: `
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-size: 0.85rem;
    }
    summary {
      cursor: pointer;
    }
    :host {
      overflow-wrap: anywhere;
    }
  `,
})
export class EconomicEvidenceNoteComponent {
  readonly code = input('');
  readonly message = input<string | null | undefined>('');
  isStructured(): boolean {
    return /^\s*\{/.test(this.message() || '');
  }
  explanation(): string {
    if (this.code() === 'COMMERCIAL_ASSUMPTION')
      return 'Commercial input is assumed, not verified supplier terms. Review the recorded input and its provenance.';
    if (this.code() === 'COMMERCIAL_INPUT_UNKNOWN' || this.code() === 'UNKNOWN_INPUT')
      return 'A commercial input is UNKNOWN. It is not zero and is excluded or blocks calculation under the canonical rules.';
    return 'Recorded evidence needs review. Expand the original detail; no missing value or verified claim has been inferred.';
  }
}
