const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatCurrency(value: number): string {
  return currency.format(value);
}

export function formatShares(value: number): string {
  // Whole lots read better without trailing zeros; fractional lots keep enough
  // precision for the DRIP-style holdings people actually enter.
  return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/0+$/, "");
}

export function formatSignedCurrency(value: number): string {
  const formatted = formatCurrency(Math.abs(value));
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `-${formatted}`;
  return formatted;
}
