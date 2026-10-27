import type { Currency } from '../api/types';

const LOCALE: Record<Currency, string> = { INR: 'en-IN', USD: 'en-US' };
const MINUS = '−';

export function formatMoney(value: number, currency: Currency): string {
  return new Intl.NumberFormat(LOCALE[currency], {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPercent(fraction: number | null | undefined, digits = 2): string {
  if (fraction === null || fraction === undefined) return 'n/a';
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** Percentage with an explicit sign, so gains and losses never rely on colour alone. */
export function formatSignedPercent(fraction: number | null | undefined, digits = 2): string {
  if (fraction === null || fraction === undefined) return 'n/a';
  const text = `${(Math.abs(fraction) * 100).toFixed(digits)}%`;
  if (fraction > 0) return `+${text}`;
  return fraction < 0 ? `${MINUS}${text}` : text;
}

export function formatSignedMoney(value: number, currency: Currency): string {
  const text = formatMoney(Math.abs(value), currency);
  if (value > 0) return `+${text}`;
  return value < 0 ? `${MINUS}${text}` : text;
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? 'n/a' : value.toFixed(digits);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Years covered by a number of daily observations, for display. */
export function observationsToYears(observations: number, tradingDays: number): string {
  const years = observations / tradingDays;
  if (years < 1.5) return `${Math.max(1, Math.round(years * 12))} months`;
  return `${years.toFixed(1)} years`;
}
