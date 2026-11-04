// Additional offline-only QA interactions. Does not authorize any provider or worker.
export function wp7aPath(path, method) {
  return (
    method === 'POST' &&
    (path === '/__qa/wp7a/control' ||
      /^\/api\/v1\/intelligence\/business-agent\/runs\/[a-f0-9-]+\/(start|retry|resume|pause|cancel)$/.test(
        path,
      ) ||
      /^\/api\/v1\/marketplaces\/accounts\/[a-f0-9-]+\/(enable|disable|remove-credential)$/.test(
        path,
      ) ||
      /^\/api\/v1\/marketplaces\/accounts\/[a-f0-9-]+\/imports$/.test(path) ||
      ['/api/v1/ai/video/queue', '/api/v1/ai/video/preview'].includes(path) ||
      /^\/api\/v1\/ai\/video\/generations\/[a-f0-9-]+\/captions$/.test(path))
  );
}
export function safeWp7aPayload(path, body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return false;
  if (path === '/__qa/wp7a/control')
    return (
      ['NONE', 'PROVIDER_UNAVAILABLE', 'EXPIRED', 'INVALID', 'REVOKED', 'EXPIRE_SESSION'].includes(
        body.scenario,
      ) && Object.keys(body).every((k) => ['scenario', 'account_id'].includes(k))
    );
  if (path.endsWith('/runs'))
    return (
      typeof body.idempotency_key === 'string' &&
      (body.idempotency_key.startsWith('wp7a-') ||
        body.idempotency_key.startsWith('business-goal-')) &&
      (body.max_provider_calls === undefined || body.max_provider_calls === 0) &&
      body.max_steps <= 20 &&
      Object.keys(body).every((k) =>
        [
          'max_steps',
          'max_provider_calls',
          'idempotency_key',
          'max_retries',
          'deadline_seconds',
        ].includes(k),
      )
    );
  if (path.endsWith('/imports'))
    return (
      body.operation === 'catalog' &&
      ['SYNTHETIC', 'SANDBOX', 'LIVE_READ_ONLY'].includes(body.mode) &&
      typeof body.idempotency_key === 'string' &&
      Object.keys(body).every((k) => ['operation', 'mode', 'idempotency_key'].includes(k))
    );
  if (path.includes('/video/queue') || path.includes('/video/preview'))
    return (
      (!body.failure_scenario || body.failure_scenario === 'success') &&
      !body.source_artifact_id &&
      !body.script_id &&
      !body.storyboard_id &&
      !body.style_id &&
      !body.preset_id &&
      !body.audio_media_id &&
      (!body.source_media_ids || body.source_media_ids.length === 0) &&
      (!body.audio_mode || body.audio_mode === 'none') &&
      Object.keys(body).every((k) =>
        [
          'brand_id',
          'product_id',
          'video_type',
          'target_channel',
          'resolution',
          'duration_seconds',
          'audio_mode',
          'idempotency_key',
          'failure_scenario',
        ].includes(k),
      )
    );
  if (path.endsWith('/captions'))
    return (
      body.locale === 'en-IN' &&
      typeof body.caption_text === 'string' &&
      body.caption_text.startsWith('[QA SYNTHETIC]')
    );
  return Object.keys(body).length === 0;
}
