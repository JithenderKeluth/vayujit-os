/* eslint-disable @typescript-eslint/no-base-to-string */
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import {
  SocialAccount,
  SocialAnalyticsSummary,
  SocialHistoryItem,
  SocialPost,
  SocialPreview,
  SocialRecoveryItem,
  SocialService,
} from './social.service';

type Platform = 'youtube' | 'instagram' | 'facebook';
@Component({
  selector: 'app-social-workspace',
  imports: [FormsModule, RouterLink],
  template: `
    <section class="social-page" aria-labelledby="social-title">
      <header class="social-header">
        <div>
          <p class="eyebrow">Multi-channel publishing</p>
          <h1 id="social-title">Social Video workspace</h1>
          <p>
            Exact-version Video publishing with safe review, scheduling, Recovery, and synthetic
            analytics.
          </p>
        </div>
        <button type="button" (click)="load()" [disabled]="loading()">Refresh</button>
      </header>
      @if (loading()) {
        <p role="status">Loading Social Video data...</p>
      }
      @if (error()) {
        <p class="social-error" role="alert">
          {{ error() }} <button type="button" (click)="load()">Retry</button>
        </p>
      }
      <nav class="social-tabs" aria-label="Social workspace">
        <a routerLink="/social">Overview</a><a routerLink="/social/compose">Compose</a
        ><a routerLink="/calendar">Calendar</a><a routerLink="/social/accounts">Accounts</a
        ><a routerLink="/social/analytics">Analytics</a
        ><a routerLink="/social/recovery">Recovery</a>
      </nav>
      @if (detail(); as post) {
        <article class="card wide">
          <h2>{{ post.platform }} / {{ post.content_type }} SocialPost</h2>
          <div class="detail-grid">
            <dl>
              <dt>Product</dt>
              <dd>
                <code>{{ post.product_id || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }}</code>
              </dd>
              <dt>Video</dt>
              <dd>
                <code>{{ post.video_output_id || post.content_artifact_id }}</code> v{{
                  post.video_version || post.content_artifact_version
                }}
              </dd>
              <dt>Metadata</dt>
              <dd>
                {{ post.metadata_artifact_id || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }} v{{
                  post.metadata_artifact_version || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â'
                }}
              </dd>
              <dt>Thumbnail</dt>
              <dd>
                {{ post.thumbnail_output_id || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }} v{{
                  post.thumbnail_version || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â'
                }}
              </dd>
              <dt>Caption</dt>
              <dd>
                {{ post.caption_track_id || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }} v{{
                  post.caption_version || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â'
                }}
              </dd>
              <dt>Status</dt>
              <dd>
                <span class="state">{{ post.lifecycle_status }}</span>
              </dd>
              <dt>Remote ID</dt>
              <dd>{{ post.remote_publication_id || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }}</dd>
              <dt>Correlation</dt>
              <dd>
                <code>{{ post.correlation_id || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }}</code>
              </dd>
            </dl>
            <div>
              <h3>History</h3>
              @for (event of history(); track event.id) {
                <p class="timeline">
                  <time>{{ event.occurred_at }}</time> <strong>{{ event.action }}</strong>
                  {{ safeSummary(event.metadata) }}
                </p>
              } @empty {
                <p class="empty">No history events yet.</p>
              }
            </div>
          </div>
        </article>
      }
      @if (!detail()) {
        @if (isCompose()) {
          <article class="card wide" aria-labelledby="compose-title">
            <h2 id="compose-title">Compose Video post</h2>
            <p>
              Step {{ step() }} of 10 ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· exact immutable identities are required.
            </p>
            <ol class="wizard">
              @for (name of steps; track name; let i = $index) {
                <li [class.current]="step() === i + 1">{{ i + 1 }}. {{ name }}</li>
              }
            </ol>
            @if (step() <= 2) {
              <fieldset>
                <legend>Platform and format</legend>
                <div class="form-grid">
                  <label
                    >Platform<select [(ngModel)]="draft.platform" (ngModelChange)="syncFormat()">
                      <option value="youtube">YouTube</option>
                      <option value="instagram">Instagram</option>
                      <option value="facebook">Facebook</option>
                    </select></label
                  ><label
                    >Format<select [(ngModel)]="draft.format">
                      <option value="">Select</option>
                      @for (format of compatibleFormats(); track format) {
                        <option [value]="format">{{ label(format) }}</option>
                      }
                    </select></label
                  >
                </div>
                <p class="hint">Formats come from the backend capability registry.</p>
              </fieldset>
            }
            @if (step() === 3) {
              <fieldset>
                <legend>Product and Brand</legend>
                <div class="form-grid">
                  <label
                    >Brand ID<input
                      [(ngModel)]="draft.brandId"
                      placeholder="Exact Brand UUID" /></label
                  ><label
                    >Product ID<input
                      [(ngModel)]="draft.productId"
                      placeholder="Exact Product UUID"
                  /></label>
                </div>
              </fieldset>
            }
            @if (step() === 4) {
              <fieldset>
                <legend>Approved Video</legend>
                <label
                  >Approved Video selector<select
                    [ngModel]="draft.videoId"
                    (ngModelChange)="selectVideo($event)"
                  >
                    <option value="">Select an approved Video</option>
                    @for (video of eligibleVideos(); track video['id']) {
                      <option [value]="video['id']">
                        {{ video['video_type'] || video['target_channel'] || 'Video' }} · v{{
                          video['version'] || video['video_version'] || 1
                        }}
                        · {{ video['duration_seconds'] || '—' }}s
                      </option>
                    }
                  </select></label
                >
                <div class="form-grid">
                  <label
                    >Video Output ID<input
                      [(ngModel)]="draft.videoId"
                      placeholder="Exact approved Video UUID" /></label
                  ><label
                    >Video version<input type="number" min="1" [(ngModel)]="draft.videoVersion"
                  /></label>
                </div>
              </fieldset>
            }
            @if (step() === 5) {
              <fieldset>
                <legend>Metadata Artifact</legend>
                <div class="form-grid">
                  <label
                    >Artifact ID<input
                      [(ngModel)]="draft.metadataId"
                      placeholder="Exact approved Artifact UUID" /></label
                  ><label
                    >Artifact version<input
                      type="number"
                      min="1"
                      [(ngModel)]="draft.metadataVersion"
                  /></label>
                </div>
              </fieldset>
            }
            @if (step() === 6) {
              <fieldset>
                <legend>Thumbnail</legend>
                <div class="form-grid">
                  <label
                    >Image Output ID<input
                      [(ngModel)]="draft.thumbnailId"
                      placeholder="Optional exact Image Output UUID" /></label
                  ><label
                    >Thumbnail version<input
                      type="number"
                      min="1"
                      [(ngModel)]="draft.thumbnailVersion"
                  /></label>
                </div>
              </fieldset>
            }
            @if (step() === 7) {
              <fieldset>
                <legend>Caption Track</legend>
                <div class="form-grid">
                  <label
                    >Track ID<input
                      [(ngModel)]="draft.captionTrackId"
                      placeholder="Optional Caption Track UUID" /></label
                  ><label
                    >Caption version<input
                      type="number"
                      min="1"
                      [(ngModel)]="draft.captionVersion" /></label
                  ><label>Caption<textarea rows="3" [(ngModel)]="draft.caption"></textarea></label>
                </div>
              </fieldset>
            }
            @if (step() === 8) {
              <fieldset>
                <legend>Social account</legend>
                <label
                  >Account<select [(ngModel)]="draft.accountId">
                    <option value="">Select enabled validated account</option>
                    @for (account of eligibleAccounts(); track account.id) {
                      <option [value]="account.id">
                        {{ account.display_name }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· {{ account.platform }}
                      </option>
                    }
                  </select></label
                >
                @if (!eligibleAccounts().length) {
                  <p class="empty">No enabled validated account matches {{ draft.platform }}.</p>
                }
              </fieldset>
            }
            @if (step() === 9) {
              <fieldset>
                <legend>Publish now or schedule</legend>
                <div class="form-grid">
                  <label
                    >Mode<select [(ngModel)]="draft.mode">
                      <option value="now">Publish now</option>
                      <option value="schedule">Future schedule</option>
                    </select></label
                  >
                  @if (draft.mode === 'schedule') {
                    <label
                      >Date and time<input
                        type="datetime-local"
                        [(ngModel)]="draft.localDateTime" /></label
                    ><label
                      >IANA timezone<input [(ngModel)]="draft.timezone" placeholder="Asia/Kolkata"
                    /></label>
                  }
                </div>
                <p class="hint">The server validates DST and resolves UTC.</p>
              </fieldset>
            }
            @if (step() === 10) {
              <fieldset>
                <legend>Review and confirm</legend>
                <dl>
                  <dt>Platform / format</dt>
                  <dd>{{ draft.platform }} / {{ label(draft.format) }}</dd>
                  <dt>Product</dt>
                  <dd>
                    <code>{{ draft.productId || 'missing' }}</code>
                  </dd>
                  <dt>Video</dt>
                  <dd>
                    <code>{{ draft.videoId || 'missing' }}</code> v{{ draft.videoVersion }}
                  </dd>
                  <dt>Metadata</dt>
                  <dd>
                    <code>{{ draft.metadataId || 'missing' }}</code> v{{ draft.metadataVersion }}
                  </dd>
                  <dt>Account</dt>
                  <dd>{{ selectedAccount()?.display_name || 'missing or disabled' }}</dd>
                </dl>
                <button type="button" (click)="previewPost()" [disabled]="busy() || !ready()">
                  Preview exact post
                </button>
                @if (preview(); as value) {
                  <div class="preview" aria-live="polite">
                    <p>
                      Fingerprint: <code>{{ value.fingerprint }}</code>
                    </p>
                    <p>{{ readiness(value.readiness) }}</p>
                    <button
                      class="primary"
                      type="button"
                      (click)="confirmPost()"
                      [disabled]="busy()"
                    >
                      Confirm {{ draft.mode === 'now' ? 'Publish Now' : 'Schedule' }}
                    </button>
                  </div>
                }
              </fieldset>
            }
            <div class="wizard-actions">
              <button type="button" (click)="step.set(step() - 1)" [disabled]="step() === 1">
                Back</button
              ><button type="button" (click)="step.set(step() + 1)" [disabled]="step() === 10">
                Next
              </button>
            </div>
            @if (message()) {
              <p class="success" role="status">{{ message() }}</p>
            }
            @if (composeError()) {
              <p class="social-error" role="alert">{{ composeError() }}</p>
            }
          </article>
        } @else if (isChannel()) {
          <article class="card wide">
            <h2>Product Channel Ãƒâ€šÃ‚Â· Social Video</h2>
            <p>Server projection only; no client-side eligibility reconstruction.</p>
            <label
              >Product ID<input [(ngModel)]="channelProductId" placeholder="Exact Product UUID"
            /></label>
            <button type="button" (click)="loadChannel()">Load channel</button>
            @if (channel(); as value) {
              @for (row of value.video; track row['post_id']) {
                <div class="channel-row">
                  <strong>{{ row['platform'] }} / {{ row['format'] }}</strong>
                  <span
                    >Current v{{ row['current_video_version'] }} Ãƒâ€šÃ‚Â· Available v{{
                      row['latest_approved_video_version']
                    }}
                    Ãƒâ€šÃ‚Â· {{ row['update_available'] ? 'Update available' : 'Current' }}</span
                  >
                  <button
                    type="button"
                    (click)="previewChannelUpdate(row)"
                    [disabled]="!row['update_available']"
                  >
                    Preview Video Update
                  </button>
                  <a [routerLink]="['/social/posts', row['post_id']]">Open SocialPost</a>
                </div>
              } @empty {
                <p class="empty">No Social Video channel projection for this Product.</p>
              }
            }
          </article>
        } @else if (isRecovery()) {
          <article class="card wide">
            <h2>Video Recovery</h2>
            <p>Actions are rendered only from the backend Recovery projection.</p>
            @for (item of recovery(); track item.post_id) {
              <div class="recovery">
                <div>
                  <strong>{{ item.platform }} / {{ item.content_type }}</strong>
                  <p>{{ item.safe_failure_message || 'Safe review required.' }}</p>
                  <code>{{ item.failure_code || 'unknown' }}</code>
                </div>
                <div>
                  @for (action of item.available_actions; track action) {
                    <button type="button" (click)="runRecovery(item, action)">
                      {{ label(action) }}
                    </button>
                  }
                </div>
              </div>
            } @empty {
              <p class="empty">No recoverable Video failures.</p>
            }
          </article>
        } @else if (isAccounts()) {
          <article class="card wide">
            <h2>Accounts and diagnostics</h2>
            <p>
              Credentials are write-only and never displayed. Disabled accounts block confirmation.
            </p>
            @for (account of accounts(); track account.id) {
              <div class="row">
                <strong>{{ account.display_name }}</strong
                ><span
                  >{{ account.platform }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
                  {{ account.environment || 'local' }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
                  {{ account.enabled ? 'Enabled' : 'Disabled' }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
                  {{ account.validation_status }}</span
                >
              </div>
            } @empty {
              <p class="empty">No Social accounts configured.</p>
            }
          </article>
        } @else if (isAnalytics()) {
          <article class="card wide">
            <div class="section-heading">
              <h2>Video analytics</h2>
              <span class="synthetic">Synthetic</span>
            </div>
            <p>
              Unknown values remain empty; synthetic values never imply live platform analytics.
            </p>
            @if (summary(); as value) {
              <div class="analytics-grid">
                <span
                  >Publications
                  <strong>{{ value.video?.publications ?? value.publications }}</strong></span
                ><span
                  >Published <strong>{{ value.published }}</strong></span
                ><span
                  >Failed <strong>{{ value.failed }}</strong></span
                ><span
                  >Scheduled <strong>{{ value.scheduled }}</strong></span
                ><span
                  >Views
                  <strong>{{
                    value.video?.views ?? 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â'
                  }}</strong></span
                ><span
                  >Engagement
                  <strong>{{
                    value.video?.engagement ?? 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â'
                  }}</strong></span
                >
              </div>
            } @else {
              <p class="empty">No metrics available.</p>
            }
          </article>
        } @else {
          <section class="social-grid" aria-label="Social overview">
            <article class="card wide">
              <h2>Video publication readiness</h2>
              <div class="metrics">
                @for (metric of metrics(); track metric.label) {
                  <span
                    ><b>{{ metric.label }}</b
                    ><strong>{{ metric.value }}</strong></span
                  >
                }
              </div>
            </article>
            <article class="card">
              <h2>Connected accounts</h2>
              @if (!accounts().length) {
                <p class="empty">No accounts. Configure one on the API.</p>
              }
              @for (account of accounts(); track account.id) {
                <div class="row">
                  <strong>{{ account.display_name }}</strong
                  ><span
                    >{{ account.platform }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
                    {{ account.validation_status }}</span
                  >
                </div>
              }
            </article>
            <article class="card">
              <h2>Platforms</h2>
              @for (platform of platforms(); track platform['key']) {
                <div class="row">
                  <strong>{{ platform['name'] }}</strong
                  ><span>{{ platform['status'] }}</span>
                </div>
              }
            </article>
            <article class="card wide">
              <h2>Recent Video posts</h2>
              @if (!posts().length) {
                <p class="empty">No Video posts yet. Start with Compose.</p>
              }
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Platform</th>
                      <th scope="col">Video</th>
                      <th scope="col">Status</th>
                      <th scope="col">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (post of posts(); track post.id) {
                      <tr>
                        <td>{{ post.platform }} / {{ post.content_type }}</td>
                        <td>
                          <code>{{ post.video_output_id || post.content_artifact_id }}</code> v{{
                            post.video_version || post.content_artifact_version
                          }}
                        </td>
                        <td>{{ post.lifecycle_status }}</td>
                        <td><a [routerLink]="['/social/posts', post.id]">Open details</a></td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            </article>
            <article class="card">
              <h2>Recoverable Video failures</h2>
              <p>{{ recovery().length }} require attention.</p>
            </article>
            <article class="card">
              <h2>Analytics <span class="synthetic">Synthetic</span></h2>
              <p>
                Publications: {{ summary()?.video?.publications ?? summary()?.publications ?? 0 }}
              </p>
            </article>
          </section>
        }
      }
    </section>
  `,
  styles: `
    :host {
      display: block;
    }
    .social-page {
      padding: 2rem;
      color: #102f35;
      max-width: 1440px;
      margin: auto;
    }
    .social-header,
    .section-heading {
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
    .eyebrow {
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: #17617a;
      font-weight: 700;
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
      padding: 0.55rem;
    }
    .card {
      border: 1px solid #c6d9dc;
      border-radius: 0.75rem;
      padding: 1.25rem;
      background: #fff;
    }
    .wide {
      grid-column: 1/-1;
    }
    .social-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
      gap: 1rem;
    }
    .metrics,
    .analytics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
      gap: 0.75rem;
    }
    .metrics span,
    .analytics-grid span {
      border: 1px solid #c6d9dc;
      border-radius: 0.5rem;
      padding: 0.8rem;
      display: flex;
      flex-direction: column;
      gap: 0.3rem;
    }
    .metrics strong,
    .analytics-grid strong {
      font-size: 1.7rem;
    }
    .row,
    .recovery {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      padding: 0.75rem 0;
      border-bottom: 1px solid #e5eef0;
      flex-wrap: wrap;
    }
    .row span,
    .muted,
    .hint {
      color: #507279;
    }
    .table-wrap {
      overflow-x: auto;
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
    button {
      font: inherit;
      border: 1px solid #9db8bd;
      border-radius: 0.45rem;
      padding: 0.65rem 0.85rem;
      background: #fff;
      color: #155f78;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.55;
    }
    .primary {
      background: #155f78;
      color: #fff;
    }
    .social-error {
      background: #fff0f0;
      color: #8e1c1c;
      padding: 1rem;
    }
    .success {
      background: #eef8f8;
      padding: 1rem;
    }
    .empty {
      border: 1px dashed #9db8bd;
      border-radius: 0.5rem;
      padding: 1rem;
      color: #507279;
    }
    fieldset {
      border: 1px solid #c6d9dc;
      border-radius: 0.6rem;
      padding: 1rem;
      margin: 1rem 0;
    }
    legend {
      font-weight: 700;
    }
    .form-grid,
    .detail-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
      gap: 1rem;
    }
    label {
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
      font-weight: 600;
    }
    input,
    select,
    textarea {
      font: inherit;
      padding: 0.65rem;
      border: 1px solid #9db8bd;
      border-radius: 0.4rem;
    }
    .wizard {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
      gap: 0.5rem;
    }
    .wizard .current {
      font-weight: 700;
      color: #155f78;
    }
    .progress {
      height: 0.4rem;
      background: #e5eef0;
    }
    .progress span {
      display: block;
      height: 100%;
      background: #155f78;
    }
    .wizard-actions {
      display: flex;
      justify-content: flex-end;
      gap: 0.6rem;
    }
    .state,
    .synthetic,
    .safe-badge {
      display: inline-block;
      border-radius: 999px;
      padding: 0.25rem 0.55rem;
      background: #e7f3ed;
      color: #185b43;
      font-size: 0.85rem;
    }
    .synthetic {
      background: #fff3c4;
      color: #735a00;
    }
    .timeline {
      border-left: 3px solid #9db8bd;
      padding: 0.4rem 0.8rem;
    }
    .social-button {
      background: #155f78;
      color: #fff;
      padding: 0.7rem;
      border-radius: 0.4rem;
      text-decoration: none;
    }
    @media (max-width: 640px) {
      .social-page {
        padding: 1rem;
      }
      .social-tabs {
        gap: 0.25rem;
      }
      .detail-grid {
        grid-template-columns: 1fr;
      }
      th,
      td {
        min-width: 9rem;
      }
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SocialWorkspaceComponent {
  private readonly social = inject(SocialService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  readonly channel = signal<import('./social.service').SocialChannelProjection | null>(null);
  channelProductId = '';
  readonly loading = signal(false);
  readonly error = signal('');
  readonly videos = signal<Array<Record<string, unknown>>>([]);
  readonly accounts = signal<SocialAccount[]>([]);
  readonly posts = signal<SocialPost[]>([]);
  readonly platforms = signal<Array<Record<string, unknown>>>([]);
  readonly recovery = signal<SocialRecoveryItem[]>([]);
  readonly summary = signal<SocialAnalyticsSummary | null>(null);
  readonly detail = signal<SocialPost | null>(null);
  readonly history = signal<SocialHistoryItem[]>([]);
  readonly preview = signal<SocialPreview | null>(null);
  readonly step = signal(1);
  readonly busy = signal(false);
  readonly message = signal('');
  readonly composeError = signal('');
  readonly steps = [
    'Platform',
    'Format',
    'Product',
    'Approved Video',
    'Metadata',
    'Thumbnail',
    'Caption',
    'Account',
    'Publish or Schedule',
    'Review & Confirm',
  ];
  draft = {
    platform: 'youtube' as Platform,
    format: '',
    brandId: '',
    productId: '',
    videoId: '',
    videoVersion: 1,
    metadataId: '',
    metadataVersion: 1,
    thumbnailId: '',
    thumbnailVersion: 1,
    captionTrackId: '',
    captionVersion: 1,
    caption: '',
    accountId: '',
    mode: 'now',
    localDateTime: '',
    timezone: 'Asia/Kolkata',
  };
  constructor() {
    void this.load();
  }
  isCompose() {
    return this.router.url.includes('/compose');
  }
  isChannel() {
    return this.router.url.includes('/channel');
  }
  isAccounts() {
    return this.router.url.includes('/accounts');
  }
  isAnalytics() {
    return this.router.url.includes('/analytics');
  }
  isRecovery() {
    return this.router.url.includes('/recovery');
  }
  async loadChannel() {
    if (!this.channelProductId) {
      this.error.set('Enter a Product ID to load the Social Channel projection.');
      return;
    }
    try {
      this.channel.set(await this.social.productChannel(this.channelProductId));
    } catch {
      this.error.set('Product Channel data is unavailable. Retry safely.');
    }
  }
  previewChannelUpdate(row: Record<string, unknown>) {
    this.message.set(
      'Update preview staged. Current v' +
        String(row['current_video_version']) +
        ' -> proposed v' +
        String(row['latest_approved_video_version']) +
        '. Confirmation is required.',
    );
  }
  async load() {
    this.loading.set(true);
    this.error.set('');
    try {
      const [a, p, f, r, s, v] = await Promise.all([
        this.social.accounts(),
        this.social.posts(),
        this.social.platforms(),
        this.social.recovery(),
        this.social.analytics(),
        this.social.videoGenerations(),
      ]);
      this.accounts.set(a);
      this.posts.set(p);
      this.platforms.set(f);
      this.recovery.set(r);
      this.summary.set(s);
      this.videos.set(v);
      const id = this.router.url.split('/posts/')[1]?.split('?')[0];
      if (id) {
        this.detail.set(await this.social.post(id));
        this.history.set(await this.social.history(id));
      }
      this.syncFormat();
    } catch {
      this.error.set(
        'Social Video data is unavailable. Check the authenticated API connection and retry.',
      );
    } finally {
      this.loading.set(false);
    }
  }
  metrics() {
    const p = this.posts();
    return [
      { label: 'Connected accounts', value: this.accounts().filter((a) => a.enabled).length },
      {
        label: 'Ready Video posts',
        value: p.filter((x) => x.lifecycle_status === 'approved').length,
      },
      { label: 'Draft Video posts', value: p.filter((x) => x.lifecycle_status === 'draft').length },
      {
        label: 'Scheduled Video posts',
        value: p.filter((x) => x.lifecycle_status === 'scheduled').length,
      },
      {
        label: 'Published Video posts',
        value: p.filter((x) => x.lifecycle_status === 'published').length,
      },
      {
        label: 'Failed Video posts',
        value: p.filter((x) => x.lifecycle_status === 'failed').length,
      },
      { label: 'Recoverable Video posts', value: this.recovery().length },
      { label: 'Upcoming schedules', value: p.filter((x) => Boolean(x.scheduled_at_utc)).length },
    ];
  }
  eligibleVideos() {
    return this.videos().filter(
      (video) =>
        video['status'] === 'succeeded' &&
        (video['approval_state'] === 'approved' ||
          video['output_status'] === 'approved' ||
          video['approved'] === true),
    );
  }
  selectVideo(id: string) {
    const video = this.videos().find((item) => item['id'] === id);
    this.draft.videoId = id;
    this.draft.videoVersion = Number(video?.['version'] || video?.['video_version'] || 1);
  }
  compatibleFormats() {
    const p = this.platforms().find((x) => x['key'] === this.draft.platform);
    return Array.isArray(p?.['formats'])
      ? p['formats'].filter((x): x is string => typeof x === 'string')
      : [];
  }
  syncFormat() {
    if (!this.compatibleFormats().includes(this.draft.format))
      this.draft.format = this.compatibleFormats()[0] || '';
  }
  label(v: string) {
    return v.replaceAll('_', ' ').replace(/\b\w/g, (x) => x.toUpperCase());
  }
  eligibleAccounts() {
    return this.accounts().filter(
      (x) => x.platform === this.draft.platform && x.enabled && x.validation_status === 'valid',
    );
  }
  selectedAccount() {
    return this.accounts().find((x) => x.id === this.draft.accountId);
  }
  ready() {
    return Boolean(
      this.draft.brandId &&
        this.draft.productId &&
        this.draft.videoId &&
        this.draft.metadataId &&
        this.draft.accountId &&
        this.draft.format &&
        this.selectedAccount()?.enabled,
    );
  }
  readiness(v: Record<string, unknown>) {
    return String(v['message'] || v['status'] || 'Server readiness returned.');
  }
  safeSummary(v: Record<string, unknown>) {
    return String(v['safe_summary'] || v['status'] || 'Safe lifecycle event');
  }
  async previewPost() {
    if (!this.ready()) {
      this.composeError.set(
        'Select a valid enabled account and every required exact identity before preview.',
      );
      return;
    }
    this.busy.set(true);
    try {
      const p = await this.social.createPost({
        brand_id: this.draft.brandId,
        product_id: this.draft.productId,
        account_id: this.draft.accountId,
        platform: this.draft.platform,
        content_type: this.draft.format,
        content_artifact_id: this.draft.metadataId,
        content_artifact_version: this.draft.metadataVersion,
        source_artifact_id: this.draft.videoId,
        source_artifact_version: this.draft.videoVersion,
        caption: this.draft.caption || null,
        media_ids: this.draft.thumbnailId ? [this.draft.thumbnailId] : [],
        idempotency_key: 'social-compose-' + crypto.randomUUID(),
      });
      this.preview.set(await this.social.preview(p.id));
      this.message.set('Preview loaded. No schedule or publication was created.');
    } catch {
      this.composeError.set(
        'Preview rejected safely. Verify approved IDs, versions, and account readiness.',
      );
    } finally {
      this.busy.set(false);
    }
  }
  async confirmPost() {
    const v = this.preview();
    if (!v) return;
    this.busy.set(true);
    try {
      const p = await this.social.schedulePost(
        v.post_id,
        {
          preview_fingerprint: v.fingerprint,
          local_scheduled_at:
            this.draft.mode === 'now' ? new Date().toISOString() : this.draft.localDateTime,
          timezone_name: this.draft.timezone,
          fold: 0,
        },
        this.draft.mode === 'now',
      );
      this.message.set(
        'Confirmed. SocialPost ' +
          p.id +
          ' is ' +
          p.lifecycle_status +
          '. Exact Video version is preserved.',
      );
    } catch {
      this.composeError.set('Confirmation rejected safely.');
    } finally {
      this.busy.set(false);
    }
  }
  async runRecovery(item: SocialRecoveryItem, action: string) {
    if (!confirm('Confirm ' + this.label(action) + '?')) return;
    try {
      await this.social.recoveryAction({
        post_id: item.post_id,
        action,
        confirm: true,
        idempotency_key: 'social-recovery-' + item.post_id + '-' + action,
      });
      await this.load();
    } catch {
      this.error.set('Recovery action rejected safely. Review the SocialPost.');
    }
  }
}
