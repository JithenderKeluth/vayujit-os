import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';

type NavigationGroup = {
  label: string;
  items: readonly (readonly [string, string])[];
};

/**
 * The seller-facing navigation contract.  Route ownership stays in Angular's
 * route table; this component only presents links and never decides access.
 */
@Component({
  selector: 'app-seller-navigation',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <nav [attr.aria-label]="label()">
      @for (group of navigationGroups; track group.label) {
        <div class="nav-group">
          <span class="nav-group-label">{{ group.label }}</span>
          @for (item of group.items; track item[1]) {
            <a [routerLink]="item[1]" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: item[1] === '/intelligence' }" ariaCurrentWhenActive="page">
              {{ item[0] }}
            </a>
          }
        </div>
      }
      <details class="advanced-nav" [open]="isAdvancedRoute()">
        <summary>Advanced</summary>
        @for (group of advancedNavigationGroups; track group.label) {
          <div class="nav-group">
            <span class="nav-group-label">{{ group.label }}</span>
            @for (item of group.items; track item[1]) {
              <a [routerLink]="item[1]" routerLinkActive="active" ariaCurrentWhenActive="page">
                {{ item[0] }}
              </a>
            }
          </div>
        }
      </details>
    </nav>
  `,
  styles: `
    :host {
      display: block;
    }
    nav {
      display: grid;
      gap: var(--vj-space-1);
    }
    .nav-group {
      display: grid;
      gap: var(--vj-space-1);
    }
    .nav-group + .nav-group {
      margin-top: var(--vj-space-3);
    }
    .nav-group-label {
      padding: 0.35rem 0.75rem;
      color: #7fa5a6;
      font-size: 0.68rem;
      font-weight: 750;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    a {
      color: #c9ddda;
      padding: 0.65rem 0.75rem;
      border-radius: var(--vj-radius-sm);
      text-decoration: none;
      font-size: 0.92rem;
    }
    a:hover {
      background: rgb(255 255 255 / 8%);
      color: #fff;
    }
    .active {
      background: var(--vj-color-brand);
      color: #fff;
      box-shadow: inset 3px 0 #f0b16f;
    }
    .advanced-nav {
      margin-top: var(--vj-space-3);
      border-top: 1px solid rgb(255 255 255 / 13%);
      padding-top: var(--vj-space-3);
    }
    .advanced-nav summary {
      padding: 0.55rem 0.75rem;
      color: #d9e9e6;
      cursor: pointer;
      font-size: 0.82rem;
      font-weight: 750;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      list-style-position: inside;
    }
    .advanced-nav[open] summary {
      color: #fff;
    }
    a:focus-visible,
    summary:focus-visible {
      outline: 3px solid #74b9d4;
      outline-offset: 2px;
    }
  `,
})
export class SellerNavigationComponent {
  readonly label = input('Primary navigation');
  private readonly router = inject(Router);

  readonly navigationGroups: readonly NavigationGroup[] = [
    {
      label: 'Home',
      items: [
        ['Dashboard', '/dashboard'],
        ['Business Agent', '/intelligence/business-agent'],
        ['Action Center', '/operations/action-center'],
        ['Launch readiness', '/operations/launch-readiness'],
      ],
    },
    {
      label: 'Research',
      items: [
        ['Product Opportunities', '/intelligence/product-opportunities'],
        ['My Research', '/intelligence'],
      ],
    },
    {
      label: 'Source',
      items: [
        ['Suppliers', '/intelligence/sourcing'],
        ['Supplier engagement', '/intelligence/supplier-engagement'],
        ['Sourcing decisions', '/intelligence/sourcing-scenarios'],
      ],
    },
    {
      label: 'Sell',
      items: [
        ['Catalog', '/catalog'],
        ['Products', '/products'],
        ['Listings', '/marketplaces/listings'],
        ['Inventory', '/marketplaces/inventory'],
        ['Orders', '/marketplaces/orders'],
        ['Financials', '/marketplaces/financials'],
      ],
    },
    {
      label: 'Create',
      items: [
        ['Content', '/ai/studio'],
        ['SEO', '/ai/studio/seo'],
        ['Images', '/ai/images'],
        ['Videos', '/ai/video'],
      ],
    },
    {
      label: 'Grow',
      items: [
        ['Campaigns', '/campaigns'],
        ['Social', '/social'],
        ['Advertising', '/ads'],
      ],
    },
    { label: 'Manage', items: [['Calendar', '/calendar']] },
  ];

  readonly advancedNavigationGroups: readonly NavigationGroup[] = [
    {
      label: 'Intelligence',
      items: [
        ['Trend Intelligence', '/intelligence/trends'],
        ['Competitors', '/intelligence/competitors'],
        ['Customer Reviews', '/intelligence/reviews'],
        ['Website Intelligence', '/intelligence/websites'],
        ['External Research', '/intelligence/external'],
        ['Autonomous Research', '/intelligence/autonomous'],
        ['Cross-marketplace Suppliers', '/intelligence/cross-marketplace'],
        ['IndiaMART Discovery', '/intelligence/indiamart'],
        ['Alibaba Discovery', '/intelligence/alibaba'],
        ['TradeIndia Discovery', '/intelligence/tradeindia'],
        ['Global Sources Discovery', '/intelligence/global-sources'],
        ['Portfolio & Resilience', '/intelligence/supplier-portfolios'],
        ['Shortlists', '/intelligence/supplier-shortlisting'],
        ['Supplier Verification', '/intelligence/due-diligence'],
        ['Sourcing Economics', '/intelligence/sourcing-economics'],
        ['Supplier Engagement', '/intelligence/supplier-engagement'],
      ],
    },
    {
      label: 'Operations',
      items: [
        ['Operations', '/operations'],
        ['Workflows', '/workflows'],
        ['Approvals', '/approvals'],
        ['Execution History', '/execution-history'],
        ['Jobs', '/publishing/jobs'],
        ['Schedules', '/publishing/schedules'],
        ['Recovery', '/operations/recovery'],
        ['System Doctor', '/operations/health'],
      ],
    },
    {
      label: 'Configuration',
      items: [
        ['Integrations', '/settings/publishing/connectors'],
        ['AI Providers', '/settings/ai/providers'],
        ['Provider Integrations', '/settings/providers'],
        ['Settings', '/settings'],
      ],
    },
  ];

  isAdvancedRoute(): boolean {
    return [
      '/intelligence/trends',
      '/intelligence/competitors',
      '/intelligence/reviews',
      '/intelligence/websites',
      '/intelligence/external',
      '/intelligence/autonomous',
      '/intelligence/cross-marketplace',
      '/intelligence/indiamart',
      '/intelligence/alibaba',
      '/intelligence/tradeindia',
      '/intelligence/global-sources',
      '/intelligence/supplier-portfolios',
      '/intelligence/supplier-shortlisting',
      '/intelligence/due-diligence',
      '/intelligence/sourcing-economics',
      '/operations',
      '/workflows',
      '/approvals',
      '/execution-history',
      '/publishing',
      '/settings',
    ].some((prefix) => this.router.url.startsWith(prefix));
  }
}
