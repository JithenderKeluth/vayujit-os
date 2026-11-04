// Acceptance assertions are appended only after real assertions. Partial is not closure.
export async function execute(entry, h) {
  const {
    p,
    s,
    expect,
    api,
    run,
    brand,
    product,
    content,
    media,
    listing,
    readDetail,
    waitResponse,
  } = h;
  const assertions = [];
  let persisted = false;
  const snapshot = async (table, id) => {
    const r = await p.request.get(s.origin + '/__qa/wp7a4/state', {
      headers: { 'x-qa-token': s.token },
    });
    expect(r.status()).toBe(200);
    const state = await r.json();
    const row = state[table]?.find((row) => row.id === id);
    expect(row).toBeTruthy();
    persisted = true;
    return row;
  };
  const result = (reason) => ({
    status: 'PARTIAL',
    reason,
    acceptance_assertions: assertions,
    persisted_state_verified: persisted,
  });
  if (entry.id === 'R-3feda36d') {
    const artifact = await content(),
      asset = await media();
    const account = await api('post', 'social/accounts', {
      platform: 'facebook',
      environment: 'local',
      display_name: '[QA SYNTHETIC] image ' + run.label,
      remote_account_id: 'qa-image-' + run.label,
      credentials: {},
      capabilities: { supported_content_types: ['facebook_post'] },
    });
    await api('post', 'social/accounts/' + account.id + '/validate', {});
    await api('post', 'social/accounts/' + account.id + '/enable', {});
    await p.goto(s.origin + '/social/compose');
    await expect(p.getByRole('heading', { name: 'Image-only draft', exact: true })).toBeVisible();
    const form = p
      .getByRole('article')
      .filter({ has: p.getByRole('heading', { name: 'Image-only draft', exact: true }) });
    await expect(
      form.getByRole('button', { name: 'Save image-only draft', exact: true }),
    ).toBeDisabled();
    await form.getByLabel('Brand', { exact: true }).selectOption(brand.id);
    await form.getByLabel('Product', { exact: true }).selectOption(product.id);
    await form.getByLabel('Approved content', { exact: true }).selectOption(artifact.id);
    await form.getByLabel('Image post account', { exact: true }).selectOption(account.id);
    await form
      .getByLabel('Exact content version', { exact: true })
      .fill(String(artifact.version_number));
    await form.getByLabel('Owned image Media Asset ID', { exact: true }).fill(asset.id);
    await form
      .getByLabel('Image draft caption', { exact: true })
      .fill('[QA SYNTHETIC] image-only draft');
    const response = waitResponse(p, '/social/posts');
    await form.getByRole('button', { name: 'Save image-only draft', exact: true }).click();
    const created = await response;
    expect(created.status()).toBe(201);
    const post = await created.json();
    await expect(p).toHaveURL(new RegExp('/social/posts/' + post.id + '$'));
    await expect(p.getByRole('heading', { name: 'Image draft review', exact: true })).toBeVisible();
    expect(post.video_generation_id || post.video_output_id).toBeFalsy();
    expect(post.media_ids).toEqual([asset.id]);
    expect(post.product_id).toBe(product.id);
    assertions.push('image_only_created', 'context_provenance', 'preview_validation');
    await p.getByRole('button', { name: 'Preview image draft', exact: true }).click();
    await expect(p.locator('.preview')).toContainText('Ready for review');
    const first = await api('get', 'social/posts/' + post.id + '/preview');
    await p.getByLabel('Draft caption', { exact: true }).fill('[QA SYNTHETIC] edited image draft');
    const saved = waitResponse(p, '/social/posts/' + post.id, 'PATCH');
    await p.getByRole('button', { name: 'Save draft caption', exact: true }).click();
    expect((await saved).status()).toBe(200);
    await expect(p.locator('main')).toContainText('Previous preview is stale');
    const changed = await api('get', 'social/posts/' + post.id + '/preview');
    expect(changed.fingerprint).not.toBe(first.fingerprint);
    await p.reload();
    await expect(p.getByLabel('Draft caption', { exact: true })).toHaveValue(
      '[QA SYNTHETIC] edited image draft',
    );
    assertions.push('save_reload', 'edit_stale_review');
    const row = await snapshot('social_posts', post.id);
    expect(row.video_generation_id).toBeNull();
    expect(row.schedule_id).toBeNull();
    expect(row.remote_publication_id).toBeNull();
    return result(
      'Image-only creation, exact media/content/product, preview/edit stale fingerprint and reload verified; HUMAN review and concurrent-action matrix remain incomplete. No publication.',
    );
  }
  if (['R-551d2f8c', 'R-db243c36', 'R-d6a495d5'].includes(entry.id)) {
    const channel = { 'R-551d2f8c': 'flipkart', 'R-db243c36': 'meesho', 'R-d6a495d5': 'amazon' }[
      entry.id
    ];
    const draft = await listing(channel);
    await p.goto(s.origin + `/marketplaces/listings/${draft.id}/${channel}`);
    await expect(p.locator('main')).toContainText(new RegExp(channel, 'i'));
    await p.reload();
    await expect(p.locator('main')).toContainText(new RegExp(channel, 'i'));
    const ready = await api('get', `marketplaces/${channel}/listings/${draft.id}/readiness`);
    expect(ready.ready).toBe(false);
    assertions.push(channel === 'meesho' ? 'missing_readiness' : 'missing_prerequisite');
    const saved = await api('get', 'marketplaces/listings/' + draft.id);
    expect(saved.product_id).toBe(product.id);
    expect(saved.account_id).toBe(draft.account_id);
    const row = await snapshot('marketplace_listings', draft.id);
    expect(row.product_id).toBe(product.id);
    if (channel === 'amazon') {
      const response = await p.request.post(
        s.origin + `/api/v1/marketplaces/amazon/listings/${draft.id}/review`,
        { data: { confirm: true, product_type: 'Kids' } },
      );
      if (response.status() !== 409)
        throw Error('AMAZON_INCOMPLETE_REVIEW_HTTP_' + response.status());
      assertions.push('human_review');
    }
    return result(
      `${channel}: persisted draft and missing-readiness/default-deny checked; readiness correction and complete authorization matrix not yet verified.`,
    );
  }
  if (entry.id === 'R-55e822d5') {
    for (const channel of ['amazon', 'flipkart', 'meesho']) await listing(channel);
    await p.goto(s.origin + '/marketplaces/overview');
    await expect(p.locator('main')).toContainText(/amazon/i);
    await p.reload();
    const accounts = await api('get', 'marketplaces/accounts');
    expect(accounts.length).toBeGreaterThanOrEqual(3);
    expect(accounts.every((a) => a.environment === 'sandbox')).toBe(true);
    assertions.push('configured_not_connected');
    for (const account of accounts.filter((a) => ['amazon', 'flipkart'].includes(a.marketplace))) {
      const status = await api('get', `marketplaces/accounts/${account.id}/connectivity`);
      expect(status.external_writes).toBe(false);
      expect(status.provider_contract).toBe('UNVERIFIED');
      await snapshot('marketplace_accounts', account.id);
    }
    return result(
      'Sandbox configuration persisted; real connection is NOT certified. Expired/revoked and exact account projections remain unverified.',
    );
  }
  if (entry.id === 'L-16') {
    const c = await h.c();
    const act = await h.activity();
    await readDetail('/campaigns/' + c.id, 'campaigns/' + c.id, c.name);
    const saved = await api('get', 'campaigns/' + c.id + '/activities');
    expect(JSON.stringify(saved)).toContain(act.id);
    await snapshot('campaigns', c.id);
    assertions.push('draft_identity', 'reload_owned');
    return result(
      'Exact draft/activity persisted and reloaded; dependency/artifact-version stale fingerprint matrix remains unverified.',
    );
  }
  if (entry.id === 'L-17') {
    const account = await h.adAccount();
    await p.goto(s.origin + '/ads/create');
    await p.locator('select[name=account_id]').selectOption(account.id);
    await p.reload();
    await expect(p.locator('main')).toContainText(/campaign/i);
    return result(
      'Local fake account/wizard exercised without submission; complete creative/authorization matrix remains unverified. Historical 502 not classified as resolved.',
    );
  }
  throw Error('UNMAPPED_WP7A6_ID');
}
