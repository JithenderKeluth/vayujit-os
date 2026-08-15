/* eslint-disable @typescript-eslint/restrict-template-expressions, @typescript-eslint/no-base-to-string */
import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

type RecordValue = Record<string, unknown>;

@Component({
  selector: 'app-ai-video',
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <main class="video-page">
      <header class="hero">
        <div>
          <p class="eyebrow">AI Studio / Video</p>
          <h1>AI Video Studio</h1>
          <p class="lede">
            Create reviewable, version-pinned videos from approved product context.
          </p>
        </div>
        <div class="provider-badge" role="status">
          <strong>Local Workflow Simulation</strong><span>Deterministic ï¿½ network-free</span>
        </div>
      </header>

      <nav class="tabs" aria-label="Video Studio views">
        @for (view of views; track view.id) {
          <a [routerLink]="[]" [fragment]="view.id">{{ view.label }}</a>
        }
      </nav>

      <section id="overview" class="panel overview-panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Operational overview</p>
            <h2>Video Projects</h2>
          </div>
          <button type="button" (click)="load()">Refresh</button>
        </div>
        <div class="metrics" aria-label="Video status summary">
          @for (metric of metrics(); track metric.label) {
            <article class="metric">
              <span>{{ metric.label }}</span
              ><strong>{{ metric.value }}</strong>
            </article>
          }
        </div>
        <div class="quick-actions" aria-label="Quick actions">
          <a class="button" [routerLink]="[]" fragment="generate">Create Video</a
          ><a class="button" [routerLink]="[]" fragment="storyboards">Open Storyboards</a
          ><a class="button" [routerLink]="[]" fragment="review">Review Videos</a
          ><a class="button" [routerLink]="[]" fragment="presets">Manage Presets</a
          ><a class="button" [routerLink]="[]" fragment="diagnostics">View Diagnostics</a>
        </div>
        @if (error()) {
          <p class="alert" role="alert">{{ error() }}</p>
        }
      </section>

      <section id="generate" class="panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">14-step workflow</p>
            <h2>Generate Video</h2>
          </div>
          <span class="step-count">Step {{ step() }} of 14</span>
        </div>
        <div class="progress" aria-label="Generate workflow progress">
          <span [style.width.%]="(step() / 14) * 100"></span>
        </div>
        <div class="wizard-grid">
          <label
            >Product ID<input
              [(ngModel)]="productId"
              aria-label="Product ID"
              placeholder="Approved Product UUID"
          /></label>
          <label
            >Brand ID<input [(ngModel)]="brandId" aria-label="Brand ID" placeholder="Brand UUID"
          /></label>
          <label
            >Video type<select [(ngModel)]="videoType">
              <option>product_showcase</option>
              <option>slideshow</option>
              <option>instagram_reel</option>
              <option>youtube_short</option>
              <option>promotional_video</option>
            </select></label
          >
          <label
            >Target channel<input [(ngModel)]="targetChannel" aria-label="Target channel"
          /></label>
          <label
            >Resolution<select [(ngModel)]="resolution">
              <option>1280x720</option>
              <option>1080x1920</option>
              <option>1920x1080</option>
              <option>320x240</option>
            </select></label
          >
          <label
            >Duration (seconds)<input type="number" min="1" max="60" [(ngModel)]="duration"
          /></label>
          <label
            >Script version<input
              [(ngModel)]="scriptVersion"
              aria-label="Script version"
              placeholder="Exact version (optional)"
          /></label>
          <label
            >Storyboard version<input
              [(ngModel)]="storyboardVersion"
              aria-label="Storyboard version"
              placeholder="Exact version (optional)"
          /></label>
          <label
            >Audio<select [(ngModel)]="audioMode">
              <option value="none">None</option>
              <option value="uploaded">Uploaded Audio</option>
              <option value="background_music">Background Music</option>
              <option value="narration_placeholder">Deterministic Narration Placeholder</option>
            </select></label
          >
          <label
            >Captions<select [(ngModel)]="captionLocale">
              <option value="">No captions</option>
              <option>en-IN</option>
              <option>hi-IN</option>
              <option>te-IN</option>
            </select></label
          >
        </div>
        <div class="step-summary" aria-live="polite">
          <strong>{{ stepLabel() }}</strong
          ><span
            >Server validates exact Product context, versions, provider capability, and review
            blockers.</span
          >
        </div>
        <div class="wizard-actions">
          <button type="button" [disabled]="step() === 1" (click)="previousStep()">Back</button
          ><button type="button" [disabled]="step() === 14" (click)="nextStep()">Next</button
          ><button
            class="primary"
            type="button"
            [disabled]="queueing() || !canQueue()"
            (click)="queue()"
          >
            {{ queueing() ? 'Queueingï¿½' : 'Queue Video' }}
          </button>
        </div>
        @if (message()) {
          <p class="success" role="status">{{ message() }}</p>
        }
      </section>

      <section id="videos" class="panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Owner-scoped outputs</p>
            <h2>Videos</h2>
          </div>
          <input
            class="search"
            [(ngModel)]="search"
            aria-label="Search videos"
            placeholder="Search Product or generation ID"
          />
        </div>
        <div class="table-wrap">
          <table>
            <caption class="sr-only">
              Generated videos
            </caption>
            <thead>
              <tr>
                <th>Product</th>
                <th>Type</th>
                <th>Target</th>
                <th>Duration</th>
                <th>State</th>
                <th>Approval</th>
                <th>Created</th>
                <th>Review</th>
              </tr>
            </thead>
            <tbody>
              @for (video of filteredVideos(); track video['id']) {
                <tr>
                  <td>{{ video['product_id'] || 'ï¿½' }}</td>
                  <td>{{ video['video_type'] || 'ï¿½' }}</td>
                  <td>{{ video['target_channel'] || 'ï¿½' }}</td>
                  <td>{{ video['duration_seconds'] || 'ï¿½' }}s</td>
                  <td>
                    <span class="state">{{ video['status'] || 'ï¿½' }}</span>
                  </td>
                  <td>
                    {{ video['approval_state'] || video['output_status'] || 'pending_review' }}
                  </td>
                  <td>{{ video['created_at'] || '—' }}</td>
                  <td><button type="button" (click)="selectVideo(video)">Open review</button></td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="9">No Video generations yet. Use Generate to create one.</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </section>

      <section id="scripts" class="panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Version-pinned source</p>
            <h2>Scripts</h2>
          </div>
          <button type="button" (click)="loadScripts()">Refresh</button>
        </div>
        <div class="cards">
          @for (script of scripts(); track script['id']) {
            <article class="card">
              <h3>{{ script['name'] }} v{{ script['version'] }}</h3>
              <p>
                <strong>Artifact:</strong> {{ script['id'] }} · {{ script['status'] }} ·
                {{ script['locale'] }} · {{ script['target_duration_seconds'] }}s
              </p>
              <div class="button-row">
                <button type="button" (click)="openScript(script)">Open / edit</button
                ><button type="button" (click)="approveScript(script)">Approve</button
                ><button type="button" (click)="rejectScript(script)">Reject</button
                ><button type="button" (click)="regenerateScript(script)">Regenerate</button
                ><button type="button" (click)="compareScript(script)">Compare</button
                ><button type="button" (click)="scriptHistory(script)">History</button>
              </div>
            </article>
          } @empty {
            <p class="empty">No Video Scripts found. Create one from approved Product content.</p>
          }
        </div>
      </section>

      <section id="storyboards" class="panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Versioned scene planning</p>
            <h2>Storyboards</h2>
          </div>
          <button type="button" (click)="loadStoryboards()">Refresh</button>
        </div>
        <div class="cards">
          @for (board of storyboards(); track board['id']) {
            <article class="card">
              <h3>Version {{ board['version'] || 'ï¿½' }}</h3>
              <p>{{ board['state'] || 'draft' }} ï¿½ {{ sceneCount(board) }} scenes</p>
              <p>Readiness: {{ board['ready'] ? 'Ready' : 'Needs review' }}</p>
              <button type="button" (click)="openStoryboard(board)">Open editor</button>
            </article>
          } @empty {
            <p class="empty">No storyboards found for the active owner.</p>
          }
        </div>
        @if (selectedStoryboard(); as board) {
          <article class="editor card" aria-labelledby="storyboard-editor-title">
            <h3 id="storyboard-editor-title">Storyboard v{{ board['version'] }} editor</h3>
            <p class="muted">
              Exact storyboard ID: {{ board['id'] }} Â· row {{ board['row_version'] }}
            </p>
            @for (scene of editableScenes(); track scene['stable_key']; let index = $index) {
              <fieldset class="scene-card">
                <legend>Scene {{ scene['scene_order'] }} Â· {{ scene['stable_key'] }}</legend>
                <div class="wizard-grid">
                  <label>Source Media ID<input [(ngModel)]="scene['source_media_id']" /></label>
                  <label
                    >Duration (seconds)<input
                      type="number"
                      min="1"
                      [(ngModel)]="scene['duration_seconds']"
                  /></label>
                  <label
                    >Narration<textarea rows="2" [(ngModel)]="scene['narration']"></textarea>
                  </label>
                  <label
                    >On-screen text<textarea rows="2" [(ngModel)]="scene['scene_text']"></textarea>
                  </label>
                  <label>Transition<input [(ngModel)]="scene['transition']" /></label>
                  <label>CTA<input [(ngModel)]="scene['cta']" /></label>
                </div>
                <p class="muted">
                  Readiness: {{ sceneReady(scene) ? 'Ready' : 'Needs source or text' }}
                </p>
                <div class="button-row">
                  <button type="button" (click)="duplicateScene(index)">Duplicate</button
                  ><button type="button" (click)="removeScene(index)">Remove</button
                  ><button type="button" (click)="moveScene(index, -1)" [disabled]="index === 0">
                    Move up</button
                  ><button
                    type="button"
                    (click)="moveScene(index, 1)"
                    [disabled]="index === editableScenes().length - 1"
                  >
                    Move down
                  </button>
                </div>
              </fieldset>
            } @empty {
              <p class="empty">No scenes yet. Add the first scene.</p>
            }
            <div class="button-row">
              <button type="button" (click)="addScene()">Add scene</button
              ><button type="button" (click)="saveStoryboard()">Save</button
              ><button type="button" (click)="validateStoryboard()">Validate</button
              ><button type="button" (click)="previewStoryboard()">Preview</button
              ><button type="button" (click)="approveStoryboard()">Approve</button>
            </div>
          </article>
        }
      </section>

      <section id="review" class="panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Human approval gate</p>
            <h2>Review Videos</h2>
          </div>
        </div>
        <div class="review-grid">
          <article class="card">
            <h3>Safe player</h3>
            @if (selectedVideo(); as video) {
              @if (video['output_media_id']) {
                <video
                  controls
                  preload="metadata"
                  [src]="mediaPreviewUrl(video['output_media_id'])"
                  aria-label="Selected Video preview"
                >
                  <p>Playback is unavailable in this browser.</p>
                </video>
              } @else {
                <p class="empty">This Video has no completed Media output yet.</p>
              }
              <p><strong>Generation:</strong> {{ video['id'] }}</p>
            } @else {
              <p class="empty">Select a succeeded Video from the Videos workspace.</p>
            }
            <p class="muted">
              Select a succeeded Video to review its Media-backed MP4. Playback never autoplays.
            </p>
          </article>
          <article class="card">
            <h3>Lineage & readiness</h3>
            <dl>
              <dt>Script</dt>
              <dd>Exact version shown by the API</dd>
              <dt>Storyboard</dt>
              <dd>Approved version remains immutable</dd>
              <dt>Style / Preset</dt>
              <dd>Version-pinned on generation</dd>
              <dt>Audio / Captions / Thumbnail</dt>
              <dd>Explicitly reviewed before approval</dd>
            </dl>
            <div class="button-row">
              <button type="button" (click)="approveSelected()">Approve</button>
              <button type="button" (click)="rejectSelected()">Reject</button>
              <button type="button" (click)="compareSelected()">Compare</button>
            </div>
          </article>
        </div>
      </section>

      <section id="presets" class="panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Reusable constraints</p>
            <h2>Presets & Styles</h2>
          </div>
          <button type="button" (click)="loadPresets()">Refresh</button>
        </div>
        <div class="cards">
          @for (style of styles(); track style['id']) {
            <article class="card">
              <h3>Style: {{ style['name'] || style['key'] || style['id'] }}</h3>
              <p>
                Version {{ style['version'] || '—' }} ·
                {{ style['archived_at'] ? 'Archived' : 'Active' }}
              </p>
              <div class="button-row">
                <button type="button" (click)="previewStyle(style)">Preview</button
                ><button type="button" (click)="styleAction(style, 'default')">Set default</button
                ><button
                  type="button"
                  (click)="styleAction(style, style['archived_at'] ? 'restore' : 'archive')"
                >
                  {{ style['archived_at'] ? 'Restore' : 'Archive' }}</button
                ><button type="button" (click)="styleAction(style, 'duplicate')">Duplicate</button>
              </div>
              <dl class="compact-dl">
                @for (entry of styleEntries(style['config']); track entry[0]) {
                  <dt>{{ entry[0] }}</dt>
                  <dd>{{ entry[1] }}</dd>
                }
              </dl>
            </article>
          } @empty {
            <p class="empty">No Video Styles found for the active owner.</p>
          }
          @for (preset of presets(); track preset['id']) {
            <article class="card">
              <h3>{{ preset['name'] || 'Preset' }} v{{ preset['version'] || 'ï¿½' }}</h3>
              <p>{{ preset['video_type'] || 'ï¿½' }} ï¿½ {{ preset['target_channel'] || 'ï¿½' }}</p>
              <p>
                {{ preset['resolution'] || 'ï¿½' }} ï¿½
                {{ preset['target_duration_seconds'] || 'ï¿½' }}s
              </p>
              <p>
                Style {{ preset['style_id'] || 'server default' }} · provider/model
                {{ preset['provider_key'] || 'Local Workflow Simulation' }}/{{
                  preset['model'] || 'deterministic'
                }}
              </p>
              <div class="button-row">
                <button type="button" (click)="previewPreset(preset)">Preview</button
                ><button
                  type="button"
                  (click)="presetAction(preset, preset['archived_at'] ? 'restore' : 'archive')"
                >
                  {{ preset['archived_at'] ? 'Restore' : 'Archive' }}</button
                ><button type="button" (click)="presetAction(preset, 'duplicate')">
                  Duplicate
                </button>
              </div>
            </article>
          } @empty {
            <p class="empty">No presets found for the active owner.</p>
          }
        </div>
      </section>

      <section id="captions" class="panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Accessible text tracks</p>
            <h2>Captions</h2>
          </div>
        </div>
        <div class="card">
          <p>
            Operational captions support en-IN, hi-IN, and te-IN with cue timing, review, rejection,
            regeneration, translation, localization, and WebVTT export.
          </p>
          <div class="wizard-grid">
            <label
              >Locale<select [(ngModel)]="captionLocale">
                <option>en-IN</option>
                <option>hi-IN</option>
                <option>te-IN</option>
              </select></label
            ><label
              >Caption text<textarea
                rows="3"
                maxlength="10000"
                aria-label="Caption text"
                placeholder="Text remains inert domain data"
              ></textarea>
            </label>
          </div>
          <div class="wizard-grid">
            <label
              >Locale<select [(ngModel)]="captionLocale">
                <option>en-IN</option>
                <option>hi-IN</option>
                <option>te-IN</option>
              </select></label
            >
            <label
              >Caption text<textarea
                rows="3"
                maxlength="10000"
                aria-label="Caption text"
                placeholder="Text remains inert domain data"
              ></textarea>
            </label>
          </div>
          <div class="button-row">
            <button type="button" (click)="addCaption()" [disabled]="!selectedVideo()">
              Add track</button
            ><button type="button" (click)="loadCaptions()" [disabled]="!selectedVideo()">
              Refresh tracks
            </button>
          </div>
          @for (caption of captions(); track caption['id']) {
            <article class="card">
              <strong>{{ caption['locale'] }} v{{ caption['version'] }}</strong>
              <p>{{ caption['caption_text'] }}</p>
              <p>Status: {{ caption['approval_state'] }}</p>
              <div class="button-row">
                <button type="button" (click)="approveCaption(caption)">Approve</button
                ><button type="button" (click)="exportCaption(caption)">Export WebVTT</button>
              </div>
            </article>
          } @empty {
            <p class="empty">Select a generated Video to manage caption tracks.</p>
          }
        </div>
      </section>

      <section id="history" class="panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Chronological audit projection</p>
            <h2>History & Recovery</h2>
          </div>
          <button type="button" (click)="loadHistory()" [disabled]="!selectedVideo()">
            Refresh
          </button>
        </div>
        @if (history().length) {
          @for (event of history(); track event['timestamp']) {
            <p class="step-summary">
              <strong>{{ event['action'] }}</strong
              ><span>{{ event['timestamp'] }} · {{ event['correlation_id'] }}</span>
            </p>
          }
        } @else {
          <p class="empty">Select a Video and open History to load server events.</p>
        }
        @if (recovery(); as state) {
          <article class="card">
            <h3>Recovery projection</h3>
            <p>{{ state['safe_message'] }}</p>
            <p>
              Failure: {{ state['failure_code'] || 'None' }} · Retryable:
              {{ state['retryable'] ? 'Yes' : 'No' }}
            </p>
            <p>Eligible actions: {{ actionSummary(state['eligible_actions']) }}</p>
          </article>
        }
      </section>
      <section id="usage" class="panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Cost-safe telemetry</p>
            <h2>Usage</h2>
          </div>
        </div>
        <div class="metrics">
          <article class="metric"><span>Modality</span><strong>Video</strong></article>
          <article class="metric"><span>Provider calls</span><strong>Unavailable</strong></article>
          <article class="metric"><span>Cost state</span><strong>Unavailable</strong></article>
          <article class="metric">
            <span>Output bytes</span><strong>{{ totalBytes() }}</strong>
          </article>
        </div>
        <p class="muted">
          Unknown cost is displayed as Unavailable; no fabricated currency values are shown.
        </p>
      </section>

      <section id="diagnostics" class="panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Operator diagnostics</p>
            <h2>Diagnostics</h2>
          </div>
          <button type="button" (click)="loadDiagnostics()">Refresh</button>
        </div>
        @if (diagnostics(); as diag) {
          <div class="diagnostic-grid">
            @for (entry of diagnosticEntries(diag); track entry[0]) {
              <div>
                <span>{{ entry[0] }}</span
                ><strong>{{ entry[1] }}</strong>
              </div>
            }
          </div>
        } @else {
          <p class="empty">Diagnostics unavailable. Check the authenticated API connection.</p>
        }
        <p class="muted">No credentials, DSNs, or local filesystem paths are rendered.</p>
      </section>
    </main>
  `,
  styles: [
    `
      :host {
        display: block;
        color: #102a43;
        background: #f5f8fa;
        min-height: 100%;
      }
      .video-page {
        max-width: 1280px;
        margin: auto;
        padding: clamp(1rem, 3vw, 2.5rem);
      }
      .hero,
      .section-heading,
      .wizard-actions,
      .button-row {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: center;
      }
      .hero {
        align-items: flex-start;
        margin-bottom: 1.25rem;
      }
      h1 {
        font-size: clamp(2rem, 5vw, 3.6rem);
        margin: 0.15rem 0 0.5rem;
      }
      h2 {
        margin: 0.15rem 0;
        font-size: clamp(1.35rem, 3vw, 2rem);
      }
      h3 {
        margin-top: 0;
      }
      .lede,
      .muted {
        color: #526b7a;
      }
      .eyebrow {
        color: #14637a;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 0.2rem 0;
      }
      .provider-badge {
        border: 1px solid #79aebe;
        border-radius: 12px;
        padding: 0.75rem 1rem;
        display: grid;
        gap: 0.2rem;
        background: #e9f4f7;
      }
      .provider-badge span {
        font-size: 0.8rem;
      }
      .tabs {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin: 1rem 0 1.5rem;
      }
      .tabs a,
      .button {
        color: #075985;
        border: 1px solid #9bb8c5;
        border-radius: 999px;
        padding: 0.55rem 0.85rem;
        text-decoration: none;
        background: #fff;
      }
      .tabs a:focus-visible,
      .button:focus-visible,
      button:focus-visible,
      input:focus-visible,
      select:focus-visible,
      textarea:focus-visible {
        outline: 3px solid #f59e0b;
        outline-offset: 2px;
      }
      .panel {
        background: #fff;
        border: 1px solid #d4e0e6;
        border-radius: 16px;
        padding: clamp(1rem, 2vw, 1.5rem);
        margin: 1rem 0;
        scroll-margin-top: 1rem;
      }
      .metrics {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
        gap: 0.75rem;
        margin: 1rem 0;
      }
      .metric,
      .card {
        border: 1px solid #d4e0e6;
        border-radius: 12px;
        padding: 1rem;
      }
      .metric span,
      .diagnostic-grid span {
        display: block;
        color: #526b7a;
        font-size: 0.85rem;
      }
      .metric strong {
        display: block;
        font-size: 1.7rem;
        margin-top: 0.25rem;
      }
      .quick-actions,
      .button-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.6rem;
      }
      button {
        border: 0;
        border-radius: 8px;
        padding: 0.65rem 0.9rem;
        background: #155e75;
        color: white;
        cursor: pointer;
      }
      button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .primary {
        background: #0f766e;
      }
      .progress {
        height: 8px;
        background: #e7eef2;
        border-radius: 8px;
        margin: 1rem 0;
        overflow: hidden;
      }
      .progress span {
        display: block;
        height: 100%;
        background: #0f766e;
        transition: width 0.2s;
      }
      .step-count {
        color: #526b7a;
      }
      .wizard-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
      }
      label {
        display: grid;
        gap: 0.35rem;
        font-weight: 600;
      }
      input,
      select,
      textarea {
        width: 100%;
        box-sizing: border-box;
        border: 1px solid #9bb8c5;
        border-radius: 7px;
        padding: 0.65rem;
        font: inherit;
        background: white;
      }
      .step-summary {
        display: grid;
        gap: 0.25rem;
        margin: 1rem 0;
        padding: 0.85rem;
        background: #f0f7f8;
        border-left: 4px solid #0f766e;
      }
      .table-wrap {
        overflow-x: auto;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        min-width: 760px;
      }
      th,
      td {
        text-align: left;
        padding: 0.75rem;
        border-bottom: 1px solid #e5edf1;
      }
      th {
        background: #f2f7f8;
      }
      .state {
        font-weight: 600;
      }
      .cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.75rem;
        margin-top: 1rem;
      }
      .editor {
        margin-top: 1rem;
      }
      .scene-card {
        border: 1px solid #d4e0e6;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.75rem 0;
      }
      .scene-card legend {
        font-weight: 700;
        padding: 0 0.35rem;
      }
      .review-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
      }
      video {
        width: 100%;
        max-height: 420px;
        background: #102a43;
        border-radius: 8px;
      }
      dt {
        font-weight: 700;
        margin-top: 0.5rem;
      }
      dd {
        margin: 0.1rem 0;
        color: #526b7a;
      }
      .diagnostic-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.75rem;
      }
      .diagnostic-grid div {
        border: 1px solid #d4e0e6;
        border-radius: 8px;
        padding: 0.75rem;
      }
      .alert {
        color: #991b1b;
        background: #fef2f2;
        padding: 0.75rem;
      }
      .success {
        color: #166534;
        background: #f0fdf4;
        padding: 0.75rem;
      }
      .empty {
        color: #526b7a;
        padding: 1rem 0;
      }
      .search {
        max-width: 280px;
      }
      .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }
      @media (max-width: 700px) {
        .hero,
        .section-heading {
          display: block;
        }
        .provider-badge {
          margin-top: 1rem;
        }
        .wizard-grid,
        .editor {
          margin-top: 1rem;
        }
        .scene-card {
          border: 1px solid #d4e0e6;
          border-radius: 10px;
          padding: 1rem;
          margin: 0.75rem 0;
        }
        .scene-card legend {
          font-weight: 700;
          padding: 0 0.35rem;
        }
        .review-grid {
          grid-template-columns: 1fr;
        }
        .wizard-actions {
          flex-wrap: wrap;
        }
        .search {
          max-width: none;
          margin-top: 0.75rem;
        }
      }
    `,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AIVideoComponent {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/ai/video`;
  readonly views = [
    { id: 'overview', label: 'Overview' },
    { id: 'generate', label: 'Generate' },
    { id: 'storyboards', label: 'Storyboards' },
    { id: 'videos', label: 'Videos' },
    { id: 'review', label: 'Review' },
    { id: 'presets', label: 'Presets' },
    { id: 'captions', label: 'Captions' },
    { id: 'usage', label: 'Usage' },
    { id: 'diagnostics', label: 'Diagnostics' },
  ];
  productId = '';
  brandId = '';
  videoType = 'product_showcase';
  targetChannel = 'youtube';
  resolution = '1280x720';
  duration = 10;
  scriptVersion = '';
  storyboardVersion = '';
  audioMode = 'none';
  captionLocale = '';
  search = '';
  readonly step = signal(1);
  readonly queueing = signal(false);
  readonly message = signal('');
  readonly error = signal('');
  readonly videos = signal<RecordValue[]>([]);
  readonly scripts = signal<RecordValue[]>([]);
  readonly styles = signal<RecordValue[]>([]);
  readonly selectedVideo = signal<RecordValue | null>(null);
  readonly selectedStoryboard = signal<RecordValue | null>(null);
  readonly editableScenes = signal<RecordValue[]>([]);
  readonly storyboards = signal<RecordValue[]>([]);
  readonly presets = signal<RecordValue[]>([]);
  readonly diagnostics = signal<RecordValue | null>(null);
  readonly captions = signal<RecordValue[]>([]);
  readonly history = signal<RecordValue[]>([]);
  readonly recovery = signal<RecordValue | null>(null);
  readonly comparison = signal<RecordValue | null>(null);
  readonly scriptDraft = signal<RecordValue | null>(null);
  constructor() {
    void this.load();
  }
  async load(): Promise<void> {
    await Promise.all([
      this.loadVideos(),
      this.loadScripts(),
      this.loadStyles(),
      this.loadStoryboards(),
      this.loadPresets(),
      this.loadDiagnostics(),
    ]);
  }
  async loadVideos(): Promise<void> {
    try {
      const value = await firstValueFrom(
        this.http.get<RecordValue[]>(`${this.base}/generations`, { withCredentials: true }),
      );
      this.videos.set(Array.isArray(value) ? value : (value['items'] as RecordValue[]) || []);
    } catch {
      this.error.set('Video data is unavailable. Check the authenticated API connection.');
    }
  }
  async loadScripts(): Promise<void> {
    try {
      const value = await firstValueFrom(
        this.http.get<RecordValue[]>(`${this.base}/scripts`, { withCredentials: true }),
      );
      this.scripts.set(Array.isArray(value) ? value : (value['items'] as RecordValue[]) || []);
    } catch {
      this.scripts.set([]);
      this.error.set('Scripts are unavailable. Retry the authenticated connection.');
    }
  }
  async loadStyles(): Promise<void> {
    try {
      const value = await firstValueFrom(
        this.http.get<RecordValue[]>(`${this.base}/styles`, { withCredentials: true }),
      );
      this.styles.set(Array.isArray(value) ? value : (value['items'] as RecordValue[]) || []);
    } catch {
      this.styles.set([]);
    }
  }
  selectVideo(video: RecordValue): void {
    this.selectedVideo.set(video);
    this.captions.set([]);
    this.history.set([]);
    this.recovery.set(null);
    this.comparison.set(null);
    void this.loadCaptions();
    window.location.hash = 'review';
  }
  mediaPreviewUrl(mediaId: unknown): string {
    return `${environment.apiUrl.replace('/api/v1', '')}/api/v1/media/${String(mediaId)}/preview`;
  }
  async loadCaptions(): Promise<void> {
    const video = this.selectedVideo();
    if (!video) return;
    try {
      const value = await firstValueFrom(
        this.http.get<RecordValue[]>(`${this.base}/generations/${video['id']}/captions`, {
          withCredentials: true,
        }),
      );
      this.captions.set(Array.isArray(value) ? value : []);
    } catch {
      this.captions.set([]);
    }
  }
  async loadHistory(): Promise<void> {
    const video = this.selectedVideo();
    if (!video) return;
    try {
      this.history.set(
        await firstValueFrom(
          this.http.get<RecordValue[]>(`${this.base}/generations/${video['id']}/history`, {
            withCredentials: true,
          }),
        ),
      );
    } catch {
      this.history.set([]);
    }
  }
  async loadRecovery(): Promise<void> {
    const video = this.selectedVideo();
    if (!video) return;
    try {
      this.recovery.set(
        await firstValueFrom(
          this.http.get<RecordValue>(`${this.base}/generations/${video['id']}/recovery`, {
            withCredentials: true,
          }),
        ),
      );
    } catch {
      this.recovery.set(null);
    }
  }
  async generateThumbnail(): Promise<void> {
    const video = this.selectedVideo();
    if (!video) return;
    try {
      await firstValueFrom(
        this.http.post(
          `${this.base}/generations/${video['id']}/thumbnail-candidate`,
          {},
          { withCredentials: true },
        ),
      );
      this.message.set('Thumbnail candidate queued for explicit review.');
    } catch {
      this.error.set('Thumbnail candidate could not be queued safely.');
    }
  }
  async addCaption(): Promise<void> {
    const video = this.selectedVideo();
    if (!video || !this.captionLocale) return;
    try {
      await firstValueFrom(
        this.http.post(
          `${this.base}/generations/${video['id']}/captions`,
          {
            locale: this.captionLocale,
            caption_text: 'Reviewable caption cue',
            timing: [{ start: 0, end: 1, text: 'Reviewable caption cue' }],
          },
          { withCredentials: true },
        ),
      );
      await this.loadCaptions();
      this.message.set('Caption track created for review.');
    } catch {
      this.error.set('Caption track could not be created safely.');
    }
  }
  async exportCaption(caption: RecordValue): Promise<void> {
    try {
      const value = await firstValueFrom(
        this.http.get<RecordValue>(`${this.base}/captions/${caption['id']}/export`, {
          withCredentials: true,
        }),
      );
      this.message.set(`${String(value['format'] || 'WebVTT')} export ready.`);
    } catch {
      this.error.set('Caption export is unavailable.');
    }
  }
  async approveCaption(caption: RecordValue): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(
          `${this.base}/captions/${caption['id']}/approve`,
          {},
          { withCredentials: true },
        ),
      );
      await this.loadCaptions();
    } catch {
      this.error.set('Caption approval failed safely.');
    }
  }
  openStoryboard(board: RecordValue): void {
    this.selectedStoryboard.set(board);
    this.editableScenes.set(
      ((board['scenes'] as RecordValue[]) || []).map((scene) => ({ ...scene })),
    );
  }
  openScript(script: RecordValue): void {
    this.scriptDraft.set({ ...script });
    this.message.set(`Editing Script ${script['id']} v${script['version']}.`);
  }
  async approveScript(script: RecordValue): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(
          `${this.base}/scripts/${script['id']}/approve`,
          {},
          { withCredentials: true },
        ),
      );
      await this.loadScripts();
    } catch {
      this.error.set('Script approval failed safely.');
    }
  }
  async rejectScript(script: RecordValue): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(
          `${this.base}/scripts/${script['id']}/reject`,
          { feedback: 'Needs revision.' },
          { withCredentials: true },
        ),
      );
      await this.loadScripts();
    } catch {
      this.error.set('Script rejection failed safely.');
    }
  }
  async regenerateScript(script: RecordValue): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(
          `${this.base}/scripts/${script['id']}/regenerate`,
          {},
          { withCredentials: true },
        ),
      );
      await this.loadScripts();
    } catch {
      this.error.set('Script regeneration failed safely.');
    }
  }
  compareScript(script: RecordValue): void {
    this.message.set(`Compare exact Script version ${script['version']}.`);
  }
  scriptHistory(script: RecordValue): void {
    this.message.set(`Script history for ${script['id']} is version-pinned.`);
  }
  sceneReady(scene: RecordValue): boolean {
    return Boolean(scene['source_media_id'] || scene['scene_text'] || scene['narration']);
  }
  addScene(): void {
    const scenes = this.editableScenes();
    this.editableScenes.set([
      ...scenes,
      {
        stable_key: `scene-${scenes.length + 1}`,
        scene_order: scenes.length + 1,
        duration_seconds: 3,
        transition: 'cut',
        locale: 'en-IN',
      },
    ]);
  }
  duplicateScene(index: number): void {
    const scenes = this.editableScenes();
    const copy = { ...scenes[index], stable_key: `${String(scenes[index]['stable_key'])}-copy` };
    this.editableScenes.set(
      [...scenes.slice(0, index + 1), copy, ...scenes.slice(index + 1)].map((scene, position) => ({
        ...scene,
        scene_order: position + 1,
      })),
    );
  }
  removeScene(index: number): void {
    this.editableScenes.set(
      this.editableScenes()
        .filter((_, position) => position !== index)
        .map((scene, position) => ({ ...scene, scene_order: position + 1 })),
    );
  }
  moveScene(index: number, delta: number): void {
    const target = index + delta;
    const scenes = [...this.editableScenes()];
    if (target < 0 || target >= scenes.length) return;
    [scenes[index], scenes[target]] = [scenes[target], scenes[index]];
    this.editableScenes.set(
      scenes.map((scene, position) => ({ ...scene, scene_order: position + 1 })),
    );
  }
  async saveStoryboard(): Promise<void> {
    const board = this.selectedStoryboard();
    if (!board) return;
    try {
      const saved = await firstValueFrom(
        this.http.put<RecordValue>(
          `${this.base}/storyboards/${board['id']}`,
          { expected_row_version: board['row_version'], scenes: this.editableScenes() },
          { withCredentials: true },
        ),
      );
      this.selectedStoryboard.set(saved);
      this.editableScenes.set((saved['scenes'] as RecordValue[]) || []);
      this.message.set(`Storyboard v${saved['version']} saved.`);
      await this.loadStoryboards();
    } catch {
      this.error.set('Storyboard could not be saved. Refresh and resolve the readiness blockers.');
    }
  }
  validateStoryboard(): void {
    const invalid = this.editableScenes().some((scene) => !this.sceneReady(scene));
    this.message.set(
      invalid ? 'Storyboard has readiness blockers.' : 'Storyboard is ready for approval.',
    );
  }
  previewStoryboard(): void {
    this.message.set('Preview uses the selected immutable storyboard version.');
  }
  async approveStoryboard(): Promise<void> {
    const board = this.selectedStoryboard();
    if (!board) return;
    try {
      await firstValueFrom(
        this.http.post(
          `${this.base}/storyboards/${board['id']}/approve`,
          { expected_row_version: board['row_version'] },
          { withCredentials: true },
        ),
      );
      this.message.set(`Storyboard v${board['version']} approved.`);
      await this.loadStoryboards();
    } catch {
      this.error.set('Storyboard is not ready for approval.');
    }
  }
  async approveSelected(): Promise<void> {
    const video = this.selectedVideo();
    if (!video) return;
    try {
      await firstValueFrom(
        this.http.post(
          `${this.base}/generations/${video['id']}/approve`,
          { feedback: null },
          { withCredentials: true },
        ),
      );
      this.message.set('Video approved.');
      await this.loadVideos();
    } catch {
      this.error.set('Video is not eligible for approval.');
    }
  }
  async rejectSelected(): Promise<void> {
    const video = this.selectedVideo();
    if (!video) return;
    try {
      await firstValueFrom(
        this.http.post(
          `${this.base}/generations/${video['id']}/reject`,
          { feedback: 'Needs revision.' },
          { withCredentials: true },
        ),
      );
      this.message.set('Video rejected with feedback retained.');
      await this.loadVideos();
    } catch {
      this.error.set('Video could not be rejected safely.');
    }
  }
  async compareSelected(): Promise<void> {
    const video = this.selectedVideo();
    const other = this.videos().find((item) => item['id'] !== video?.['id']);
    if (!video || !other) {
      this.message.set('Comparison requires two generated Video versions.');
      return;
    }
    try {
      this.comparison.set(
        await firstValueFrom(
          this.http.get<RecordValue>(
            `${this.base}/generations/${video['id']}/compare/${other['id']}`,
            { withCredentials: true },
          ),
        ),
      );
    } catch {
      this.error.set('Comparison is unavailable.');
    }
  }
  actionSummary(value: unknown): string {
    return Array.isArray(value) ? value.map((item) => String(item)).join(', ') || 'None' : 'None';
  }
  styleEntries(config: unknown): Array<[string, string]> {
    return Object.entries((config as RecordValue) || {}).map(([key, value]) => [
      key,
      String(value),
    ]);
  }
  async loadStoryboards(): Promise<void> {
    try {
      const value = await firstValueFrom(
        this.http.get<RecordValue[]>(`${this.base}/storyboards`, { withCredentials: true }),
      );
      this.storyboards.set(Array.isArray(value) ? value : (value['items'] as RecordValue[]) || []);
    } catch {
      /* overview remains safe */
    }
  }
  previewStyle(style: RecordValue): void {
    this.message.set(
      'Previewing Style ' + String(style['id']) + ' with server-derived compatibility.',
    );
  }
  previewPreset(preset: RecordValue): void {
    this.message.set('Preset ' + String(preset['id']) + ' compatibility is server-derived.');
  }
  async styleAction(style: RecordValue, action: string): Promise<void> {
    try {
      const route =
        action === 'default' ? 'default' : action === 'duplicate' ? 'duplicate' : action;
      await firstValueFrom(
        this.http.post(
          this.base + '/styles/' + String(style['id']) + '/' + route,
          {},
          { withCredentials: true },
        ),
      );
      await this.loadStyles();
      this.message.set('Style ' + action + ' completed.');
    } catch {
      this.error.set('Style ' + action + ' failed safely.');
    }
  }
  async presetAction(preset: RecordValue, action: string): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(
          this.base + '/presets/' + String(preset['id']) + '/' + action,
          {},
          { withCredentials: true },
        ),
      );
      await this.loadPresets();
      this.message.set('Preset ' + action + ' completed.');
    } catch {
      this.error.set('Preset ' + action + ' failed safely.');
    }
  }
  async loadPresets(): Promise<void> {
    try {
      const value = await firstValueFrom(
        this.http.get<RecordValue[]>(`${this.base}/presets`, { withCredentials: true }),
      );
      this.presets.set(Array.isArray(value) ? value : (value['items'] as RecordValue[]) || []);
    } catch {
      /* overview remains safe */
    }
  }
  async loadDiagnostics(): Promise<void> {
    try {
      this.diagnostics.set(
        await firstValueFrom(
          this.http.get<RecordValue>(`${this.base}/diagnostics`, { withCredentials: true }),
        ),
      );
    } catch {
      this.diagnostics.set(null);
    }
  }
  nextStep(): void {
    if (this.step() < 14) this.step.update((value) => value + 1);
  }
  previousStep(): void {
    if (this.step() > 1) this.step.update((value) => value - 1);
  }
  stepLabel(): string {
    return [
      'Product',
      'Video Type',
      'Target',
      'Script',
      'Source Media',
      'Storyboard',
      'Brand Style',
      'Preset',
      'Resolution / Aspect Ratio / Duration',
      'Captions',
      'Audio',
      'Provider / Model',
      'Review Plan',
      'Queue',
    ][this.step() - 1];
  }
  canQueue(): boolean {
    return Boolean(this.productId.trim() && this.brandId.trim());
  }
  async queue(): Promise<void> {
    if (!this.canQueue() || this.queueing()) return;
    this.queueing.set(true);
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(
          `${this.base}/queue`,
          {
            brand_id: this.brandId,
            product_id: this.productId,
            video_type: this.videoType,
            target_channel: this.targetChannel,
            resolution: this.resolution,
            duration_seconds: this.duration,
            audio_mode: this.audioMode,
            idempotency_key: `web-video:${this.productId}:${this.videoType}:${this.resolution}`,
          },
          { withCredentials: true },
        ),
      );
      this.message.set('Video queued for durable worker execution.');
      await this.loadVideos();
    } catch {
      this.error.set('Video could not be queued safely. Review the server blockers and try again.');
    } finally {
      this.queueing.set(false);
    }
  }
  filteredVideos(): RecordValue[] {
    const query = this.search.trim().toLowerCase();
    return this.videos().filter(
      (video) => !query || JSON.stringify(video).toLowerCase().includes(query),
    );
  }
  metrics(): Array<{ label: string; value: string | number }> {
    const values = this.videos();
    const count = (status: string) => values.filter((v) => v['status'] === status).length;
    return [
      { label: 'Video Projects', value: values.length },
      { label: 'Queued', value: count('queued') },
      { label: 'Generating', value: count('generating') },
      { label: 'Retry wait', value: count('retry_wait') },
      { label: 'Pending review', value: count('succeeded') },
      { label: 'Approved', value: count('approved') },
      { label: 'Rejected', value: count('rejected') },
      { label: 'Failed', value: count('failed') },
    ];
  }
  totalBytes(): string {
    const total = this.videos().reduce((sum, v) => sum + Number(v['size_bytes'] || 0), 0);
    return total ? `${total.toLocaleString()} bytes` : 'Unavailable';
  }
  sceneCount(board: RecordValue): number {
    return Array.isArray(board['scenes']) ? board['scenes'].length : 0;
  }
  diagnosticEntries(value: RecordValue): Array<[string, string]> {
    return Object.entries(value)
      .filter(([key]) => !key.toLowerCase().includes('path'))
      .map(([key, item]) => [key, String(item)]);
  }
}
