import fs from 'node:fs/promises';
import path from 'node:path';

// Normal authenticated APIs only, on the freshly witnessed owned child. These
// are local draft/media records, never provider acquisition or approvals.
export async function prepareAuditArtifacts({ apiPort, origin, token, runDir }) {
  if (process.env.QA_DATABASE_ADMIN_URL === undefined || !/^[a-f0-9]{16}$/.test(token))
    throw new Error('QA_AUDIT_FIXTURE_GUARD');
  const base = `http://127.0.0.1:${apiPort}`;
  const witness = await (await fetch(base + '/__qa/witness')).json();
  if (witness.token !== token || !witness.disposable) throw new Error('QA_AUDIT_WITNESS');
  let cookie;
  const operations = [];
  async function request(route, data, multipart = false) {
    const response = await fetch(base + route, {
      method: data === undefined ? 'GET' : 'POST',
      headers: {
        Origin: origin,
        ...(cookie ? { Cookie: cookie } : {}),
        ...(data !== undefined && !multipart ? { 'Content-Type': 'application/json' } : {}),
      },
      body: data === undefined ? undefined : multipart ? data : JSON.stringify(data),
      signal: AbortSignal.timeout(45000),
    });
    operations.push({ route, status: response.status });
    if (!response.ok) throw new Error(`QA_AUDIT_ARTIFACT_HTTP_${response.status}`);
    if (route.endsWith('/login')) cookie = response.headers.get('set-cookie')?.split(';')[0];
    return response.json();
  }
  await request('/api/v1/auth/login', {
    email: 'qa-phase3-owner@example.com',
    password: 'SyntheticPhase3Only123!',
  });
  const manifest = JSON.parse(await fs.readFile(path.join(runDir, 'phase3-manifest.json'), 'utf8'));
  const campaign = await request('/api/v1/campaigns', {
    brand_id: manifest.brand_id,
    name: '[QA SYNTHETIC] Phase 4C local draft',
    timezone_name: 'Asia/Kolkata',
    local_start_at: '2027-01-01T09:00:00',
    local_end_at: '2027-01-02T09:00:00',
    approval_policy: 'manual_campaign_release',
  });
  const form = new globalThis.FormData();
  const png = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a4x8AAAAASUVORK5CYII=',
    'base64',
  );
  form.append(
    'file',
    new globalThis.Blob([png], { type: 'image/png' }),
    'qa-synthetic-phase4c.png',
  );
  const media = await request('/api/v1/media', form, true);
  const result = {
    campaign_id: campaign.id,
    media_id: media.id,
    media_filename: media.safe_filename,
    operations,
    scope: 'synthetic local drafts; no execution, review or authorization issued',
  };
  await fs.writeFile(path.join(runDir, 'phase4c-manifest.json'), JSON.stringify(result, null, 2));
  return result;
}
