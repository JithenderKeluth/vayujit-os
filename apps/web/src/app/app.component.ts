import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from './auth/auth.service';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { BrandService } from './brands/brand.service';
import { OperationsService } from './operations/operations.service';
import { BreadcrumbService } from './shared/breadcrumb.service';
import { BreadcrumbsComponent } from './shared/breadcrumbs.component';

@Component({
  selector: 'app-root',
  imports: [RouterLink, RouterLinkActive, RouterOutlet, BreadcrumbsComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  readonly auth = inject(AuthService);
  readonly brands = inject(BrandService);
  private readonly router = inject(Router);
  private readonly operations = inject(OperationsService);
  readonly breadcrumbs = inject(BreadcrumbService);
  readonly navigationGroups = [
    {
      label: 'Home',
      items: [
        ['Dashboard', '/dashboard'],
        ['Business Agent', '/intelligence/business-agent'],
      ] as const,
    },
    {
      label: 'Research',
      items: [
        ['Product Opportunities', '/intelligence/product-opportunities'],
        ['My Research', '/intelligence'],
      ] as const,
    },
    {
      label: 'Source',
      items: [
        ['Suppliers', '/intelligence/sourcing'],
        ['Sourcing decisions', '/intelligence/sourcing-scenarios'],
      ] as const,
    },
    {
      label: 'Sell',
      items: [
        ['Products', '/products'],
        ['Listings', '/marketplaces/listings'],
        ['Inventory', '/marketplaces/inventory'],
        ['Orders', '/marketplaces/orders'],
      ] as const,
    },
    {
      label: 'Create',
      items: [
        ['Content', '/ai/studio'],
        ['SEO', '/ai/studio/seo'],
        ['Images', '/ai/images'],
        ['Videos', '/ai/video'],
      ] as const,
    },
    {
      label: 'Grow',
      items: [
        ['Campaigns', '/campaigns'],
        ['Social', '/social'],
        ['Advertising', '/ads'],
      ] as const,
    },
    {
      label: 'Manage',
      items: [['Calendar', '/calendar']] as const,
    },
  ] as const;
  readonly advancedNavigationGroups = [
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
      ] as const,
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
      ] as const,
    },
    {
      label: 'Configuration',
      items: [
        ['Integrations', '/settings/publishing/connectors'],
        ['AI Providers', '/settings/ai/providers'],
        ['Provider Integrations', '/settings/providers'],
        ['Settings', '/settings'],
      ] as const,
    },
  ] as const;
  readonly maintenance = signal(false);
  private readonly advancedPrefixes = [
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
  ];

  isAdvancedRoute(): boolean {
    return this.advancedPrefixes.some((prefix) => this.router.url.startsWith(prefix));
  }
  constructor() {
    effect(() => {
      if (this.auth.user()) {
        void this.restoreBrandContext();
        void this.loadMaintenance();
      } else this.brands.activeBrand.set(null);
    });
  }
  private async loadMaintenance(): Promise<void> {
    try {
      this.maintenance.set((await this.operations.maintenance()).enabled);
    } catch {
      this.maintenance.set(false);
    }
  }
  async logout(): Promise<void> {
    await this.auth.logout();
    await this.router.navigateByUrl('/login');
  }
  private async restoreBrandContext(): Promise<void> {
    const active = await this.brands.loadActive();
    if (active) return;
    try {
      const id = (await this.operations.settings()).preferences.default_brand_id;
      if (id) await this.brands.activate(id);
    } catch {
      // An unavailable preference must never prevent application startup.
    }
  }
}
