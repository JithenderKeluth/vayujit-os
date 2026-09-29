import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { CommerceNextAction } from './commerce-journey.types';

@Component({
  selector: 'app-commerce-next-action',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `@if (action) {
    <aside class="commerce-next-action" aria-label="Next best action">
      <div>
        <p class="eyebrow">Next best action</p>
        <h3>{{ action.title }}</h3>
        <p>{{ action.detail }}</p>
      </div>
      <a class="op-button" [routerLink]="action.route">Open workspace</a>
    </aside>
  }`,
  styles: [
    `
      .commerce-next-action {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: center;
        border-left: 4px solid #0d7281;
        padding: 0.8rem 1rem;
        margin: 1rem 0;
        background: #eef7f7;
      }
      .commerce-next-action h3 {
        margin: 0.1rem 0;
      }
    `,
  ],
})
export class CommerceNextActionComponent {
  @Input() action: CommerceNextAction | null = null;
}
