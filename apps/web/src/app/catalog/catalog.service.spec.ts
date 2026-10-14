import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { CatalogService } from './catalog.service';

describe('CatalogService', () => {
  let service: CatalogService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(CatalogService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads owner-scoped catalog context and readiness', async () => {
    const detailPromise = service.getProduct('product-1');
    const detailRequest = http.expectOne('http://127.0.0.1:8000/api/v1/catalog/products/product-1');
    expect(detailRequest.request.withCredentials).toBe(true);
    detailRequest.flush({ product: { id: 'product-1' }, lineage: null, variants: [], supplier_associations: [], listing_drafts: [] });
    expect((await detailPromise).product.id).toBe('product-1');

    const readinessPromise = service.readiness('product-1');
    http.expectOne('http://127.0.0.1:8000/api/v1/catalog/products/product-1/readiness').flush({
      product_id: 'product-1',
      readiness: 'BLOCKED',
      blockers: ['listing_draft_required'],
      next_actions: ['Create a draft'],
      external_publication: 'DISABLED_IN_PR_SOS_01',
    });
    expect((await readinessPromise).blockers).toEqual(['listing_draft_required']);
  });

  it('sends optimistic version and HUMAN review decisions', async () => {
    const draft = {
      id: 'draft-1',
      product_id: 'product-1',
      channel: 'amazon_in' as const,
      title: 'Draft',
      description: '',
      bullets: [],
      category: null,
      attributes: {},
      image_refs: [],
      intended_price_amount: null,
      intended_currency: null,
      compliance: {},
      missing_fields: ['description'],
      validation_state: 'incomplete',
      readiness_state: 'BLOCKED',
      human_review_state: 'not_reviewed' as const,
      status: 'incomplete' as const,
      provenance_json: {},
      version: 2,
      created_at: '',
      updated_at: '',
      archived_at: null,
    };
    const updatePromise = service.updateListingDraft(draft, { description: 'Ready for review' });
    const updateRequest = http.expectOne('http://127.0.0.1:8000/api/v1/catalog/listing-drafts/draft-1');
    expect(updateRequest.request.method).toBe('PATCH');
    expect(updateRequest.request.body.version).toBe(2);
    updateRequest.flush({ ...draft, description: 'Ready for review', version: 3 });
    expect((await updatePromise).version).toBe(3);

    const reviewPromise = service.reviewListingDraft({ ...draft, version: 3 }, 'approve');
    const reviewRequest = http.expectOne(
      'http://127.0.0.1:8000/api/v1/catalog/listing-drafts/draft-1/review',
    );
    expect(reviewRequest.request.body).toEqual({ version: 3, decision: 'approve' });
    reviewRequest.flush({ ...draft, version: 4, human_review_state: 'approved' });
    expect((await reviewPromise).human_review_state).toBe('approved');
  });
});
