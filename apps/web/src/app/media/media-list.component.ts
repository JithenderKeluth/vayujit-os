import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { MediaAsset } from '@vayujit/shared';
import { MediaService } from './media.service';

@Component({
  selector: 'app-media-list',
  imports: [FormsModule, RouterLink],
  template: `
    <section class="media-page" aria-labelledby="media-title">
      <header class="media-header">
        <div>
          <h1 id="media-title">Media Library</h1>
          <p>Secure owner-scoped JPEG, PNG, and WebP assets.</p>
        </div>
        <a routerLink="/media/upload">Upload image</a>
      </header>
      <form class="media-toolbar" (ngSubmit)="load(1)">
        <label>Search <input name="search" [(ngModel)]="search" /></label>
        <label
          >MIME type
          <select name="mime" [(ngModel)]="mime">
            <option value="">All</option>
            <option value="image/jpeg">JPEG</option>
            <option value="image/png">PNG</option>
            <option value="image/webp">WebP</option>
          </select></label
        >
        <label><input type="checkbox" name="archived" [(ngModel)]="archived" /> Archived</label>
        <label
          >Sort
          <select name="sort" [(ngModel)]="sort">
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
            <option value="name">Name</option>
            <option value="size">Size</option>
          </select></label
        >
        <button>Apply</button>
        <button type="button" (click)="listView.set(!listView())">
          {{ listView() ? 'Grid view' : 'List view' }}
        </button>
      </form>
      @if (error()) {
        <p class="media-error" role="alert">{{ error() }}</p>
      }
      @if (loading()) {
        <p role="status">Loading media…</p>
      } @else if (!items().length) {
        <div class="media-card">
          <h2>No media found</h2>
          <p>Upload an image or change the filters.</p>
        </div>
      } @else {
        <div class="media-grid" [class.list]="listView()">
          @for (item of items(); track item.id) {
            <article class="media-card">
              <img class="media-thumb" [src]="api.previewUrl(item.id)" [alt]="item.safe_filename" />
              <h2>
                <a [routerLink]="['/media', item.id]">{{ item.safe_filename }}</a>
              </h2>
              <p>
                {{ item.mime_type }} · {{ item.width }}×{{ item.height }} ·
                {{ size(item.size_bytes) }}
              </p>
              <p class="media-status">{{ item.status }} · used {{ item.usage_count }} times</p>
            </article>
          }
        </div>
      }
      <nav class="media-actions" aria-label="Media pages">
        <button [disabled]="page() <= 1" (click)="load(page() - 1)">Previous</button>
        <span>Page {{ page() }} of {{ pages() || 1 }}</span>
        <button [disabled]="page() >= pages()" (click)="load(page() + 1)">Next</button>
      </nav>
    </section>
  `,
  styleUrl: './media.css',
})
export class MediaListComponent implements OnInit {
  readonly api = inject(MediaService);
  readonly items = signal<MediaAsset[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly page = signal(1);
  readonly pages = signal(0);
  readonly listView = signal(false);
  search = '';
  mime = '';
  archived = false;
  sort = 'newest';
  ngOnInit(): void {
    void this.load(1);
  }
  async load(page: number) {
    this.loading.set(true);
    this.error.set('');
    try {
      const result = await this.api.list({
        search: this.search,
        mimeType: this.mime,
        archived: this.archived,
        sort: this.sort,
        page,
      });
      this.items.set(result.items);
      this.page.set(result.page);
      this.pages.set(result.pages);
    } catch {
      this.error.set('Unable to load the Media Library.');
    } finally {
      this.loading.set(false);
    }
  }
  size(value: number) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
}
