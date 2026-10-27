import { ApiError } from '../api/client';
import { guessBaseCurrency } from '../hooks/useFlow';
import { friendlyError } from './errors';
import { validateFile } from './files';
import {
  formatBytes,
  formatMoney,
  formatPercent,
  formatSignedMoney,
  formatSignedPercent,
  observationsToYears,
} from './format';
import { cellStyle, contrastRatio } from './heatmap';
import { benchmarkName, metricLabel } from './labels';
import { plainText } from './text';

describe('format', () => {
  it('formats money in the base currency locale', () => {
    expect(formatMoney(4538931, 'INR')).toBe('₹45,38,931');
    expect(formatMoney(1234567, 'USD')).toBe('$1,234,567');
  });

  it('formats percentages and signs', () => {
    expect(formatPercent(0.15414)).toBe('15.41%');
    expect(formatPercent(0.15414, 1)).toBe('15.4%');
    expect(formatPercent(null)).toBe('n/a');
    expect(formatSignedPercent(0.5)).toBe('+50.00%');
    expect(formatSignedPercent(-0.0197)).toBe('−1.97%');
    expect(formatSignedPercent(0)).toBe('0.00%');
    expect(formatSignedMoney(-50000, 'INR')).toBe('−₹50,000');
    expect(formatSignedMoney(5, 'USD')).toBe('+$5');
  });

  it('formats sizes and windows', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2.0 KB');
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB');
    expect(observationsToYears(504, 252)).toBe('2.0 years');
    expect(observationsToYears(120, 252)).toBe('6 months');
  });
});

describe('validateFile', () => {
  const file = (name: string, size = 10) => {
    const f = new File(['x'], name);
    Object.defineProperty(f, 'size', { value: size });
    return f;
  };

  it('accepts csv, xlsx and json in any case', () => {
    for (const name of ['a.csv', 'a.XLSX', 'a.Json']) expect(validateFile(file(name))).toBeNull();
  });

  it('rejects other types with specific advice for Excel variants', () => {
    expect(validateFile(file('a.pdf'))).toMatch(/not a supported file type/);
    expect(validateFile(file('noextension'))).toMatch(/not a supported file type/);
    expect(validateFile(file('a.xlsm'))).toMatch(/Save the file as \.xlsx/);
    expect(validateFile(file('a.xls'))).toMatch(/Save the file as \.xlsx or \.csv/);
  });

  it('rejects empty and oversized files', () => {
    expect(validateFile(file('a.csv', 0))).toMatch(/is empty/);
    expect(validateFile(file('a.csv', 5 * 1024 * 1024))).toBeNull();
    expect(validateFile(file('a.csv', 5 * 1024 * 1024 + 1))).toMatch(/limit is 5\.0 MB/);
  });
});

describe('friendlyError', () => {
  it('never exposes status codes or error slugs', () => {
    const cases: ApiError[] = [
      new ApiError(0, 'network_error', 'x'),
      new ApiError(415, 'unsupported_media_type', 'Unsupported file type. Save as .xlsx.'),
      new ApiError(413, 'payload_too_large', 'File is larger than 5 MB.'),
      new ApiError(429, 'rate_limited', 'x', 30),
      new ApiError(503, 'ai_unavailable', 'x'),
      new ApiError(502, 'ai_error', 'x'),
      new ApiError(422, 'validation_error', 'holdings: List should have at least 1 item'),
      new ApiError(502, 'bad_gateway', 'No price data.'),
      new ApiError(500, 'internal_error', 'Internal server error.'),
    ];
    for (const error of cases) {
      const { title, message } = friendlyError(error);
      expect(`${title} ${message}`).not.toMatch(
        /\b(0|413|415|422|429|500|502|503)\b|_error|rate_limited/,
      );
    }
  });

  it('marks only transient failures as retryable', () => {
    expect(friendlyError(new ApiError(0, 'network_error', 'x')).retryable).toBe(true);
    expect(friendlyError(new ApiError(502, 'bad_gateway', 'x')).retryable).toBe(true);
    expect(friendlyError(new ApiError(422, 'validation_error', 'x')).retryable).toBe(false);
    expect(friendlyError(new ApiError(415, 'unsupported_media_type', 'x')).retryable).toBe(false);
  });

  it('handles errors that are not ApiErrors', () => {
    expect(friendlyError(new Error('boom')).message).toMatch(/unexpected error/);
    expect(friendlyError('nope').title).toBe('Something went wrong');
  });
});

describe('labels and helpers', () => {
  it('names metrics and benchmarks readably', () => {
    expect(metricLabel('risk.volatility')).toBe('volatility');
    expect(metricLabel('weight.TCS')).toBe('TCS weight');
    expect(metricLabel('sector.Financial Services')).toBe('Financial Services sector');
    expect(metricLabel('mystery.key')).toBe('mystery.key');
    expect(benchmarkName('^GSPC')).toBe('S&P 500');
    expect(benchmarkName('^XYZ')).toBe('^XYZ');
  });

  it('guesses the base currency from the holdings', () => {
    expect(guessBaseCurrency([{ symbol: 'A', quantity: 1 }])).toBe('INR');
    expect(
      guessBaseCurrency([
        { symbol: 'A', quantity: 1, exchange: 'NASDAQ' },
        { symbol: 'B', quantity: 1, currency: 'usd' },
        { symbol: 'C', quantity: 1, exchange: 'NSE' },
      ]),
    ).toBe('USD');
  });

  it('colours heatmap cells from white at 0 to saturated at +/-1', () => {
    expect(cellStyle(0).background).toBe('rgb(255, 255, 255)');
    expect(cellStyle(1).background).toBe('rgb(37, 99, 235)');
    expect(cellStyle(-1).background).toBe('rgb(234, 88, 12)');
  });

  it('always picks a text colour with at least 4.5:1 contrast on every cell', () => {
    const parse = (css: string): [number, number, number] => {
      const [r = 0, g = 0, b = 0] = (css.match(/\d+/g) ?? []).map(Number);
      return [r, g, b];
    };
    for (let v = -1; v <= 1.0001; v += 0.01) {
      const { background, color } = cellStyle(v);
      expect(
        contrastRatio(parse(background), parse(color)),
        `value ${v.toFixed(2)}`,
      ).toBeGreaterThanOrEqual(4.5);
    }
  });
});

describe('plainText', () => {
  it('removes markdown emphasis and normalises bullets', () => {
    expect(plainText('Your biggest holding is **AAPL**, at **21.6%**.')).toBe(
      'Your biggest holding is AAPL, at 21.6%.',
    );
    expect(plainText('* one\n- two\n`code` and __bold__')).toBe(
      '\u2022 one\n\u2022 two\ncode and bold',
    );
    expect(plainText('## Heading')).toBe('Heading');
    expect(plainText('No markdown here.')).toBe('No markdown here.');
  });
});
