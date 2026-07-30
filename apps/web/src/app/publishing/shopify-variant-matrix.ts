import type { ShopifyVariantInput } from '@vayujit/shared';

export interface ShopifyOptionDefinition {
  name: string;
  values: string[];
}

export interface VariantMatrixResult {
  variants: ShopifyVariantInput[];
  removedKeys: string[];
  count: number;
  errors: string[];
}

export const SHOPIFY_MAX_OPTIONS = 3;
export const SHOPIFY_MAX_VARIANTS = 100;

function normalized(value: string): string {
  return value.trim().toLocaleLowerCase();
}

export function variantStableKey(options: { name: string; value: string }[]): string {
  return options
    .map(({ name, value }) => `${normalized(name)}=${normalized(value)}`)
    .join('|')
    .replace(/[^a-z0-9=|._-]+/g, '-')
    .slice(0, 100);
}

export function validateOptionDefinitions(options: ShopifyOptionDefinition[]): string[] {
  const errors: string[] = [];
  if (!options.length || options.length > SHOPIFY_MAX_OPTIONS)
    errors.push('Use between one and three options.');
  const names = options.map((option) => normalized(option.name));
  if (names.some((name) => !name)) errors.push('Option names cannot be blank.');
  if (new Set(names).size !== names.length) errors.push('Option names must be unique.');
  options.forEach((option, index) => {
    const values = option.values.map(normalized);
    if (!values.length || values.some((value) => !value))
      errors.push(`Option ${index + 1} values cannot be blank.`);
    if (new Set(values).size !== values.length)
      errors.push(`Option ${index + 1} values must be unique.`);
  });
  return errors;
}

export function generateVariantMatrix(
  definitions: ShopifyOptionDefinition[],
  existing: ShopifyVariantInput[],
  defaultPrice: string | null,
): VariantMatrixResult {
  const errors = validateOptionDefinitions(definitions);
  const count = definitions.reduce((total, option) => total * option.values.length, 1);
  if (count > SHOPIFY_MAX_VARIANTS)
    errors.push(`The matrix would create ${count} variants; Shopify allows at most 100.`);
  if (errors.length) return { variants: existing, removedKeys: [], count, errors };
  const combinations = definitions.reduce<{ name: string; value: string }[][]>(
    (rows, definition) =>
      rows.flatMap((row) =>
        definition.values.map((value) => [...row, { name: definition.name.trim(), value }]),
      ),
    [[]],
  );
  const previous = new Map(existing.map((variant) => [variantStableKey(variant.options), variant]));
  const variants = combinations.map((options) => {
    const key = variantStableKey(options);
    const matched = previous.get(key);
    return matched
      ? { ...matched, local_key: matched.local_key || key, options }
      : {
          local_key: key,
          options,
          sku: null,
          price: defaultPrice,
          compare_at_price: null,
          barcode: null,
          weight: null,
          weight_unit: null,
          taxable: true,
          track_inventory: false,
        };
  });
  const retained = new Set(variants.map((variant) => variantStableKey(variant.options)));
  return {
    variants,
    removedKeys: existing
      .filter((variant) => !retained.has(variantStableKey(variant.options)))
      .map((variant) => variant.local_key),
    count,
    errors: [],
  };
}
