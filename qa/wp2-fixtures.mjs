// Synthetic records via existing domain APIs only. No discovery/provider execution.
export const wp2Owner = { email: 'qa-wp2@example.com', password: 'SyntheticWP2Only123!' };
export async function wp2Fixtures(page, origin, runId = '') {
  const api = async (method, suffix, data) => {
    const response = await page.request[method](origin + '/api/v1/' + suffix, { data });
    if (!response.ok()) throw new Error('WP2_CANONICAL_FIXTURE_REJECTED');
    return response.json();
  };
  const items = [];
  for (const name of ['Bottle', 'Lunch Bag']) {
    const op = await api('post', 'intelligence/product-opportunities', {
      name: `[QA SYNTHETIC] ${name}`,
      description: 'Manual synthetic QA identity, not verified market evidence.',
      product_concept: name,
      category: 'Kids',
      target_marketplace: 'AMAZON_IN',
      target_region: 'IN',
      origin: 'manual',
      notes: 'DETERMINISTIC_TEST — no live market claims',
      idempotency_key: runId ? `business-agent:${runId}:candidate:wp2-${name}` : 'wp2-' + name,
    });
    const c = await api('post', `intelligence/product-opportunities/${op.id}/constraints`, {
      available_capital: '300000',
      currency: 'INR',
      marketplace: 'AMAZON_IN',
      idempotency_key: 'wp2-c-' + name,
    });
    const a = await api('post', `intelligence/product-opportunities/${op.id}/assessments`, {
      constraint_version_id: c.id,
      evidence_state: 'insufficient_evidence',
      status: 'created',
      input_snapshot: { evidence_environment: 'DETERMINISTIC_TEST' },
      idempotency_key: 'wp2-a-' + name,
    });
    await api('post', `intelligence/product-opportunities/${op.id}/assessments/${a.id}/score`, {
      idempotency_key: 'wp2-s-' + name,
    });
    items.push({ ...op, assessment_id: a.id });
  }
  return { items, api };
}
