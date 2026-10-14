import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { DashboardResponse, SettingsResponse, OperationalHealth, BackupSummary } from '@vayujit/shared';
import { LaunchReadinessComponent } from './launch-readiness.component';
import { OperationsService } from './operations.service';
import { ProductService } from '../products/product.service';
import { CatalogService } from '../catalog/catalog.service';
import { MarketplaceService } from '../marketplaces/marketplace.service';

describe('LaunchReadinessComponent', () => {
  let fixture: ComponentFixture<LaunchReadinessComponent>;
  const health: OperationalHealth = {
    status: 'healthy',
    components: [],
    current_migration: 'head',
    expected_migration: 'head',
    application_version: 'test',
    build_identifier: 'test',
  };
  const settings: SettingsResponse = {
    profile: { id: 'owner', full_name: 'VAYUJIT', email: 'owner@example.test', created_at: '', last_login_at: null },
    preferences: { timezone: 'Asia/Kolkata', date_format: 'medium', default_page_size: 25, execution_history_page_size: 25, default_brand_id: null, default_prompt_template_id: null, default_publishing_destination_id: null, confirm_before_publish: true, confirm_before_retry: true, theme_preference: 'system', density_preference: 'comfortable' },
  };
  const dashboard: DashboardResponse = { metrics: { pending_approvals: 0, failed_workflows: 0 } as DashboardResponse['metrics'], activity: [] };
  const backup: BackupSummary = { id: 'b1', backup_key: 'b1', filename: 'backup.dump', format: 'custom', size_bytes: 1, checksum_sha256: 'x', application_version: 'test', migration_revision: 'head', database_name: 'test', created_at: '', verified_at: '', verification_status: 'verified', status: 'completed', encryption_status: 'not_encrypted' };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LaunchReadinessComponent],
      providers: [
        provideRouter([]),
        { provide: OperationsService, useValue: { settings: () => Promise.resolve(settings), health: () => Promise.resolve(health), backups: () => Promise.resolve([backup]), dashboard: () => Promise.resolve(dashboard), productionReadiness: () => Promise.resolve({ configuration: { emergency_stop_active: true }, live_mutations: {} }), controlReleaseReadiness: () => Promise.resolve({ status: 'conditional', checks: { live_provider_signoff: false } }) } },
        { provide: ProductService, useValue: { list: () => Promise.resolve({ total: 1, items: [{ id: 'p1', cost_amount: null }] }) } },
        { provide: CatalogService, useValue: { getProduct: () => Promise.resolve({ images: [], listing_drafts: [] }), readiness: () => Promise.resolve({ readiness: 'BLOCKED', blockers: [], next_actions: [] }) } },
        { provide: MarketplaceService, useValue: { accounts: () => Promise.resolve([{ id: 'a1' }]), canonicalInventory: () => Promise.resolve([{ id: 'i1', on_hand_quantity: 1 }]), financialSummary: () => Promise.resolve({ missing_inputs: [], evidence_status: 'observed' }), listings: () => Promise.resolve([]), inventoryMappings: () => Promise.resolve([]) } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(LaunchReadinessComponent);
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('projects canonical evidence into actionable readiness areas', () => {
    expect(fixture.nativeElement.textContent).toContain('Launch readiness');
    expect(fixture.nativeElement.textContent).toContain('Catalog & listing preparation');
    expect(fixture.nativeElement.textContent).toContain('READY FOR REVIEW');
    expect(fixture.nativeElement.querySelector('a[href="/catalog"]')).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Warnings before a production-ready decision');
    expect(fixture.nativeElement.textContent).toContain('Product acquisition cost is missing');
    expect(fixture.nativeElement.textContent).toContain('Product image evidence is missing');
  });

  it('keeps go-live HUMAN-gated and writes disabled in the visible boundary', () => {
    expect(fixture.nativeElement.textContent).toContain('explicit HUMAN approval');
    expect(fixture.nativeElement.textContent).toContain('No marketplace, supplier, payment, or inventory write');
  });
});
