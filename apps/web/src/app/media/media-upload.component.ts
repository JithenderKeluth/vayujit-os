import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import type { MediaAsset } from '@vayujit/shared';
import { MediaService } from './media.service';

@Component({
  selector: 'app-media-upload',
  imports: [RouterLink],
  template: `
    <section class="media-page" aria-labelledby="upload-title">
      <header class="media-header">
        <div>
          <h1 id="upload-title">Upload image</h1>
          <p>JPEG, PNG, or WebP up to 10 MB.</p>
        </div>
        <a routerLink="/media">Back to library</a>
      </header>
      @if (error()) {
        <p class="media-error" role="alert">{{ error() }}</p>
      }
      @if (status()) {
        <p role="status">{{ status() }}</p>
      }
      <div
        class="media-drop"
        [class.dragging]="dragging()"
        (dragover)="drag($event, true)"
        (dragleave)="drag($event, false)"
        (drop)="drop($event)"
      >
        <div>
          <p>Drag and drop an image here</p>
          <p>or</p>
          <label
            >Choose local image
            <input
              #picker
              type="file"
              accept="image/jpeg,image/png,image/webp"
              (change)="select($event)"
          /></label>
        </div>
      </div>
      @if (preview(); as source) {
        <article class="media-card">
          <img class="media-thumb" [src]="source" alt="Selected image preview" />
          <p>{{ selected()?.name }} · {{ selected()?.type }} · {{ size(selected()?.size || 0) }}</p>
          <div class="media-actions">
            <button [disabled]="busy()" (click)="upload()">
              {{ busy() ? 'Validating and storing…' : 'Upload securely' }}</button
            ><button [disabled]="busy()" (click)="clear()">Cancel selection</button>
          </div>
        </article>
      }
      @if (result(); as item) {
        <article class="media-card">
          <h2>{{ item.duplicate_reused ? 'Existing media reused' : 'Upload complete' }}</h2>
          <p>{{ item.safe_filename }} · {{ item.width }}×{{ item.height }}</p>
          <a [routerLink]="['/media', item.id]">View media details</a>
        </article>
      }
    </section>
  `,
  styleUrl: './media.css',
})
export class MediaUploadComponent {
  private readonly api = inject(MediaService);
  private readonly router = inject(Router);
  readonly selected = signal<File | null>(null);
  readonly preview = signal('');
  readonly dragging = signal(false);
  readonly busy = signal(false);
  readonly status = signal('');
  readonly error = signal('');
  readonly result = signal<MediaAsset | null>(null);
  select(event: Event) {
    this.useFile((event.target as HTMLInputElement).files?.[0]);
  }
  drag(event: DragEvent, active: boolean) {
    event.preventDefault();
    this.dragging.set(active);
  }
  drop(event: DragEvent) {
    event.preventDefault();
    this.dragging.set(false);
    this.useFile(event.dataTransfer?.files[0]);
  }
  private useFile(file?: File) {
    this.error.set('');
    this.result.set(null);
    if (!file || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      this.error.set('Choose a JPEG, PNG, or WebP image.');
      return;
    }
    this.clear();
    this.selected.set(file);
    this.preview.set(URL.createObjectURL(file));
  }
  clear() {
    if (this.preview()) URL.revokeObjectURL(this.preview());
    this.preview.set('');
    this.selected.set(null);
  }
  async upload() {
    const file = this.selected();
    if (!file || this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.status.set('Validating, hashing, and storing image…');
    try {
      const item = await this.api.upload(file);
      this.result.set(item);
      this.status.set(
        item.duplicate_reused ? 'Duplicate detected; existing media reused.' : 'Media is ready.',
      );
      this.clear();
      void this.router.navigate(['/media', item.id]);
    } catch {
      this.error.set('The image was rejected or could not be stored.');
      this.status.set('Upload failed.');
    } finally {
      this.busy.set(false);
    }
  }
  size(value: number) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
}
