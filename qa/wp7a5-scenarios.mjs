// Exact remaining acceptance scenarios; canonical API preparation is distinct from UI evidence.
const partial = (reason) => ({ status: 'PARTIAL', reason });
export async function execute(entry, h) {
  const {
    p,
    s,
    run,
    api,
    product,
    brand,
    content,
    video,
    image,
    worker,
    c,
    listing,
    readDetail,
    waitResponse,
    expect,
  } = h;
  const url = (path) => s.origin + '/api/v1/' + path;
  const owned = async (path) => {
    const anonymous = await p.context().browser().newContext();
    try {
      expect((await anonymous.request.get(url(path))).status()).toBe(401);
    } finally {
      await anonymous.close();
    }
  };
  const one = async (fail = false) => {
    const r = await p.request.post(s.origin + '/__qa/wp7a3/control', {
      headers: { 'x-qa-token': s.token },
      data: { scenario: fail ? 'WORKER_FAIL' : 'WORKER_SUCCESS', limit: 1 },
    });
    expect(r.status()).toBe(200);
  };
  const fail = async () => {
    for (let n = 0; n < 4; n++) await worker(true);
  };
  switch (entry.id) {
    case 'R-184826c3': {
      const context = await api('post', 'intelligence/trends/contexts', {
        name: '[QA SYNTHETIC] WP7A5 ' + run.label,
        subject_type: 'PRODUCT',
        product_id: product.id,
        subject_key: product.id,
        idempotency_key: 'wp7a5-trend-' + product.id,
      });
      const source = await api('post', 'intelligence/sources', {
        source_type: 'trend_source',
        display_name: '[QA SYNTHETIC] WP7A5 manual observations ' + run.label,
        provider: 'LOCAL_FIXTURE',
        access_method: 'manual_entry',
        trust_classification: 'trusted_internal',
      });
      await api('get', 'intelligence/trends/signal-definitions');
      const ids = [];
      for (let n = 0; n < 3; n++) {
        const observation = await api(
          'post',
          `intelligence/trends/contexts/${context.id}/observations`,
          {
            source_id: source.id,
            signal_type: 'CUSTOM_INDEX',
            observed_at: `2026-10-${20 + n}T00:00:00Z`,
            value_numeric: String(10 + n),
            unit: 'index',
            scale: '100',
            verification_state: 'UNKNOWN',
            raw_metadata: { synthetic: true },
            provenance_note: '[QA SYNTHETIC] invented fixture index, not market demand',
            idempotency_key: 'wp7a5-observation-' + product.id + '-' + n,
          },
        );
        ids.push(observation.id);
        expect(observation.verification_state).toBe('UNKNOWN');
      }
      const snapshot = await api('post', `intelligence/trends/contexts/${context.id}/snapshots`, {
        observation_ids: ids,
      });
      await p.goto(s.origin + '/intelligence/trends/' + context.id);
      const response = waitResponse(p, `/contexts/${context.id}/analyses`);
      await p
        .getByRole('button', { name: 'Analyze latest immutable snapshot', exact: true })
        .click();
      expect((await response).status()).toBe(201);
      await p.reload();
      await expect(p.locator('main')).toContainText(/unknown|unverified|insufficient/i);
      const observations = await api(
        'get',
        `intelligence/trends/contexts/${context.id}/observations`,
      );
      expect(JSON.stringify(observations)).toContain('[QA SYNTHETIC]');
      expect(snapshot.id).toBeTruthy();
      await owned(`intelligence/trends/contexts/${context.id}`);
      return;
    }
    case 'R-794214d7': {
      await content();
      const queued = await api('post', 'ai/video/queue', {
        brand_id: brand.id,
        product_id: product.id,
        video_type: 'product_showcase',
        target_channel: 'youtube',
        resolution: '320x240',
        duration_seconds: 2,
        idempotency_key: 'wp7a5-activity-recovered-' + run.label,
      });
      await fail();
      await p.goto(s.origin + '/ai/video?generation=' + queued.id);
      await expect(p.locator('main')).toContainText(queued.id);
      await p
        .locator('article')
        .filter({ has: p.getByRole('heading', { name: 'Lineage & readiness', exact: true }) })
        .getByRole('button', { name: 'Recovery', exact: true })
        .click();
      const retry = waitResponse(p, '/generations/' + queued.id + '/recovery');
      await p.getByRole('button', { name: 'Retry failed Video', exact: true }).click();
      expect((await retry).status()).toBe(200);
      await worker();
      await p.reload();
      await expect(p.locator('main')).toContainText(queued.id);
      const approval = waitResponse(p, '/generations/' + queued.id + '/approve');
      await p
        .locator('article')
        .filter({ has: p.getByRole('heading', { name: 'Lineage & readiness', exact: true }) })
        .getByRole('button', { name: 'Approve', exact: true })
        .click();
      expect((await approval).status()).toBe(200);
      const v = await api('get', 'ai/video/generations/' + queued.id),
        campaign = await c();
      const activity = await api('post', `campaigns/${campaign.id}/activities`, {
        activity_type: 'video_campaign',
        name: '[QA SYNTHETIC] WP7A5 exact Video',
        sequence: 1,
        scheduled_local_date: '2026-11-11',
        scheduled_local_time: '09:00:00',
        product_id: product.id,
        video_generation_id: v.id,
        video_output_id: v.output_id,
        video_media_id: v.output_media_id,
        video_version: 1,
        video_channel: 'youtube',
      });
      await p.goto(s.origin + `/campaigns/${campaign.id}/video/${activity.id}`);
      await expect(p.locator('main')).toContainText(activity.id);
      await expect(p.locator('main')).toContainText(v.id);
      await p.getByRole('link', { name: 'Review exact Video job', exact: true }).click();
      await expect(p).toHaveURL(new RegExp('generation=' + v.id));
      await p.reload();
      await expect(p.locator('main')).toContainText('approved');
      await p.locator('#history').getByRole('button', { name: 'Refresh', exact: true }).click();
      await expect(p.locator('#history')).toContainText('ai.video_recovery_requested');
      await p.goto(
        s.origin + `/campaigns/${campaign.id}/video/00000000-0000-4000-8000-000000000099`,
      );
      await expect(p.getByRole('alert')).toContainText(/unavailable/i);
      expect(
        (
          await p.request.get(
            url(
              `campaigns/${campaign.id}/video/activities/00000000-0000-4000-8000-000000000099/detail`,
            ),
          )
        ).status(),
      ).toBe(404);
      await p.goto(s.origin + `/campaigns/${campaign.id}/video/${activity.id}`);
      const detail = await api(
        'get',
        `campaigns/${campaign.id}/video/activities/${activity.id}/detail`,
      );
      expect(detail.activity.video_generation_id).toBe(v.id);
      await owned(`campaigns/${campaign.id}/video/activities/${activity.id}/detail`);
      return;
    }
    case 'L-10': {
      const gen = await api('post', 'ai/studio/generate', {
        product_ids: [product.id],
        channels: ['canonical'],
        content_types: ['product_title'],
        locale: 'en-IN',
        idempotency_key: 'wp7a5-studio-' + run.label,
      });
      await fail();
      await p.goto(s.origin + '/ai/studio?generation=' + gen.id);
      await expect(p.getByRole('status').filter({ hasText: 'Generation status' })).toContainText(
        'failed',
      );
      const retry = waitResponse(p, '/studio/recovery/actions');
      await p.getByRole('button', { name: 'Retry failed content', exact: true }).click();
      expect((await retry).status()).toBe(200);
      await worker();
      await p.getByRole('button', { name: 'Refresh generation status', exact: true }).click();
      const saved = await api('get', 'ai/studio/generations/' + gen.id);
      expect(saved.outputs[0].artifact_id).toBeTruthy();
      const artifact = await api('get', 'ai/studio/artifacts/' + saved.outputs[0].artifact_id);
      expect(artifact.status).toBe('pending_review');
      await p.reload();
      await expect(p.locator('main')).toContainText(/completed|succeeded/i);
      const old = await api('post', 'ai/studio/generate', {
        product_ids: [product.id],
        channels: ['canonical'],
        content_types: ['product_title'],
        idempotency_key: 'wp7a5-stale-' + run.label,
      });
      await api('patch', 'products/' + product.id, {
        description: '[QA SYNTHETIC] WP7A5 changed text context ' + run.label,
      });
      await worker();
      expect(
        (await api('get', 'ai/studio/generations/' + old.id)).outputs.every((o) => !o.artifact_id),
      ).toBe(true);
      await p.goto(s.origin + '/ai/studio?generation=' + old.id);
      await expect(p.locator('main')).toContainText(/stale/i);
      await p.getByLabel(/^Content types/).selectOption(['product_title']);
      const fresh = waitResponse(p, '/studio/generate');
      await p.getByRole('button', { name: 'Generate deterministic draft', exact: true }).click();
      const next = await (await fresh).json();
      expect(next.id).not.toBe(old.id);
      await worker();
      await p.getByRole('button', { name: 'Refresh generation status', exact: true }).click();
      const nextState = await api('get', 'ai/studio/generations/' + next.id);
      expect(nextState.outputs[0].artifact_id).toBeTruthy();
      expect(
        (await api('get', 'ai/studio/artifacts/' + nextState.outputs[0].artifact_id)).status,
      ).toBe('pending_review');
      await p.reload();
      await owned('ai/studio/generations/' + next.id);
      return;
    }
    case 'L-12': {
      const gen = await api('post', 'ai/images/generate', {
        brand_id: brand.id,
        product_id: product.id,
        operation: 'generate_product_image',
        channel: 'canonical',
        width: 64,
        height: 64,
        output_count: 1,
        provider: 'deterministic_mock_v1',
        idempotency_key: 'wp7a5-failed-image-' + run.label,
      });
      await fail();
      const saved = await api('get', 'ai/images/generations/' + gen.generation_id);
      const output = saved.outputs[0];
      await p.goto(s.origin + '/ai/images/assets/' + output.id);
      await expect(p.locator('main')).toContainText(/failed|no processed image/i);
      await expect(
        p.getByRole('button', { name: 'Approve exact output', exact: true }),
      ).toBeDisabled();
      await expect(p.getByRole('button', { name: 'Regenerate', exact: true })).toBeDisabled();
      const retry = waitResponse(p, '/studio/recovery/actions');
      await p.getByRole('button', { name: 'Retry exact image job', exact: true }).click();
      expect((await retry).status()).toBe(200);
      await worker();
      await p.getByRole('button', { name: 'Refresh exact output', exact: true }).click();
      await expect(
        p.getByRole('button', { name: 'Approve exact output', exact: true }),
      ).toBeEnabled();
      await p.reload();
      const recovered = await api('get', 'ai/images/outputs/' + output.id);
      expect(recovered.job_id).toBe(output.job_id);
      expect(recovered.media_id).toBeTruthy();
      expect(recovered.status).not.toBe('approved');
      await p.getByRole('button', { name: 'Show history', exact: true }).click();
      await expect(p.locator('main')).toContainText('History events:');
      await owned('ai/images/outputs/' + output.id);
      await owned('media/' + recovered.media_id);
      const regeneration = waitResponse(p, '/outputs/' + output.id + '/regenerate');
      await p.getByRole('button', { name: 'Regenerate', exact: true }).click();
      const child = (await (await regeneration).json()).outputs[0];
      expect(child.id).not.toBe(output.id);
      await worker();
      await p.getByRole('button', { name: 'Refresh exact output', exact: true }).click();
      await p.reload();
      const descendant = await api('get', 'ai/images/outputs/' + child.id);
      expect(descendant.parent_output_id).toBe(output.id);
      expect(descendant.parent_media_id).toBe(recovered.media_id);
      expect(descendant.status).not.toBe('approved');
      expect((await api('get', 'ai/images/outputs/' + output.id)).media_id).toBe(
        recovered.media_id,
      );
      return;
    }
    case 'L-13': {
      const op = await api('post', 'ai/studio/bulk', {
        product_ids: [product.id],
        channels: ['canonical'],
        content_types: ['product_title', 'product_description'],
        locale: 'en-IN',
        idempotency_key: 'wp7a5-text-bulk-' + run.label,
      });
      await one();
      await fail();
      let saved = await api('get', 'ai/studio/bulk/' + op.id);
      expect(saved.outputs.some((o) => o.artifact_id)).toBe(true);
      expect(saved.outputs.some((o) => o.status === 'failed')).toBe(true);
      await p.goto(s.origin + '/ai/studio/bulk');
      const row = p
        .locator('.ai-bulk-operation')
        .filter({ hasText: /partially|failed/ })
        .first();
      await row.getByRole('button', { name: 'Open details', exact: true }).click();
      const request = waitResponse(p, `/bulk/${op.id}/retry-failed`);
      await row.getByRole('button', { name: 'Retry failed', exact: true }).click();
      expect((await request).status()).toBe(200);
      const replay = await Promise.all([
        api('post', `ai/studio/bulk/${op.id}/retry-failed`, {}),
        api('post', `ai/studio/bulk/${op.id}/retry-failed`, {}),
      ]);
      expect(replay).toHaveLength(2);
      await worker();
      saved = await api('get', 'ai/studio/bulk/' + op.id);
      expect(new Set(saved.outputs.map((o) => o.job_id)).size).toBe(2);
      expect(saved.outputs.every((o) => o.artifact_id)).toBe(true);
      await p.reload();
      await p.getByRole('button', { name: 'Open details', exact: true }).first().click();
      await expect(p.locator('main')).toContainText(/completed|succeeded/i);
      await owned('ai/studio/bulk/' + op.id);
      const cancellable = await api('post', 'ai/studio/bulk', {
        product_ids: [product.id],
        channels: ['canonical'],
        content_types: ['product_title'],
        locale: 'en-IN',
        idempotency_key: 'wp7a5-text-cancel-' + run.label,
      });
      await p.reload();
      const cancelRow = p
        .locator('.ai-bulk-operation')
        .filter({ hasText: /queued/ })
        .first();
      const cancelled = waitResponse(p, `/bulk/${cancellable.id}/cancel`);
      await cancelRow.getByRole('button', { name: 'Cancel remaining', exact: true }).click();
      expect((await cancelled).status()).toBe(200);
      await api('post', `ai/studio/bulk/${cancellable.id}/cancel`, {});
      await worker();
      expect(
        (await api('get', 'ai/studio/bulk/' + cancellable.id)).outputs.every(
          (o) => o.status === 'cancelled',
        ),
      ).toBe(true);
      expect(
        (await api('get', 'ai/studio/bulk/' + op.id)).outputs.every((o) => o.artifact_id),
      ).toBe(true);
      await p.reload();
      return;
    }
    case 'L-15': {
      const a = await content();
      await p.goto(s.origin + `/ai/studio/seo?product=${product.id}&artifact=${a.id}`);
      await p.getByRole('button', { name: 'Keywords', exact: true }).click();
      const name = '[QA SYNTHETIC] WP7A5 keywords ' + run.label;
      await p.getByLabel('Name', { exact: true }).fill(name);
      await p.getByLabel('Paste keywords', { exact: true }).fill('synthetic\nlocal');
      let response = waitResponse(p, '/ai/seo/keywords');
      await p.getByRole('button', { name: 'Save Keyword Set', exact: true }).click();
      const created = await (await response).json();
      expect(created.product_id).toBe(product.id);
      await p.getByRole('button', { name: 'Edit ' + name, exact: true }).click();
      await p.getByLabel('Paste keywords', { exact: true }).fill('synthetic\nupdated');
      response = waitResponse(p, '/ai/seo/keywords/' + created.id, 'PUT');
      await p.getByRole('button', { name: 'Save Keyword Set', exact: true }).click();
      const changed = await (await response).json();
      expect(changed.version).toBe(created.version + 1);
      await p.reload();
      await p.getByRole('button', { name: 'Keywords', exact: true }).click();
      await expect(p.getByRole('list', { name: 'Saved keyword sets' })).toContainText(name);
      await p.getByRole('button', { name: 'Tags', exact: true }).click();
      await p
        .getByLabel('Tag set name', { exact: true })
        .fill('[QA SYNTHETIC] WP7A5 tags ' + run.label);
      await p.getByLabel('Tags', { exact: true }).fill('#synthetic\nsynthetic');
      response = waitResponse(p, '/ai/seo/tags');
      await p.getByRole('button', { name: 'Save tags', exact: true }).click();
      const tags = await (await response).json();
      expect(tags.tags).toEqual(['synthetic']);
      await expect(p.getByRole('list', { name: 'Saved tag sets' })).toContainText('WP7A5 tags');
      await p.getByRole('button', { name: 'Edit ' + tags.name, exact: true }).click();
      await p.getByLabel('Tags', { exact: true }).fill('#updated\nupdated');
      response = waitResponse(p, '/ai/seo/tags/' + tags.id, 'PUT');
      await p.getByRole('button', { name: 'Save tags', exact: true }).click();
      expect((await (await response).json()).tags).toEqual(['updated']);
      await p.reload();
      expect((await api('get', 'ai/seo/tags')).find((t) => t.id === tags.id).tags).toEqual([
        'updated',
      ]);
      await p.getByRole('button', { name: 'Overview', exact: true }).click();
      await p.getByLabel(/^Saved keyword set/).selectOption(created.id);
      response = waitResponse(p, '/ai/seo/analyze');
      await p.getByRole('button', { name: 'Analyze', exact: true }).click();
      const analysis = await (await response).json();
      expect(analysis.product_id).toBe(product.id);
      expect(analysis.keyword_set_id).toBe(created.id);
      expect(analysis.keyword_set_version).toBe(changed.version);
      await expect(p.locator('main')).toContainText('Search volume unavailable');
      await p.getByRole('button', { name: 'Analysis History', exact: true }).click();
      await p.getByRole('button', { name: 'Refresh history', exact: true }).click();
      response = waitResponse(p, `/analyses/${analysis.id}/reanalyze`);
      await p
        .getByRole('button', { name: 'Re-analyze saved snapshot', exact: true })
        .first()
        .click();
      const revised = await (await response).json();
      expect(revised.id).toBe(analysis.id); // same fingerprint is canonical idempotent reanalysis
      expect((await api('get', 'ai/seo/analyses/' + analysis.id)).artifact_version).toBe(
        analysis.artifact_version,
      );
      await p.getByLabel('Primary keyword', { exact: true }).fill('changed synthetic phrase');
      response = waitResponse(p, '/ai/seo/analyze');
      await p.getByRole('button', { name: 'Analyze', exact: true }).click();
      const newAnalysis = await (await response).json();
      expect(newAnalysis.id).not.toBe(analysis.id);
      expect((await api('get', 'ai/seo/analyses/' + analysis.id)).status).toBe('stale');
      await p.reload();
      await owned('ai/seo/analyses/' + analysis.id);
      return;
    }
    case 'L-21': {
      await content();
      const data = {
        product_ids: [product.id],
        video_types: ['product_showcase', 'product_demo'],
        targets: ['youtube'],
        duration_seconds: 2,
        resolution: '320x240',
        idempotency_key: 'wp7a5-video-bulk-' + run.label,
      };
      const preview = await api('post', 'ai/video/bulk/preview', data);
      const op = await api('post', 'ai/video/bulk', {
        ...data,
        confirm: true,
        preview_fingerprint: preview.plan_fingerprint,
      });
      await one();
      await fail();
      let saved = await api('get', 'ai/video/bulk/' + op.id);
      expect(saved.children.some((c) => c.status === 'succeeded')).toBe(true);
      expect(saved.children.some((c) => c.status === 'failed')).toBe(true);
      await p.goto(s.origin + '/ai/video/bulk?operation=' + op.id);
      await expect(p.locator('main')).toContainText(op.id);
      await p.reload();
      const response = waitResponse(p, `/bulk/${op.id}/retry-failed`);
      await p.getByRole('button', { name: 'Retry failed children', exact: true }).click();
      expect((await response).status()).toBe(200);
      await Promise.all([
        api('post', `ai/video/bulk/${op.id}/retry-failed`, {}),
        api('post', `ai/video/bulk/${op.id}/retry-failed`, {}),
      ]);
      await worker();
      saved = await api('get', 'ai/video/bulk/' + op.id);
      expect(saved.children.every((c) => c.status === 'succeeded')).toBe(true);
      expect(new Set(saved.children.map((c) => c.job_id)).size).toBe(2);
      await p.getByRole('button', { name: 'Refresh status', exact: true }).click();
      await expect(p.locator('main')).toContainText('video_bulk_child_retried');
      await p.reload();
      await expect(p.locator('main')).toContainText(op.id);
      await owned('ai/video/bulk/' + op.id);
      const cancelledData = { ...data, idempotency_key: 'wp7a5-video-cancel-' + run.label };
      const cancelledPreview = await api('post', 'ai/video/bulk/preview', cancelledData);
      const cancelOp = await api('post', 'ai/video/bulk', {
        ...cancelledData,
        confirm: true,
        preview_fingerprint: cancelledPreview.plan_fingerprint,
      });
      await p.goto(s.origin + '/ai/video/bulk?operation=' + cancelOp.id);
      const cancel = waitResponse(p, `/bulk/${cancelOp.id}/cancel`);
      await p.getByRole('button', { name: 'Cancel remaining children', exact: true }).click();
      expect((await cancel).status()).toBe(200);
      await Promise.all([
        api('post', `ai/video/bulk/${cancelOp.id}/cancel`, {}),
        api('post', `ai/video/bulk/${cancelOp.id}/cancel`, {}),
      ]);
      await worker();
      await p.reload();
      expect(
        (await api('get', 'ai/video/bulk/' + cancelOp.id)).children.every(
          (c) => c.status === 'cancelled',
        ),
      ).toBe(true);
      expect(
        (await api('get', 'ai/video/bulk/' + op.id)).children.every(
          (c) => c.status === 'succeeded',
        ),
      ).toBe(true);
      await expect(p.locator('main')).toContainText('cancelled');
      return;
    }
    case 'L-16': {
      const campaign = await c(),
        a = await content();
      const destinationId = (await h.publishing()).destination_id;
      const activity = await api('post', `campaigns/${campaign.id}/activities`, {
        activity_type: 'mock_publish',
        name: '[QA SYNTHETIC] WP7A5 freshness',
        sequence: 4,
        product_id: product.id,
        artifact_id: a.id,
        destination_id: destinationId,
        scheduled_local_date: '2026-11-12',
        scheduled_local_time: '09:00:00',
      });
      await p.goto(s.origin + '/campaigns/' + campaign.id);
      await p.reload();
      await expect(p.locator('main')).toContainText(activity.name);
      await api('patch', 'products/' + product.id, {
        description: '[QA SYNTHETIC] changed campaign input',
      });
      await api('post', `publishing/destinations/${destinationId}/disable`, {});
      await p.goto(s.origin + '/campaigns/' + campaign.id);
      let readiness = waitResponse(p, `/campaigns/${campaign.id}/validate`);
      await p.getByRole('button', { name: 'Review readiness', exact: true }).click();
      const blocked = await (await readiness).json();
      expect(
        blocked.issues.some(
          (i) => i.activity_id === activity.id && i.code === 'destination_disabled',
        ),
      ).toBe(true);
      await p.reload();
      await expect(p.locator('main')).toContainText(activity.name);
      await api('post', `publishing/destinations/${destinationId}/enable`, {});
      await p.goto(s.origin + '/campaigns/' + campaign.id);
      readiness = waitResponse(p, `/campaigns/${campaign.id}/validate`);
      await p.getByRole('button', { name: 'Review readiness', exact: true }).click();
      const refreshed = await (await readiness).json();
      expect(
        refreshed.issues.some(
          (i) => i.activity_id === activity.id && i.code === 'destination_disabled',
        ),
      ).toBe(false);
      const current = await api('get', `campaigns/${campaign.id}/activities`);
      expect(current.find((x) => x.id === activity.id).artifact_id).toBe(a.id);
      await p.reload();
      await owned('campaigns/' + campaign.id);
      return partial(
        'Exact approved binding, changed product, disabled prerequisite/recovery and reload checked. Artifact-version replacement and dependency ordering remain unexecuted; approved content is not rejected through a UI that intentionally does not expose that action.',
      );
    }
    case 'R-3feda36d':
    case 'L-22': {
      const a = await content(),
        img = await image();
      const v = await h.once('socialVideo', async () => {
        const queued = await api('post', 'ai/video/queue', {
          brand_id: brand.id,
          product_id: product.id,
          video_type: 'youtube_video',
          target_channel: 'youtube',
          resolution: '320x240',
          duration_seconds: 2,
          idempotency_key: 'wp7a5-social-video-' + run.label,
        });
        await worker();
        await p.goto(s.origin + '/ai/video?generation=' + queued.id);
        await expect(p.locator('main')).toContainText(queued.id);
        const approved = waitResponse(p, '/generations/' + queued.id + '/approve');
        await p
          .locator('article')
          .filter({ has: p.getByRole('heading', { name: 'Lineage & readiness', exact: true }) })
          .getByRole('button', { name: 'Approve', exact: true })
          .click();
        expect((await approved).status()).toBe(200);
        return api('get', 'ai/video/generations/' + queued.id);
      });
      await p.goto(s.origin + '/ai/images/assets/' + img.id);
      if ((await api('get', 'ai/images/outputs/' + img.id)).status !== 'approved') {
        const approved = waitResponse(p, '/outputs/' + img.id + '/approve');
        await p.getByRole('button', { name: 'Approve exact output', exact: true }).click();
        expect((await approved).status()).toBe(200);
      }
      const account = await api('post', 'social/accounts', {
        platform: 'youtube',
        environment: 'local',
        display_name: '[QA SYNTHETIC] WP7A5 social ' + entry.id,
        remote_account_id: 'qa-wp7a5-' + entry.id + '-' + run.label,
        credentials: {},
        capabilities: { supported_content_types: ['youtube_video'] },
      });
      await api('post', `social/accounts/${account.id}/validate`, {});
      await api('post', `social/accounts/${account.id}/enable`, {});
      await p.goto(s.origin + '/social/compose');
      await p.getByLabel(/^Platform/).selectOption('youtube');
      await p.getByLabel(/^Format/).selectOption('youtube_video');
      await p.getByRole('button', { name: 'Next', exact: true }).click();
      await p.getByRole('button', { name: 'Next', exact: true }).click();
      await p.getByRole('combobox', { name: 'Brand', exact: true }).selectOption(brand.id);
      await p
        .getByRole('combobox', { name: 'Product', exact: true })
        .first()
        .selectOption(product.id);
      const next = () => p.getByRole('button', { name: 'Next', exact: true }).click();
      await next(); // 4: exact generation selector
      await p.getByLabel(/^Approved Video selector/).selectOption(v.id);
      await next(); // 5: metadata
      await p.getByRole('combobox', { name: 'Approved content', exact: true }).selectOption(a.id);
      await next(); // 6: thumbnail
      await p.getByLabel('Image Output ID', { exact: true }).fill(img.id);
      await next();
      await next(); // 8: account
      await p.getByLabel(/^Account/).selectOption(account.id);
      expect(await p.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
        p.viewportSize().width,
      );
      await next();
      await next(); // 10: preview only
      const prepared = waitResponse(p, '/video/channels/prepare');
      await p.getByRole('button', { name: 'Preview exact post', exact: true }).click();
      const preparationResponse = await prepared;
      expect(preparationResponse.status()).toBe(200);
      const preparation = await preparationResponse.json();
      await expect(p.locator('main')).toContainText(v.output_id);
      const confirmed = waitResponse(p, '/channels/' + preparation.id + '/confirm');
      await p.getByRole('button', { name: 'Save reviewed Video draft', exact: true }).click();
      const result = await confirmed;
      expect(result.status()).toBe(200);
      const postId = (await result.json()).social_post_id;
      await expect(p).toHaveURL(new RegExp('/social/posts/' + postId + '$'));
      await p.reload();
      const saved = await api('get', 'social/posts/' + postId);
      expect(saved.video_generation_id).toBe(v.id);
      expect(saved.video_output_id).toBe(v.output_id);
      expect(saved.thumbnail_output_id).toBe(img.id);
      expect(saved.metadata_artifact_id).toBe(a.id);
      expect(saved.lifecycle_status).toBe('draft');
      expect(saved.remote_publication_id).toBeNull();
      const stale = await p.request.post(url('ai/video/channels/preview'), {
        data: {
          video_generation_id: v.id,
          channel: 'youtube',
          target_id: account.id,
          metadata_artifact_id: a.id,
          metadata_artifact_version: a.version_number + 100,
          idempotency_key: 'social-video-prepare-stale-' + entry.id + '-' + run.label,
        },
      });
      expect(stale.status()).toBe(409);
      await owned('social/posts/' + postId);
      return;
    }
    case 'R-55e822d5': {
      for (const channel of ['amazon', 'flipkart', 'meesho']) await listing(channel);
      await p.goto(s.origin + '/marketplaces/overview');
      await p.reload();
      await expect(p.locator('main')).toContainText(/amazon/i);
      const accounts = await api('get', 'marketplaces/accounts');
      expect(accounts.every((a) => a.environment === 'sandbox')).toBe(true);
      return partial(
        'Configured synthetic sandbox accounts are persisted and overview reloaded. Connected/revoked/expired canonical channel-account projections need exact channel-specific fixtures.',
      );
    }
    case 'R-551d2f8c':
    case 'R-db243c36':
    case 'R-d6a495d5': {
      const channel = { 'R-551d2f8c': 'flipkart', 'R-db243c36': 'meesho', 'R-d6a495d5': 'amazon' }[
        entry.id
      ];
      const target = await listing(channel);
      await p.goto(s.origin + `/marketplaces/listings/${target.id}/${channel}`);
      await p.reload();
      await expect(p.locator('main')).toContainText(new RegExp(channel, 'i'));
      await owned('marketplaces/listings/' + target.id);
      return partial(
        `Exact ${channel} draft/default-deny remains correct; full readiness correction plus missing/expired/revoked/stale HUMAN authorization UI permutations not executed. No submit/transport invoked.`,
      );
    }
    case 'L-17': {
      const a = await h.adAccount();
      await p.goto(s.origin + '/ads/create');
      await p.locator('select[name=account_id]').selectOption(a.id);
      await p.reload();
      await expect(p.locator('main')).toContainText(/campaign/i);
      return partial(
        'Owned fake local account creation/validation and Ads wizard reload exercised; content/image creative, stale/expired authorization permutations not yet established.',
      );
    }
    case 'L-23': {
      const data = {
        brand_id: brand.id,
        product_ids: [product.id],
        objective: 'sales',
        target_channels: ['social', 'campaign'],
        budget_envelope: { total: '250.50', currency: 'INR', allocations: {} },
        strategy_mode: 'manual',
        automation_mode: 'manual',
        creative_mapping: {},
        targeting: {},
        schedule: { mode: 'immediate' },
        idempotency_key: 'web-marketing-plan-wp7a5-' + run.label,
      };
      const initial = await api('post', 'ads/marketing/plans/preview', {
        plan: data,
        expected_version: 1,
      });
      const created = await api('post', 'ads/marketing/plans/confirm', {
        plan: data,
        expected_version: 1,
        preview_fingerprint: initial.fingerprint,
        confirm: true,
      });
      await p.goto(s.origin + '/ads/marketing');
      await p.getByRole('button', { name: 'Review plan details', exact: true }).first().click();
      await expect(p.locator('main')).toContainText(created.id);
      await expect(p.locator('main')).toContainText('Canonical recommendations');
      const field = p.getByLabel('Proposed total budget', { exact: true });
      await field.fill('-1');
      let response = waitResponse(p, `/plans/${created.id}/budget/preview`);
      await p.getByRole('button', { name: 'Preview budget revision', exact: true }).click();
      expect((await (await response).json()).valid).toBe(false);
      await expect(
        p.getByRole('button', { name: 'Confirm reviewed budget revision', exact: true }),
      ).toBeDisabled();
      await field.fill('300.50');
      response = waitResponse(p, `/plans/${created.id}/budget/preview`);
      await p.getByRole('button', { name: 'Preview budget revision', exact: true }).click();
      const preview = await (await response).json();
      expect(preview.valid).toBe(true);
      expect((await api('get', 'ads/marketing/plans/' + created.id)).current_version).toBe(1);
      response = waitResponse(p, `/plans/${created.id}/budget/confirm`);
      await p
        .getByRole('button', { name: 'Confirm reviewed budget revision', exact: true })
        .click();
      const confirmed = await response;
      expect(confirmed.status()).toBe(200);
      const confirmedBody = confirmed.request().postDataJSON();
      await Promise.all([
        api('post', `ads/marketing/plans/${created.id}/budget/confirm`, confirmedBody),
        api('post', `ads/marketing/plans/${created.id}/budget/confirm`, confirmedBody),
      ]);
      const saved = await api('get', 'ads/marketing/plans/' + created.id);
      expect(saved.current_version).toBe(2);
      expect(String(saved.budget_envelope.total)).toBe('300.50');
      expect(saved.budget_envelope.allocations).toEqual({});
      const stale = await p.request.post(url(`ads/marketing/plans/${created.id}/budget/preview`), {
        data: {
          proposed: preview.proposed,
          expected_version: 1,
          preview_fingerprint: 'preview-not-confirmed',
        },
      });
      expect(stale.status()).toBe(409);
      await p.reload();
      await expect(p.locator('main')).toContainText('Saved plan v2');
      await owned('ads/marketing/plans/' + created.id);
      return;
    }
    default:
      throw Error('UNMAPPED_WP7A5_ORIGINAL_ID');
  }
}
