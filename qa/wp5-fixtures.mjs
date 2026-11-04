// Only canonical local, explicitly synthetic records inside a witnessed QA installation.
export async function wp5Operations(api, brand) {
  const product = await api('post', 'products', {
    brand_id: brand.id,
    name: '[QA SYNTHETIC] WP5 Organizer',
    sku: 'QA-WP5-BOX',
    product_type: 'physical',
    price_amount: '100.13',
    price_currency: 'INR',
  });
  const item = await api('post', 'inventory/items', {
    product_id: product.id,
    internal_sku: product.sku,
    opening_quantity: 10,
    low_stock_threshold: 2,
    idempotency_key: 'wp5-opening',
  });
  const account = await api('post', 'marketplaces/accounts', {
    marketplace: 'flipkart',
    display_name: '[QA SYNTHETIC] WP5 sandbox',
    seller_account_id: 'qa3-wp5',
    environment: 'sandbox',
    credentials: {},
  });
  await api('post', 'inventory/mappings', {
    inventory_item_id: item.id,
    account_id: account.id,
    external_sku: product.sku,
    idempotency_key: 'wp5-mapping',
  });
  const event = (id, type = 'new_order', version = 1) => ({
    account_id: account.id,
    external_order_id: id,
    event_id: `${id}-${type}-${version}`,
    event_type: type,
    event_version: version,
    lines:
      type === 'new_order'
        ? [{ external_sku: product.sku, quantity: 2, unit_price: '100.125' }]
        : [],
  });
  const order = await api('post', 'orders/fake/events', event('QA-WP5-ORDER'));
  const cancelled = await api('post', 'orders/fake/events', event('QA-WP5-CANCEL'));
  await api('post', 'orders/fake/events', event('QA-WP5-CANCEL', 'cancel', 2));
  const financial = (key, type, amount) => ({
    account_id: account.id,
    product_id: product.id,
    order_id: order.id,
    marketplace: 'flipkart',
    source_event_id: key,
    event_type: type,
    amount,
    effective_at: '2026-10-01T12:00:00Z',
    source_type: 'synthetic_fixture',
    evidence_status: 'reported',
  });
  await api('post', 'financial/events', financial('wp5-sale', 'sale', '200.25'));
  await api('post', 'financial/events', financial('wp5-fee', 'fee', '20.05'));
  const empty = await api('post', 'products', {
    brand_id: brand.id,
    name: '[QA SYNTHETIC] WP5 Zero stock',
    sku: 'QA-WP5-ZERO',
    product_type: 'physical',
  });
  const zero = await api('post', 'inventory/items', {
    product_id: empty.id,
    internal_sku: empty.sku,
    opening_quantity: 0,
    low_stock_threshold: 2,
    idempotency_key: 'wp5-zero',
  });
  await api('post', 'financial/calculations/recalculate', {});
  await api('post', 'operations/action-center/scan', {});
  return { product, item, account, order, cancelled, zero, event, financial };
}
