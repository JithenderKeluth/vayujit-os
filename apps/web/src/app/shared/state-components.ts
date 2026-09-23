import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

@Component({
  selector: 'app-loading-state',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div class="ux-state loading" role="status" aria-live="polite">
    <span class="indicator" aria-hidden="true"></span><span>{{ message() }}</span>
  </div>`,
  styles: `
    :host {
      display: block;
    }
    .ux-state {
      display: flex;
      align-items: center;
      gap: 0.65rem;
      padding: var(--vj-space-4);
      color: var(--vj-color-ink-soft);
    }
    .indicator {
      width: 0.8rem;
      height: 0.8rem;
      border: 2px solid var(--vj-color-border-strong);
      border-top-color: var(--vj-color-brand);
      border-radius: 50%;
      animation: ux-spin 800ms linear infinite;
    }
    @media (prefers-reduced-motion: reduce) {
      .indicator {
        animation: none;
      }
    }
    @keyframes ux-spin {
      to {
        transform: rotate(360deg);
      }
    }
  `,
})
export class LoadingStateComponent {
  readonly message = input('Loading…');
}

@Component({
  selector: 'app-empty-state',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<section class="ux-state empty" aria-live="polite">
    <h2>{{ title() }}</h2>
    <p>{{ message() }}</p>
    <ng-content />
    @if (actionLabel()) {
      <button type="button" (click)="action.emit()">{{ actionLabel() }}</button>
    }
  </section>`,
  styles: `
    :host {
      display: block;
    }
    .ux-state {
      padding: var(--vj-space-6);
      border: 1px dashed var(--vj-color-border-strong);
      border-radius: var(--vj-radius-md);
      text-align: center;
      background: var(--vj-color-surface);
    }
    h2 {
      margin: 0;
    }
    p {
      color: var(--vj-color-ink-soft);
    }
    button {
      min-height: 2.5rem;
      padding: 0.55rem 0.9rem;
      border: 0;
      border-radius: var(--vj-radius-sm);
      background: var(--vj-color-brand);
      color: #fff;
      cursor: pointer;
    }
  `,
})
export class EmptyStateComponent {
  readonly title = input.required<string>();
  readonly message = input.required<string>();
  readonly actionLabel = input('');
  readonly action = output<void>();
}

@Component({
  selector: 'app-error-state',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<section class="ux-state error" role="alert">
    <h2>{{ title() }}</h2>
    <p>{{ message() }}</p>
    @if (retryLabel()) {
      <button type="button" (click)="retry.emit()">{{ retryLabel() }}</button>
    }
    <ng-content />
  </section>`,
  styles: `
    :host {
      display: block;
    }
    .ux-state {
      padding: var(--vj-space-4);
      border: 1px solid #e7b8b8;
      border-radius: var(--vj-radius-md);
      background: #fff1f1;
      color: var(--vj-color-error);
    }
    h2 {
      margin-top: 0;
      font-size: 1rem;
    }
    button {
      min-height: 2.4rem;
      padding: 0.5rem 0.8rem;
      border: 1px solid currentColor;
      border-radius: var(--vj-radius-sm);
      background: transparent;
      color: inherit;
      cursor: pointer;
    }
  `,
})
export class ErrorStateComponent {
  readonly title = input('Something went wrong');
  readonly message = input.required<string>();
  readonly retryLabel = input('');
  readonly retry = output<void>();
}
