import { Pipe, PipeTransform } from '@angular/core';

// Presentation only: exact decimal strings stay unchanged in canonical records.
// Round half away from zero to two display places without a binary float roundtrip.
export function displayDecimal(value: unknown, ratio = false): string {
  if (typeof value !== 'string' && typeof value !== 'number') return 'UNKNOWN';
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(String(value));
  if (!match || String(value).length > 120) return 'UNKNOWN';
  const fraction = match[3] || '';
  const places = ratio ? 4 : 2;
  const digits = fraction.padEnd(places + 1, '0');
  let scaled = BigInt(match[2]) * 10n ** BigInt(places) + BigInt(digits.slice(0, places));
  if (digits[places] >= '5') scaled += 1n;
  const whole = scaled / 100n;
  const decimal = String(scaled % 100n).padStart(2, '0');
  const sign = match[1] && scaled !== 0n ? '-' : '';
  return `${sign}${new Intl.NumberFormat('en-IN').format(whole)}.${decimal}${ratio ? '%' : ''}`;
}

@Pipe({ name: 'sellerMoney', standalone: true })
export class SellerMoneyPipe implements PipeTransform {
  transform(value: unknown, currency: unknown): string {
    const amount = displayDecimal(value);
    if (amount === 'UNKNOWN') return amount;
    const code = typeof currency === 'string' && /^[A-Z]{3}$/.test(currency) ? currency : null;
    return `${code === 'INR' ? '₹' : code ? code + ' ' : 'Currency UNKNOWN · '}${amount}`;
  }
}

@Pipe({ name: 'sellerPercent', standalone: true })
export class SellerPercentPipe implements PipeTransform {
  transform(value: unknown): string {
    return displayDecimal(value, true);
  }
}

@Pipe({ name: 'sellerComponentMoney', standalone: true })
export class SellerComponentMoneyPipe implements PipeTransform {
  transform(
    line: {
      per_unit_amount?: string | number | null;
      amount?: string | number | null;
      currency?: string | null;
    },
    baseCurrency: unknown,
  ): string {
    // Canonical per_unit_amount is already FX-converted by the backend. Its
    // currency is the model base currency, not the original component currency.
    return new SellerMoneyPipe().transform(
      line.per_unit_amount ?? line.amount,
      line.per_unit_amount != null ? baseCurrency : line.currency,
    );
  }
}
