import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { BrandVoiceWorkspaceComponent } from './brand-voice-workspace.component';
import { PresetWorkspaceComponent } from './preset-workspace.component';
import { AIService } from './ai.service';
import { BrandService } from '../brands/brand.service';
import { ProductService } from '../products/product.service';
import { DestinationFormComponent } from '../publishing/destination-form.component';
import { PublishingService } from '../publishing/publishing.service';
import { MediaService } from '../media/media.service';
import { WorkflowTimelineComponent } from '../workflows/workflow-timeline.component';

describe('WP7A4 browser-owned corrections', () => {
  it.each([
    ['voice', BrandVoiceWorkspaceComponent],
    ['preset', PresetWorkspaceComponent],
  ] as const)(
    'renders asynchronous %s list changes without manual change detection',
    async (kind, component) => {
      const list = vi.fn().mockResolvedValue([]);
      const create = vi.fn().mockImplementation(() => {
        list.mockResolvedValue([{ id: 'new', name: 'Saved fixture', version: 1 }]);
        return Promise.resolve();
      });
      TestBed.configureTestingModule({
        providers: [
          provideRouter([]),
          {
            provide: AIService,
            useValue: {
              studioBrandVoices: list,
              studioPresets: list,
              createStudioBrandVoice: create,
              createStudioPreset: create,
            },
          },
          { provide: BrandService, useValue: { list: vi.fn().mockResolvedValue({ items: [] }) } },
          { provide: ProductService, useValue: { list: vi.fn().mockResolvedValue({ items: [] }) } },
        ],
      });
      // Both concrete components are tested; keep their distinct form contracts.
      const fixture =
        kind === 'voice'
          ? TestBed.createComponent(BrandVoiceWorkspaceComponent)
          : TestBed.createComponent(PresetWorkspaceComponent);
      await fixture.whenStable();
      fixture.componentInstance.draft.name = 'Saved fixture';
      await fixture.componentInstance.save();
      await fixture.whenStable();
      expect(fixture.nativeElement.textContent).toContain('Saved fixture');
      expect(create).toHaveBeenCalledOnce();
      expect(component).toBeTruthy();
    },
  );
  it('does not send immutable connector identity in destination PATCH', async () => {
    const update = vi.fn().mockResolvedValue({ id: 'destination' });
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: { get: () => 'destination' } } },
        },
        {
          provide: PublishingService,
          useValue: {
            updateDestination: update,
            destination: vi.fn().mockResolvedValue({
              name: 'Original',
              connector_key: 'mock_publisher_v1',
              configuration: { channel_name: 'LOCAL', publication_prefix: 'PUB' },
            }),
          },
        },
        { provide: BrandService, useValue: { list: vi.fn().mockResolvedValue({ items: [] }) } },
        { provide: MediaService, useValue: { list: vi.fn().mockResolvedValue({ items: [] }) } },
      ],
    });
    const c = TestBed.runInInjectionContext(() => new DestinationFormComponent());
    c.form.patchValue({ name: 'Too early', channel_name: 'LOCAL' });
    await c.save();
    expect(update).not.toHaveBeenCalled();
    c.ngOnInit();
    await vi.waitFor(() => {
      expect(c.ready()).toBe(true);
    });
    c.editing.set(true);
    c.form.patchValue({ name: 'Updated', channel_name: 'LOCAL' });
    await c.save();
    expect(update).toHaveBeenCalledOnce();
    expect(update.mock.calls[0][1]).not.toHaveProperty('connector_key');
    expect(update.mock.calls[0][1]).toHaveProperty('name', 'Updated');
  });
  it('gives the named workflow timeline a valid grouping role', async () => {
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    const fixture = TestBed.createComponent(WorkflowTimelineComponent);
    fixture.componentRef.setInput('steps', []);
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('.wf-timeline').getAttribute('role')).toBe('group');
  });
});
