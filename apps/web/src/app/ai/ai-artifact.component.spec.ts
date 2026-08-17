import { ActivatedRoute } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { OperationsService } from '../operations/operations.service';
import { WorkflowService } from '../workflows/workflow.service';
import { AIArtifactComponent } from './ai-artifact.component';
import { AIService } from './ai.service';

const artifact = {
  id: 'artifact-1',
  status: 'approved',
  version_number: 2,
  locale: 'en-IN',
  brand_name: 'Brand',
  product_name: 'Product',
  content: {
    product_title: 'Title',
    long_description: 'Description',
    key_features: [],
    keywords: [],
  },
};
const ai = {
  studioListingHandoff: vi.fn().mockResolvedValue({ status: 'ready', artifact_id: 'artifact-1' }),
  studioCampaignHandoff: vi.fn().mockResolvedValue({ status: 'ready', artifact_id: 'artifact-1' }),
};
const operations = {
  approval: vi.fn().mockResolvedValue({ artifact, versions: [{ artifact }] }),
};

describe('AI artifact handoff acceptance', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    operations.approval.mockResolvedValue({ artifact, versions: [{ artifact }] });
    ai.studioListingHandoff.mockResolvedValue({ status: 'ready', artifact_id: 'artifact-1' });
    ai.studioCampaignHandoff.mockResolvedValue({ status: 'ready', artifact_id: 'artifact-1' });
  });

  it('requires explicit confirmation and keeps handoff version pinned', async () => {
    await TestBed.configureTestingModule({
      imports: [AIArtifactComponent],
      providers: [
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { paramMap: { get: () => 'artifact-1' }, queryParamMap: { get: () => null } },
          },
        },
        { provide: AIService, useValue: ai },
        { provide: OperationsService, useValue: operations },
        { provide: WorkflowService, useValue: { continue: vi.fn() } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(AIArtifactComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Version');
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    await fixture.componentInstance.handoffMarketplace(artifact as never);
    expect(ai.studioListingHandoff).not.toHaveBeenCalled();
    confirm.mockReturnValue(true);
    await fixture.componentInstance.handoffMarketplace(artifact as never);
    await fixture.componentInstance.handoffCampaign(artifact as never);
    expect(ai.studioListingHandoff).toHaveBeenCalledWith('artifact-1');
    expect(ai.studioCampaignHandoff).toHaveBeenCalledWith('artifact-1');
    expect(fixture.componentInstance.handoffStatus()).toBe('ready');
  });
});
