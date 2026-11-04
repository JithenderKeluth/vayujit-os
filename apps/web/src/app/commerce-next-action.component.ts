import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { CommerceNextAction } from './commerce-journey.types';

@Component({
  selector: 'app-commerce-next-action',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `@if (action) {
    <section class="commerce-next-action" aria-label="Next best action">
      <div>
        <p class="eyebrow">Next best action</p>
        <h3>{{ action.title }}</h3>
        <p>{{ action.detail }}</p>
      </div>
      <a class="op-button" [routerLink]="action.route">Open workspace</a>
    </section>
  }`,
  styles: [
    `
      .commerce-next-action {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: center;
        flex-wrap: wrap;
        border-left: 4px solid #0d7281;
        padding: 0.8rem 1rem;
        margin: 1rem 0;
        background: #eef7f7;
      }
      .commerce-next-action > div {
        min-width: 0;
        flex: 1 1 18rem;
      }
      .commerce-next-action h3 {
        margin: 0.1rem 0;
      }
      .commerce-next-action p {
        overflow-wrap: anywhere;
      }
      .commerce-next-action .op-button {
        flex: 0 0 auto;
      }
      @media (max-width: 520px) {
        .commerce-next-action .op-button {
          width: 100%;
          box-sizing: border-box;
          text-align: center;
        }
      }
    `,
  ],
})
export class CommerceNextActionComponent {
  @Input() action: CommerceNextAction | null = null;
}
