// Canonical API fixture preparation only. Every identity and amount is synthetic.
export const wp3Owner = { email: 'qa-wp3@example.com', password: 'SyntheticWP3Only123!' };

export function wp3Api(page, origin) {
  return async (method, suffix, data) => {
    const response = await page.request[method](origin + '/api/v1/' + suffix, { data });
    if (!response.ok()) throw Error(`WP3_FIXTURE_${response.status()}_${suffix.split('/').at(-1)}`);
    return response.json();
  };
}

export async function wp3Product(page, origin) {
  const api = wp3Api(page, origin);
  const brand = await api('post', 'brands', { name: '[QA SYNTHETIC] WP3 Brand' });
  const op = await api('post', 'intelligence/product-opportunities', {
    name: '[QA SYNTHETIC] WP3 Bottle',
    description: 'Synthetic reusable bottle for disposable local QA, not live market evidence.',
    product_concept: 'stainless steel insulated water bottles',
    category: 'Home & Kitchen',
    target_marketplace: 'AMAZON_IN',
    target_region: 'IN',
    origin: 'manual',
    notes: 'DETERMINISTIC_TEST / SYNTHETIC',
    idempotency_key: 'wp3-op',
  });
  const constraint = await api('post', `intelligence/product-opportunities/${op.id}/constraints`, {
    available_capital: '300000',
    currency: 'INR',
    marketplace: 'AMAZON_IN',
    idempotency_key: 'wp3-constraint',
  });
  const assessment = await api('post', `intelligence/product-opportunities/${op.id}/assessments`, {
    constraint_version_id: constraint.id,
    evidence_state: 'insufficient_evidence',
    status: 'created',
    input_snapshot: { evidence_environment: 'DETERMINISTIC_TEST' },
  });
  await api(
    'post',
    `intelligence/product-opportunities/${op.id}/assessments/${assessment.id}/score`,
    { idempotency_key: 'wp3-score' },
  );
  const goal = await api('post', 'intelligence/business-agent/goals', {
    raw_goal: 'Research a bottle for Amazon India with INR 300000. Synthetic local QA only.',
    structured_goal: {
      product_opportunity_id: op.id,
      marketplace: 'AMAZON_IN',
      category: 'Home & Kitchen',
      currency: 'INR',
      capital: 300000,
    },
    provenance: { mode: 'LOCAL_FIXTURE', evidence_environment: 'DETERMINISTIC_TEST' },
    idempotency_key: 'wp3-goal',
  });
  await api('post', `intelligence/business-agent/goals/${goal.id}/plan`, {});
  return { api, op, assessment, goal, brand };
}

export async function wp3Economics(api, op, assessment) {
  const base = `intelligence/product-opportunities/${op.id}/assessments/${assessment.id}`;
  const assumptions = [
    ['supplier_unit_price', '100.125', { unit: 'per_unit', currency: 'INR' }],
    ['supplier_currency', 'INR', {}],
    ['freight_cost', '2500', { unit: 'per_shipment', currency: 'INR' }],
    ['freight_currency', 'INR', {}],
    ['origin', 'IN', {}],
    ['destination', 'IN', {}],
  ].map(([key, value, extra]) => ({
    key,
    value,
    ...extra,
    reason: 'Hypothetical synthetic QA assumption, not an actual supplier quotation.',
  }));
  const readiness = await api('post', base + '/commercial-readiness', {
    idempotency_key: 'wp3-readiness',
    scenario_key: 'DETERMINISTIC_TEST',
    assumptions,
  });
  const landed = await api('post', base + '/landed-cost', {
    idempotency_key: 'wp3-landed',
    base_currency: 'INR',
    target_quantity: '500',
    quantity_unit: 'unit',
  });
  const unit = await api('post', base + '/commercial/unit-economics', {
    idempotency_key: 'wp3-unit',
    selling_price: '250',
    selling_price_currency: 'INR',
    selling_price_provenance: 'DETERMINISTIC_TEST',
    quantity: '500',
    selling_cost_components: [
      {
        key: 'scenario_percent',
        basis: 'PERCENT_OF_SELLING_PRICE',
        currency: 'INR',
        required: true,
        provenance: 'DETERMINISTIC_TEST',
        marker: 'DETERMINISTIC_TEST',
        reason: 'Hypothetical only; not an Amazon fee schedule.',
        rate: '10',
      },
      {
        key: 'scenario_order',
        basis: 'PER_ORDER',
        currency: 'INR',
        required: true,
        provenance: 'DETERMINISTIC_TEST',
        marker: 'DETERMINISTIC_TEST',
        reason: 'Hypothetical only; not an Amazon fee schedule.',
        amount: '50',
      },
    ],
  });
  return { readiness, landed, unit };
}
