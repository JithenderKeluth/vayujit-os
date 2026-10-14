import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { DashboardResponse, SettingsResponse, OperationalHealth, BackupSummary, ProductSummary } from '@vayujit/shared';
import { PageHeaderComponent } from '../shared/page-header.component';
import { ErrorStateComponent, LoadingStateComponent } from '../shared/state-components';
import { StatusBadgeComponent } from '../shared/status-badge.component';
import { OperationsService } from './operations.service';
import { ProductService } from '../products/product.service';
import { CatalogService } from '../catalog/catalog.service';
import { MarketplaceService, type MarketplaceAccount, type InventoryItem, type FinancialSummary } from '../marketplaces/marketplace.service';

type ReadinessState = 'NOT STARTED' | 'IN PROGRESS' | 'READY FOR REVIEW' | 'BLOCKED' | 'VERIFIED';

interface ReadinessItem {
  key: string;
  title: string;
  state: ReadinessState;
  summary: string;
  evidence: string;
  route: string;
  action: string;
}

interface LaunchWarning {
  key: string;
  severity: 'BLOCKED' | 'WARNING' | 'INFO';
  title: string;
  summary: string;
  evidence: string;
  route: string;
  action: string;
}

interface ProductionReadinessProjection {
  configuration: Record<string, unknown>;
  live_mutations: Record<string, boolean>;
}

/**
 * First-seller launch projection. This screen composes existing owner-scoped
 * authorities; it does not persist a second business, launch, or approval
 * record and it never enables an external write.
 */
@Component({
  selector: 'app-launch-readiness',
  imports: [RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent, StatusBadgeComponent],
  template: `
    <section class="op-page launch-page" aria-labelledby="launch-title">
      <app-page-header
        eyebrow="Sell / first-seller launch"
        title="Launch readiness"
        headingId="launch-title"
        description="A single evidence-backed checklist for preparing VAYUJIT's first seller. Every item links to its canonical workspace."
      >
        <a class="op-button" page-header-actions routerLink="/dashboard">Back to dashboard</a>
      </app-page-header>

      <section class="launch-callout" role="note" aria-label="Launch safety boundary">
        <strong>Local preparation only.</strong>
        <span>Go-live requires explicit HUMAN approval and external infrastructure certification. No marketplace, supplier, payment, or inventory write is performed from this page.</span>
      </section>

      @if (loading()) { <app-loading-state message="Checking canonical launch evidence..." /> }
      @if (error()) { <app-error-state title="Launch readiness is partially unavailable" [message]="error()" retryLabel="Retry checks" (retry)="load()" /> }

      @if (snapshot(); as value) {
        <section class="launch-summary" aria-labelledby="summary-title">
          <div>
            <p class="eyebrow">Current decision boundary</p>
            <h2 id="summary-title">{{ value.readyForReview }} of {{ value.total }} areas ready for HUMAN review</h2>
            <p>{{ value.blocked }} blocked · {{ value.notStarted }} not started · {{ value.verified }} verified</p>
          </div>
          <a class="op-button primary" routerLink="/operations/action-center">Review Action Center</a>
        </section>

        <section class="launch-warnings op-card" aria-labelledby="warnings-title">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Release-risk evidence</p>
              <h2 id="warnings-title">Warnings before a production-ready decision</h2>
            </div>
            <span class="warning-count" role="status" [attr.aria-label]="value.warnings.length + ' unresolved launch warnings'">{{ value.warnings.length }} unresolved</span>
          </div>
          <p class="launch-warning-intro">Each item below is derived from an owner-scoped canonical source. Open the linked workspace to resolve it; this page never approves or enables an external action.</p>
          @if (value.warnings.length) {
            <ul class="warning-list">
              @for (warning of value.warnings; track warning.key) {
                <li class="warning-item" [attr.data-severity]="warning.severity">
                  <div class="warning-heading"><span class="warning-severity">{{ warning.severity }}</span><h3>{{ warning.title }}</h3></div>
                  <p>{{ warning.summary }}</p>
                  <p class="launch-evidence"><strong>Evidence:</strong> {{ warning.evidence }}</p>
                  <a class="op-button secondary" [routerLink]="warning.route">{{ warning.action }}</a>
                </li>
              }
            </ul>
          } @else {
            <p class="launch-clear" role="status">No unresolved warnings were returned by the canonical readiness sources. HUMAN review is still required before any go-live decision.</p>
          }
        </section>

        <section class="launch-grid" aria-label="First-seller readiness areas">
          @for (item of value.items; track item.key) {
            <article class="launch-card">
              <div class="launch-card-heading">
                <div><p class="eyebrow">{{ item.key }}</p><h2>{{ item.title }}</h2></div>
                <app-status-badge [status]="item.state" [label]="item.state" [tone]="tone(item.state)" />
              </div>
              <p>{{ item.summary }}</p>
              <p class="launch-evidence"><strong>Evidence:</strong> {{ item.evidence }}</p>
              <a class="op-button secondary" [routerLink]="item.route">{{ item.action }}</a>
            </article>
          }
        </section>

        <section class="launch-steps op-card" aria-labelledby="steps-title">
          <p class="eyebrow">Recommended order</p>
          <h2 id="steps-title">Prepare, review, then authorize</h2>
          <ol>
            <li><a routerLink="/settings">Confirm business identity, timezone, and seller preferences.</a></li>
            <li><a routerLink="/catalog">Prepare a real product, variant, SKU, images, costs, and listing draft.</a></li>
            <li><a routerLink="/marketplaces/inventory">Record only HUMAN-confirmed physical stock and location evidence.</a></li>
            <li><a routerLink="/marketplaces/accounts">Review marketplace account readiness; keep providers synthetic or read-only until separately approved.</a></li>
            <li><a routerLink="/operations/backups">Create and verify an encrypted off-host backup plan before any production migration.</a></li>
            <li><a routerLink="/operations/action-center">Resolve evidence gaps and record the final HUMAN go-live decision.</a></li>
          </ol>
        </section>
      }
    </section>
  `,
  styleUrl: './operations.css',
})
export class LaunchReadinessComponent {
  private readonly operations = inject(OperationsService);
  private readonly products = inject(ProductService);
  private readonly catalog = inject(CatalogService);
  private readonly marketplaces = inject(MarketplaceService);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly snapshot = signal<{ items: ReadinessItem[]; warnings: LaunchWarning[]; total: number; readyForReview: number; blocked: number; notStarted: number; verified: number } | null>(null);

  constructor() { void this.load(); }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    const results = await Promise.allSettled([
      this.operations.settings(),
      this.operations.health(),
      this.operations.backups(),
      this.operations.dashboard(),
      this.products.list({ pageSize: 20, allBrands: true }),
      this.marketplaces.accounts(),
      this.marketplaces.canonicalInventory(),
      this.marketplaces.financialSummary(),
      this.marketplaces.listings(),
      this.marketplaces.inventoryMappings(),
      this.operations.productionReadiness(),
    ]);
    const [settings, health, backups, dashboard, products, accounts, inventory, financial] = results;
    const failed = results.filter((item) => item.status === 'rejected').length;
    if (failed) this.error.set(`${failed} readiness source${failed === 1 ? '' : 's'} could not be loaded. A failed check remains unresolved until the source is reviewed.`);
    const value = (index: number): unknown => {
      const result = results[index];
      return result.status === 'fulfilled' ? result.value : null;
    };
    const profile = value(0) as SettingsResponse | null;
    const healthValue = value(1) as OperationalHealth | null;
    const backupValue = value(2) as BackupSummary[] | null;
    const dashboardValue = value(3) as DashboardResponse | null;
    const productValue = value(4) as { items?: ProductSummary[]; total: number } | null;
    const accountValue = value(5) as MarketplaceAccount[] | null;
    const inventoryValue = value(6) as InventoryItem[] | null;
    const financialValue = value(7) as FinancialSummary | null;
    const listingsValue = value(8) as Array<{ product_id: string; marketplace_sku: string | null }> | null;
    const mappingsValue = value(9) as Array<{ listing_id: string | null; external_sku: string; status: string }> | null;
    const productionValue = value(10) as ProductionReadinessProjection | null;
    const warnings: LaunchWarning[] = [];
    const addWarning = (warning: LaunchWarning): void => {
      if (!warnings.some((item) => item.key === warning.key)) warnings.push(warning);
    };
    const addProductWarning = (key: string, title: string, summary: string, evidence: string, productId?: string): void => {
      addWarning({ key, severity: 'BLOCKED', title, summary, evidence, route: productId ? `/catalog/${productId}` : '/catalog', action: productId ? 'Open product evidence' : 'Open catalog' });
    };
    if (!profile?.profile.full_name?.trim() || !profile.preferences.timezone?.trim()) {
      addWarning({ key: 'business-information', severity: 'BLOCKED', title: 'Business information is incomplete', summary: 'Complete the owner name and operating timezone before treating launch preparation as reviewable.', evidence: profile ? 'Settings profile or timezone is missing.' : 'Settings authority was unavailable.', route: '/settings', action: 'Review business settings' });
    }

    const productItems = (productValue as { items?: ProductSummary[] } | null)?.items ?? [];
    const detailResults = await Promise.all(productItems.slice(0, 20).map(async (product) => {
      const [detail, readiness] = await Promise.allSettled([this.catalog.getProduct(product.id), this.catalog.readiness(product.id)]);
      return {
        product,
        detail: detail.status === 'fulfilled' ? detail.value : null,
        readiness: readiness.status === 'fulfilled' ? readiness.value : null,
      };
    }));
    const productsMissingCost = productItems.filter((product) => !product.cost_amount);
    if (productsMissingCost.length) {
      addProductWarning('product-cost', 'Product acquisition cost is missing', 'Enter a HUMAN-confirmed acquisition cost before financial readiness can be assessed.', `${productsMissingCost.length} catalog product(s) have no cost_amount.`, productsMissingCost[0]?.id);
    }
    const productsMissingImage = detailResults.filter((result) => result.detail && result.detail.images.length === 0);
    if (productsMissingImage.length) {
      addProductWarning('product-image', 'Product image evidence is missing', 'Attach a private catalog image before a listing can be treated as ready for review.', `${productsMissingImage.length} product detail record(s) contain no canonical product images.`, productsMissingImage[0]?.product.id);
    }
    const productsWithBlockedListing = detailResults.filter((result) => result.readiness?.readiness === 'BLOCKED' || result.detail?.listing_drafts.some((draft) => draft.readiness_state === 'BLOCKED'));
    if (productsWithBlockedListing.length) {
      addProductWarning('listing-readiness', 'Catalog listing preparation is blocked', 'Resolve the authoritative listing fields shown in the catalog workspace; launch review cannot bypass them.', `${productsWithBlockedListing.length} product(s) have a BLOCKED catalog/listing readiness result.`, productsWithBlockedListing[0]?.product.id);
    }
    if (listingsValue?.some((listing) => !listing.marketplace_sku)) {
      addWarning({ key: 'marketplace-sku', severity: 'BLOCKED', title: 'A marketplace SKU is not mapped', summary: 'Map each local inventory item to its marketplace SKU before inventory or listing operations can be reviewed.', evidence: 'At least one canonical marketplace listing has no marketplace_sku.', route: '/marketplaces/inventory', action: 'Review SKU mappings' });
    } else if (listingsValue?.length && !mappingsValue?.length) {
      addWarning({ key: 'marketplace-sku', severity: 'BLOCKED', title: 'Marketplace SKU mapping is not recorded', summary: 'Review the canonical inventory mapping workspace before any channel operation.', evidence: `${listingsValue.length} marketplace listing(s) exist but no owner-scoped mapping is present.`, route: '/marketplaces/inventory', action: 'Review SKU mappings' });
    }
    if (!inventoryValue?.length || inventoryValue.every((item) => item.on_hand_quantity <= 0)) {
      addWarning({ key: 'initial-stock', severity: 'WARNING', title: 'Initial stock is not confirmed', summary: 'Record HUMAN-confirmed opening stock and location evidence before planning a first seller launch.', evidence: inventoryValue?.length ? 'Canonical inventory contains no non-zero on-hand quantity.' : 'No canonical inventory record exists.', route: '/marketplaces/inventory', action: 'Review stock evidence' });
    }
    if (financialValue?.missing_inputs?.length) {
      addWarning({ key: 'financial-assumptions', severity: 'WARNING', title: 'Financial assumptions are incomplete', summary: 'Review missing fees, taxes, cost, or settlement inputs. UNKNOWN values are not treated as zero.', evidence: financialValue.missing_inputs.join(', '), route: '/marketplaces/financials', action: 'Review financial evidence' });
    }
    if (!accountValue?.length || accountValue.some((account) => account.validation_status !== 'valid' || !account.enabled)) {
      addWarning({ key: 'marketplace-authorization', severity: 'WARNING', title: 'Marketplace authorization is not verified', summary: 'Keep the connection synthetic/read-only until its canonical validation and HUMAN approval are complete.', evidence: accountValue?.length ? `${accountValue.length} account(s); at least one is unverified or disabled.` : 'No marketplace account is configured.', route: '/marketplaces/accounts', action: 'Review marketplace authorization' });
    }
    if (productionValue && (!Object.values(productionValue.live_mutations).every(Boolean) || productionValue.configuration['emergency_stop_active'] === true)) {
      addWarning({ key: 'external-mutations', severity: 'INFO', title: 'External mutations remain disabled', summary: 'This is the safe local boundary. No marketplace, supplier, payment, or inventory write can be triggered from launch preparation.', evidence: 'Canonical production-readiness reports live mutation switches disabled or emergency stop active.', route: '/operations/action-center', action: 'Review safety boundary' });
    }
    const pendingApprovals = dashboardValue?.metrics.pending_approvals ?? 0;
    const failedWorkflows = dashboardValue?.metrics.failed_workflows ?? 0;
    if (pendingApprovals || failedWorkflows) {
      addWarning({ key: 'action-center', severity: 'WARNING', title: 'Action Center items need HUMAN review', summary: 'Resolve pending approvals and failed workflows before recording a launch decision.', evidence: `${pendingApprovals} pending approval(s) · ${failedWorkflows} failed workflow(s).`, route: '/operations/action-center', action: 'Open Action Center' });
    }
    const releaseValue = typeof this.operations.controlReleaseReadiness === 'function'
      ? await this.operations.controlReleaseReadiness().catch(() => null) as { checks?: Record<string, boolean>; status?: string } | null
      : null;
    if (releaseValue?.checks?.['live_provider_signoff'] === false) {
      addWarning({ key: 'human-approval', severity: 'BLOCKED', title: 'HUMAN go-live approval is not recorded', summary: 'The application remains conditional until the owner reviews evidence and records the final decision in the Action Center.', evidence: `Release readiness status: ${releaseValue.status || 'conditional'}; live provider signoff is false.`, route: '/operations/action-center', action: 'Review approval boundary' });
    }
    const items: ReadinessItem[] = [
      this.item('business', 'Business identity & preferences', profile?.profile.full_name && profile.preferences.timezone ? 'READY FOR REVIEW' : 'BLOCKED', 'Owner identity and operating preferences are explicit; legal registrations remain unverified.', profile ? `Owner ${profile.profile.full_name || 'name missing'} · ${profile.preferences.timezone}` : 'Settings unavailable', '/settings', 'Review settings'),
      this.item('infrastructure', 'Application infrastructure', healthValue?.status === 'healthy' ? 'READY FOR REVIEW' : healthValue ? 'BLOCKED' : 'IN PROGRESS', 'Health and migration status come from the canonical Operations authority.', healthValue ? `${healthValue.status} · migration ${healthValue.current_migration}/${healthValue.expected_migration}` : 'Health unavailable', '/operations/health', 'Open system health'),
      this.item('catalog', 'Catalog & listing preparation', productValue?.total ? 'READY FOR REVIEW' : 'NOT STARTED', 'Real products must have variants, SKU, images, costs, and listing evidence before review.', productValue ? `${productValue.total} product(s) in the catalog` : 'Catalog unavailable', '/catalog', 'Prepare catalog'),
      this.item('inventory', 'Inventory & stock evidence', inventoryValue?.length ? 'READY FOR REVIEW' : 'NOT STARTED', 'Initial stock remains HUMAN-confirmed and separate from provider observations.', inventoryValue ? `${inventoryValue.length} canonical stock record(s)` : 'Inventory unavailable', '/marketplaces/inventory', 'Review inventory'),
      this.item('marketplace', 'Marketplace connections', accountValue?.length ? 'READY FOR REVIEW' : 'NOT STARTED', 'Synthetic and read-only connections are visible; live OAuth and writes remain separately authorized.', accountValue ? `${accountValue.length} account record(s); live writes denied` : 'Marketplace accounts unavailable', '/marketplaces/accounts', 'Review connections'),
      this.item('financial', 'Financial readiness', financialValue?.missing_inputs?.length ? 'BLOCKED' : financialValue ? 'READY FOR REVIEW' : 'IN PROGRESS', 'Unknown fees, costs, taxes, and settlements remain UNKNOWN; estimates are not actuals.', financialValue ? (financialValue.missing_inputs.length ? `${financialValue.missing_inputs.length} missing input(s)` : `${financialValue.evidence_status} evidence`) : 'Financial evidence unavailable', '/marketplaces/financials', 'Review financials'),
      this.item('backup', 'Backup & recovery', backupValue?.some((item) => item.verification_status === 'verified') ? 'READY FOR REVIEW' : 'BLOCKED', 'A verified backup and disposable restore rehearsal are required before go-live.', backupValue ? `${backupValue.length} backup record(s); ${backupValue.filter((item) => item.verification_status === 'verified').length} verified` : 'Backup evidence unavailable', '/operations/backups', 'Review backups'),
      this.item('operations', 'Action Center & approvals', dashboardValue?.metrics.pending_approvals || dashboardValue?.metrics.failed_workflows ? 'IN PROGRESS' : dashboardValue ? 'READY FOR REVIEW' : 'IN PROGRESS', 'Business Agent remains advisory; consequential launch decisions require HUMAN review.', dashboardValue ? `${dashboardValue.metrics.pending_approvals} approval(s) · ${dashboardValue.metrics.failed_workflows} failed workflow(s)` : 'Action Center unavailable', '/operations/action-center', 'Review actions'),
    ];
    this.snapshot.set({
      items,
      warnings,
      total: items.length,
      readyForReview: items.filter((item) => item.state === 'READY FOR REVIEW').length,
      blocked: items.filter((item) => item.state === 'BLOCKED').length,
      notStarted: items.filter((item) => item.state === 'NOT STARTED').length,
      verified: items.filter((item) => item.state === 'VERIFIED').length,
    });
    void settings; void health; void backups; void dashboard; void products; void accounts; void inventory; void financial;
    this.loading.set(false);
  }

  tone(state: ReadinessState): 'info' | 'warning' | 'danger' {
    return state === 'BLOCKED' ? 'danger' : state === 'READY FOR REVIEW' || state === 'VERIFIED' ? 'info' : 'warning';
  }

  private item(key: string, title: string, state: ReadinessState, summary: string, evidence: string, route: string, action: string): ReadinessItem {
    return { key, title, state, summary, evidence, route, action };
  }
}
