import {
  displayDecimal,
  SellerMoneyPipe,
  SellerPercentPipe,
  SellerComponentMoneyPipe,
} from './seller-financial-format';

describe('Seller financial presentation (not calculation)', () => {
  it.each([
    [null, 'UNKNOWN'],
    [undefined, 'UNKNOWN'],
    ['', 'UNKNOWN'],
    ['UNKNOWN', 'UNKNOWN'],
    [0, '0.00'],
    ['0.00000000', '0.00'],
    ['100.12500000', '100.13'],
    ['-100.125', '-100.13'],
    ['300000.00000000', '3,00,000.00'],
    ['999.999', '1,000.00'],
    ['9007199254740993123.455', '90,07,19,92,54,74,09,93,123.46'],
    [NaN, 'UNKNOWN'],
    [Infinity, 'UNKNOWN'],
    ['1e3', 'UNKNOWN'],
    [{}, 'UNKNOWN'],
  ])('formats %s as %s without changing source values', (value, expected) => {
    expect(displayDecimal(value)).toBe(expected);
  });
  it('converts canonical margin ratios to percentages, including zero and negatives', () => {
    const pipe = new SellerPercentPipe();
    expect(pipe.transform('0.47910000')).toBe('47.91%');
    expect(pipe.transform('-0.00125')).toBe('-0.13%');
    expect(pipe.transform('0')).toBe('0.00%');
    expect(pipe.transform(null)).toBe('UNKNOWN');
  });
  it('requires an explicit currency and never silently substitutes INR', () => {
    const pipe = new SellerMoneyPipe();
    expect(pipe.transform('300000', 'INR')).toBe('₹3,00,000.00');
    expect(pipe.transform('0', 'USD')).toBe('USD 0.00');
    expect(pipe.transform('12', null)).toBe('Currency UNKNOWN · 12.00');
    expect(pipe.transform(null, 'INR')).toBe('UNKNOWN');
  });
  it('labels backend-converted per-unit costs in base currency, retaining original unknown/excluded amounts', () => {
    const pipe = new SellerComponentMoneyPipe();
    expect(pipe.transform({ per_unit_amount: '83.125', amount: '1', currency: 'USD' }, 'INR')).toBe(
      '₹83.13',
    );
    expect(pipe.transform({ per_unit_amount: null, amount: '1', currency: 'USD' }, 'INR')).toBe(
      'USD 1.00',
    );
    expect(pipe.transform({ per_unit_amount: '0', amount: '1', currency: 'USD' }, null)).toBe(
      'Currency UNKNOWN · 0.00',
    );
    expect(pipe.transform({ per_unit_amount: null, amount: null, currency: 'USD' }, 'INR')).toBe(
      'UNKNOWN',
    );
  });
});
