import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { MediaListComponent } from './media-list.component';
import { MediaService } from './media.service';

describe('MediaListComponent', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: MediaService,
          useValue: {
            list: () =>
              Promise.resolve({
                items: [
                  {
                    id: 'media-1',
                    safe_filename: 'image.png',
                    mime_type: 'image/png',
                    width: 2,
                    height: 3,
                    size_bytes: 100,
                    status: 'ready',
                    usage_count: 0,
                  },
                ],
                page: 1,
                pages: 1,
              }),
            previewUrl: (id: string) => `/api/v1/media/${id}/preview`,
          },
        },
      ],
    });
  });

  it('loads the responsive Media Library grid', async () => {
    const fixture = TestBed.createComponent(MediaListComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.media-grid')).toBeTruthy();
    expect(fixture.nativeElement.textContent).toContain('image.png');
  });

  it('supports compact list view', async () => {
    const fixture = TestBed.createComponent(MediaListComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.componentInstance.listView.set(true);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.media-grid.list')).toBeTruthy();
  });
});
