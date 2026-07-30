import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import type { MediaAsset } from '@vayujit/shared';
import { MediaService } from './media.service';

@Component({
  selector: 'app-media-details',
  imports: [RouterLink],
  template: `
    <section class="media-page">
      <header class="media-header">
        <h1>Media details</h1>
        <a routerLink="/media">Back to library</a>
      </header>
      @if (error()) {
        <p class="media-error" role="alert">{{ error() }}</p>
      }
      @if (item(); as value) {
        <article class="media-card">
          <img class="media-thumb" [src]="api.previewUrl(value.id)" [alt]="value.safe_filename" />
          <h2>{{ value.safe_filename }}</h2>
          <dl>
            <dt>Original filename</dt>
            <dd>{{ value.original_filename }}</dd>
            <dt>Type</dt>
            <dd>{{ value.mime_type }}</dd>
            <dt>Dimensions</dt>
            <dd>{{ value.width }}×{{ value.height }}</dd>
            <dt>Size</dt>
            <dd>{{ value.size_bytes }} bytes</dd>
            <dt>Checksum</dt>
            <dd>{{ value.checksum_sha256 }}</dd>
            <dt>Uploaded</dt>
            <dd>{{ value.created_at }}</dd>
            <dt>Usage</dt>
            <dd>{{ value.usage_count }}</dd>
            <dt>Status</dt>
            <dd>{{ value.status }}</dd>
          </dl>
          <button (click)="toggle(value)">
            {{ value.status === 'archived' ? 'Restore' : 'Archive' }}
          </button>
        </article>
      }
    </section>
  `,
  styleUrl: './media.css',
})
export class MediaDetailsComponent implements OnInit {
  readonly api = inject(MediaService);
  private readonly route = inject(ActivatedRoute);
  readonly item = signal<MediaAsset | null>(null);
  readonly error = signal('');
  private id = '';
  ngOnInit(): void {
    this.id = this.route.snapshot.paramMap.get('id') ?? '';
    void this.load();
  }
  private async load() {
    try {
      this.item.set(await this.api.get(this.id));
    } catch {
      this.error.set('Media item was not found.');
    }
  }
  async toggle(value: MediaAsset) {
    this.item.set(
      await this.api.setArchived(value.id, value.status === 'archived' ? 'restore' : 'archive'),
    );
  }
}
