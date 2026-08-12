import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { RouterLink } from '@angular/router';
import {
  SocialAccount,
  SocialAnalyticsSummary,
  SocialPost,
  SocialRecoveryItem,
  SocialService,
} from './social.service';

@Component({
  selector: 'app-social-workspace',
  imports: [RouterLink],
  template: `
    <section class="social-page" aria-labelledby="social-title">
      <header class="social-header">
        <div>
          <p class="eyebrow">Multi-channel publishing</p>
          <h1 id="social-title">Social</h1>
          <p>
            Create, review, schedule, publish, reconcile, and analyze local-certified social posts.
          </p>
        </div>
        <a class="social-button" routerLink="/social/compose">Compose post</a>
      </header>
      @if (error()) {
        <p class="social-error" role="alert">{{ error() }}</p>
      }
      <nav class="social-tabs" aria-label="Social workspace">
        <a routerLink="/social">Overview</a><a routerLink="/social/compose">Compose</a
        ><a routerLink="/calendar">Calendar</a><a routerLink="/social/accounts">Accounts</a
        ><a routerLink="/social/analytics">Analytics</a
        ><a routerLink="/social/recovery">Recovery</a>
      </nav>
      @if (section() === 'compose') {
        <article class="social-card social-wide" aria-labelledby="compose-title">
          <h2 id="compose-title">Compose wizard</h2>
          <ol class="wizard-steps">
            @for (step of composeSteps; track step) {
              <li>{{ step }}</li>
            }
          </ol>
          <p>
            Select a Brand, Product, platform, exact approved Artifact, and Media before preview and
            approval.
          </p>
        </article>
      }
      @if (section() === 'accounts') {
        <article class="social-card social-wide" aria-labelledby="accounts-title">
          <h2 id="accounts-title">Accounts and diagnostics</h2>
          <p>
            Configure, validate, enable, disable, replace credentials, or archive owner-scoped
            accounts.
          </p>
          @for (account of accounts(); track account.id) {
            <div class="platform-row">
              <strong>{{ account.display_name }}</strong
              ><span
                >{{ account.platform }} - {{ account.validation_status }} -
                {{ account.enabled ? 'enabled' : 'disabled' }}</span
              >
            </div>
          }
        </article>
      }
      @if (section() === 'recovery') {
        <article class="social-card social-wide" aria-labelledby="recovery-title">
          <h2 id="recovery-title">Recovery</h2>
          @if (!recovery().length) {
            <p>No Social posts need recovery.</p>
          }
          @for (item of recovery(); track item.post_id) {
            <div class="platform-row">
              <strong>{{ item.platform }} / {{ item.content_type }}</strong
              ><span
                >{{ item.failure_code || item.lifecycle_status }} -
                {{ item.available_actions.join(', ') }}</span
              >
            </div>
          }
        </article>
      }
      @if (section() === 'analytics') {
        <article class="social-card social-wide" aria-labelledby="analytics-title">
          <h2 id="analytics-title">Analytics</h2>
          @if (summary(); as value) {
            <div class="analytics-grid">
              <span>Published {{ value.published }}</span
              ><span>Scheduled {{ value.scheduled }}</span
              ><span>Failed {{ value.failed }}</span
              ><span>Source {{ value.synthetic ? 'synthetic test data' : 'connector data' }}</span>
            </div>
          }
        </article>
      }
      <div class="social-grid">
        <article class="social-card">
          <h2>Platforms</h2>
          @for (platform of platforms(); track platform['key']) {
            <div class="platform-row">
              <strong>{{ platform['name'] }}</strong
              ><span>{{ platform['status'] }}</span>
            </div>
          }
        </article>
        <article class="social-card">
          <h2>Accounts</h2>
          @if (!accounts().length) {
            <p>No social accounts configured.</p>
          }
          @for (account of accounts(); track account.id) {
            <div class="platform-row">
              <strong>{{ account.display_name }}</strong
              ><span>{{ account.platform }} · {{ account.validation_status }}</span>
            </div>
          }
        </article>
        <article class="social-card social-wide">
          <h2>Recent posts</h2>
          @if (!posts().length) {
            <p>No social posts yet. Start with Compose.</p>
          }
          <table>
            <thead>
              <tr>
                <th scope="col">Platform</th>
                <th scope="col">Format</th>
                <th scope="col">Status</th>
                <th scope="col">Remote ID</th>
              </tr>
            </thead>
            <tbody>
              @for (post of posts(); track post.id) {
                <tr>
                  <td>{{ post.platform }}</td>
                  <td>{{ post.content_type }}</td>
                  <td>{{ post.lifecycle_status }}</td>
                  <td>{{ post.remote_publication_id || '—' }}</td>
                </tr>
              }
            </tbody>
          </table>
        </article>
      </div>
    </section>
  `,
  styles: `
    :host {
      display: block;
      padding: 2rem;
      color: #102f35;
    }
    .social-header {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      align-items: flex-start;
      flex-wrap: wrap;
    }
    h1 {
      font-size: clamp(2.2rem, 5vw, 4rem);
      margin: 0.25rem 0;
    }
    h2 {
      margin-top: 0;
    }
    .eyebrow {
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: #17617a;
      font-weight: 700;
    }
    .social-button {
      background: #155f78;
      color: white;
      border-radius: 0.5rem;
      padding: 0.8rem 1rem;
      text-decoration: none;
    }
    .social-tabs {
      display: flex;
      gap: 1rem;
      flex-wrap: wrap;
      margin: 2rem 0 1.5rem;
    }
    .social-tabs a {
      color: #155f78;
      font-weight: 600;
    }
    .social-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
      gap: 1rem;
    }
    .social-card {
      border: 1px solid #c6d9dc;
      border-radius: 0.75rem;
      padding: 1.25rem;
      background: #fff;
    }
    .social-wide {
      grid-column: 1 / -1;
      overflow-x: auto;
    }
    .platform-row {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      padding: 0.75rem 0;
      border-bottom: 1px solid #e5eef0;
    }
    .platform-row span {
      color: #507279;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th,
    td {
      padding: 0.7rem;
      text-align: left;
      border-bottom: 1px solid #e5eef0;
    }
    .wizard-steps {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
      gap: 0.6rem 1.2rem;
      padding-left: 1.4rem;
    }
    .analytics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
      gap: 0.75rem;
    }
    .analytics-grid span {
      border: 1px solid #c6d9dc;
      border-radius: 0.5rem;
      padding: 0.75rem;
    }
    .social-error {
      color: #9b1c1c;
      background: #fff0f0;
      padding: 1rem;
    }
    @media (max-width: 640px) {
      :host {
        padding: 1rem;
      }
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SocialWorkspaceComponent {
  private readonly social = inject(SocialService);
  private readonly router = inject(Router);
  readonly section = signal(this.router.url.split('?')[0].split('/')[2] || 'overview');
  readonly composeSteps = [
    'Brand / Product',
    'Platform(s)',
    'Format',
    'Content',
    'Media',
    'Caption / Metadata',
    'CTA / Link',
    'Schedule',
    'Preview',
    'Review',
    'Queue',
  ];
  readonly accounts = signal<SocialAccount[]>([]);
  readonly posts = signal<SocialPost[]>([]);
  readonly platforms = signal<Array<Record<string, unknown>>>([]);
  readonly recovery = signal<SocialRecoveryItem[]>([]);
  readonly summary = signal<SocialAnalyticsSummary | null>(null);
  readonly error = signal('');

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    try {
      const [accounts, posts, platforms, recovery, summary] = await Promise.all([
        this.social.accounts(),
        this.social.posts(),
        this.social.platforms(),
        this.social.recovery(),
        this.social.analytics(),
      ]);
      this.accounts.set(accounts);
      this.posts.set(posts);
      this.platforms.set(platforms);
      this.recovery.set(recovery);
      this.summary.set(summary);
    } catch {
      this.error.set('Social data is unavailable. Check the API connection and try again.');
    }
  }
}
