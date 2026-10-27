// Blue for positive, orange for negative: distinguishable without relying on red versus green.
const POSITIVE: [number, number, number] = [37, 99, 235];
const NEGATIVE: [number, number, number] = [234, 88, 12];
// Pure black (not slate): with white as the alternative, some colour always reaches 4.5:1.
const DARK_TEXT: [number, number, number] = [0, 0, 0];
const LIGHT_TEXT: [number, number, number] = [255, 255, 255];

type Rgb = [number, number, number];

function luminance([r, g, b]: Rgb): number {
  const channel = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** WCAG contrast ratio between two colours. */
export function contrastRatio(a: Rgb, b: Rgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05);
}

/**
 * Cell colour for a correlation in [-1, 1]: white at 0, saturated at ±1. The text colour is
 * whichever of dark or white has the higher contrast, so mid-range cells stay readable.
 */
export function cellStyle(value: number): { background: string; color: string } {
  const strength = Math.min(1, Math.abs(value));
  const target = value >= 0 ? POSITIVE : NEGATIVE;
  const bg = target.map((c) => Math.round(255 + (c - 255) * strength)) as Rgb;
  const text =
    contrastRatio(bg, DARK_TEXT) >= contrastRatio(bg, LIGHT_TEXT) ? DARK_TEXT : LIGHT_TEXT;
  return { background: `rgb(${bg.join(', ')})`, color: `rgb(${text.join(', ')})` };
}
