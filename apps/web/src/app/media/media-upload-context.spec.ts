import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter, Router } from '@angular/router';
import { vi } from 'vitest';
import { MediaUploadComponent } from './media-upload.component';
import { MediaService } from './media.service';

describe('Catalog private media upload handoff', () => {
  const id = '00000000-0000-0000-0000-000000000001';
  function create(product: string) {
    const upload = vi.fn().mockResolvedValue({ id: 'media-a' });
    TestBed.configureTestingModule({
      imports: [MediaUploadComponent],
      providers: [
        provideRouter([]),
        { provide: MediaService, useValue: { upload } },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { queryParamMap: convertToParamMap({ catalog_product_id: product }) },
          },
        },
      ],
    });
    const f = TestBed.createComponent(MediaUploadComponent);
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    f.componentInstance.selected.set(
      new File(['synthetic'], 'synthetic.png', { type: 'image/png' }),
    );
    return { c: f.componentInstance, navigate, upload };
  }
  it('returns an uploaded asset to the exact product as a picker choice, never auto-attaches', async () => {
    const { c, navigate, upload } = create(id);
    await c.upload();
    expect(upload).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledWith(['/catalog', id], {
      queryParams: { media_id: 'media-a' },
      fragment: 'images-title',
    });
  });
  it('rejects arbitrary return URLs and keeps the normal owned media route', async () => {
    const { c, navigate } = create('https://example.com');
    await c.upload();
    expect(c.catalogProductId).toBeNull();
    expect(navigate).toHaveBeenCalledWith(['/media', 'media-a']);
  });
});
