import {
  generateVariantMatrix,
  validateOptionDefinitions,
  variantStableKey,
} from './shopify-variant-matrix';

describe('Shopify variant matrix', () => {
  it('generates one, two, and three option matrices', () => {
    expect(generateVariantMatrix([{ name: 'Size', values: ['S', 'M'] }], [], '10').count).toBe(2);
    expect(
      generateVariantMatrix(
        [
          { name: 'Size', values: ['S', 'M'] },
          { name: 'Color', values: ['Red', 'Blue'] },
        ],
        [],
        '10',
      ).count,
    ).toBe(4);
    expect(
      generateVariantMatrix(
        [
          { name: 'Size', values: ['S', 'M'] },
          { name: 'Color', values: ['Red', 'Blue'] },
          { name: 'Material', values: ['Cotton', 'Wool'] },
        ],
        [],
        '10',
      ).count,
    ).toBe(8);
  });

  it('accepts 100 variants and rejects 101', () => {
    const hundred = Array.from({ length: 100 }, (_, index) => `${index}`);
    expect(generateVariantMatrix([{ name: 'Number', values: hundred }], [], '10').errors).toEqual(
      [],
    );
    expect(
      generateVariantMatrix(
        [{ name: 'Number', values: [...hundred, '100'] }],
        [],
        '10',
      ).errors.join(' '),
    ).toContain('at most 100');
  });

  it('preserves stable keys and entered data for equivalent combinations', () => {
    const options = [{ name: 'Size', value: 'Large' }];
    const existing = [
      {
        local_key: 'persisted-key',
        options,
        sku: 'SKU-1',
        price: '19.00',
        compare_at_price: null,
        barcode: null,
        weight: null,
        weight_unit: null,
        taxable: true,
        track_inventory: false,
      },
    ];
    const result = generateVariantMatrix([{ name: ' size ', values: [' large '] }], existing, null);
    expect(result.variants[0]?.local_key).toBe('persisted-key');
    expect(result.variants[0]?.sku).toBe('SKU-1');
    expect(variantStableKey(result.variants[0]?.options ?? [])).toBe(variantStableKey(options));
  });

  it('reports blank and duplicate option data', () => {
    expect(
      validateOptionDefinitions([
        { name: 'Size', values: ['S', 's'] },
        { name: ' size ', values: [''] },
      ]).length,
    ).toBeGreaterThan(0);
  });
});
