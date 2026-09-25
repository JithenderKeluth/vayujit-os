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
      label: 'Discover',
      items: [
        ['Research', '/intelligence'],
        ['Product Opportunities', '/intelligence/product-opportunities'],
        ['Trend Intelligence', '/intelligence/trends'],
        ['Competitors', '/intelligence/competitors'],
        ['Customer Reviews', '/intelligence/reviews'],
        ['External Research', '/intelligence/external'],
        ['Website Intelligence', '/intelligence/websites'],
        ['Autonomous Research', '/intelligence/autonomous'],
      ] as const,
    },
    {
      label: 'Source',
      items: [
        ['Suppliers', '/intelligence/sourcing'],
        ['Shortlists', '/intelligence/supplier-shortlisting'],
        ['Supplier Verification', '/intelligence/due-diligence'],
        ['Sourcing Scenarios', '/intelligence/sourcing-scenarios'],
        ['Portfolio & Resilience', '/intelligence/supplier-portfolios'],
        ['Cross-marketplace Suppliers', '/intelligence/cross-marketplace'],
        ['IndiaMART Discovery', '/intelligence/indiamart'],
        ['Alibaba Discovery', '/intelligence/alibaba'],
        ['TradeIndia Discovery', '/intelligence/tradeindia'],
        ['Global Sources Discovery', '/intelligence/global-sources'],
      ] as const,
    },
    {
      label: 'Create',
      items: [
        ['Content', '/ai/studio'],
        ['SEO', '/ai/studio/seo'],
        ['Images', '/ai/images'],
        ['Videos', '/ai/video'],
        ['Brand Voices', '/ai/brand-voices'],
        ['Presets', '/ai/presets'],
        ['Media', '/media'],
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
      label: 'Sell',
      items: [
        ['Brands', '/brands'],
        ['Products', '/products'],
        ['Listings', '/marketplaces/listings'],
        ['Inventory', '/marketplaces/inventory'],
        ['Orders', '/marketplaces/orders'],
        ['Marketplace', '/marketplaces'],
        ['Marketplace Video', '/marketplaces/video'],
        ['Publishing', '/publishing'],
      ] as const,
    },
    {
      label: 'Operate',
      items: [
        ['Calendar', '/calendar'],
        ['Schedules', '/publishing/schedules'],
        ['Jobs', '/publishing/jobs'],
        ['Workflows', '/workflows'],
        ['Approvals', '/approvals'],
        ['Execution History', '/execution-history'],
        ['Recovery', '/operations/recovery'],
        ['System Doctor', '/operations/health'],
        ['Operations', '/operations'],
      ] as const,
    },
    {
      label: 'System',
      items: [
        ['Integrations', '/settings/publishing/connectors'],
        ['AI Providers', '/settings/ai/providers'],
        ['Provider Integrations', '/settings/providers'],
        ['Settings', '/settings'],
      ] as const,
    },
  ] as const;
  readonly maintenance = signal(false);
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
