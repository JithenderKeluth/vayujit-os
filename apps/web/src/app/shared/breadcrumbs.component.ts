import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import type { BreadcrumbItem } from './ux-foundation.types';

@Component({
  selector: 'app-breadcrumbs',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (items().length) {
      <nav class="ux-breadcrumbs" aria-label="Breadcrumb">
        <ol>
          @for (item of items(); track item.label + (item.url || '')) {
            <li>
              @if (item.url) {
                <a [routerLink]="item.url">{{ item.label }}</a>
              } @else {
                <span aria-current="page">{{ item.label }}</span>
              }
            </li>
          }
        </ol>
      </nav>
    }
  `,
  styles: `
    :host {
      display: block;
      max-width: var(--vj-content-width);
      margin: 0 auto var(--vj-space-4);
    }
    ol {
      display: flex;
      flex-wrap: wrap;
      gap: var(--vj-space-2);
      margin: 0;
      padding: 0;
      list-style: none;
      color: var(--vj-color-muted);
      font-size: 0.86rem;
    }
    li {
      display: inline-flex;
      align-items: center;
      gap: var(--vj-space-2);
    }
    li + li::before {
      content: '/';
      color: var(--vj-color-border-strong);
    }
    a {
      color: var(--vj-color-brand-strong);
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
  `,
})
export class BreadcrumbsComponent {
  readonly items = input.required<BreadcrumbItem[]>();
}
