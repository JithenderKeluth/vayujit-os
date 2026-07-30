import { provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { MediaService } from './media.service';
import { MediaUploadComponent } from './media-upload.component';
import { Component } from '@angular/core';

@Component({ template: '' })
class RouteStubComponent {}

describe('MediaUploadComponent', () => {
  const uploaded = {
    id: 'media-1',
    safe_filename: 'image.png',
    duplicate_reused: true,
    width: 2,
    height: 3,
  };
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: 'media/:id', component: RouteStubComponent }]),
        { provide: MediaService, useValue: { upload: () => Promise.resolve(uploaded) } },
      ],
    });
  });

  it('provides a keyboard-accessible file picker and drag-and-drop alternative', () => {
    const fixture = TestBed.createComponent(MediaUploadComponent);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('input[type=file]')).toBeTruthy();
    expect(fixture.nativeElement.textContent).toContain('Drag and drop');
  });

  it('rejects unsupported files before upload', () => {
    const component = TestBed.createComponent(MediaUploadComponent).componentInstance;
    component.select({
      target: { files: [new File(['unsafe'], 'unsafe.svg', { type: 'image/svg+xml' })] },
    } as unknown as Event);
    expect(component.error()).toContain('JPEG, PNG, or WebP');
    expect(component.selected()).toBeNull();
  });

  it('announces duplicate reuse from the backend', async () => {
    const component = TestBed.createComponent(MediaUploadComponent).componentInstance;
    component.selected.set(new File(['png'], 'image.png', { type: 'image/png' }));
    await component.upload();
    expect(component.status()).toContain('Duplicate detected');
  });
});
