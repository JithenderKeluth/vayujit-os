import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-page-header',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="ux-page-header">
      <div>
        @if (eyebrow()) {
          <p class="eyebrow">{{ eyebrow() }}</p>
        }
        <h1 [id]="headingId() || null">{{ title() }}</h1>
        @if (description()) {
          <p class="lede">{{ description() }}</p>
        }
      </div>
      <div class="actions"><ng-content select="[page-header-actions]" /></div>
    </header>
  `,
  styles: `
    :host {
      display: block;
    }
    .ux-page-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: var(--vj-space-5);
      margin-bottom: var(--vj-space-5);
    }
    h1 {
      margin: 0;
    }
    .lede {
      max-width: 65ch;
      margin: var(--vj-space-2) 0 0;
      color: var(--vj-color-ink-soft);
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: var(--vj-space-2);
    }
    @media (max-width: 640px) {
      .ux-page-header {
        flex-direction: column;
      }
    }
  `,
})
export class PageHeaderComponent {
  readonly title = input.required<string>();
  readonly eyebrow = input('');
  readonly description = input('');
  readonly headingId = input('');
}
