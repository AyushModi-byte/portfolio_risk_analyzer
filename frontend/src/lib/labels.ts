import type { ColumnField } from '../api/types';

export const BENCHMARKS = [
  { value: '', label: 'Automatic' },
  { value: '^NSEI', label: 'Nifty 50' },
  { value: '^GSPC', label: 'S&P 500' },
] as const;

const BENCHMARK_NAMES: Record<string, string> = {
  '^NSEI': 'Nifty 50',
  '^GSPC': 'S&P 500',
  '^BSESN': 'Sensex',
  '^IXIC': 'Nasdaq Composite',
};

export function benchmarkName(symbol: string): string {
  return BENCHMARK_NAMES[symbol] ?? symbol;
}

export const FIELD_LABELS: Record<ColumnField, string> = {
  symbol: 'Symbol',
  quantity: 'Quantity',
  avg_buy_price: 'Average price',
  name: 'Name',
  exchange: 'Exchange',
  currency: 'Currency',
};

const METRIC_LABELS: Record<string, string> = {
  'summary.value': 'portfolio value',
  'summary.invested': 'amount invested',
  'summary.pnl': 'profit and loss',
  'summary.pnl_pct': 'return',
  'risk.volatility': 'volatility',
  'risk.beta': 'beta',
  'risk.sharpe': 'Sharpe ratio',
  'risk.var_95': 'value at risk',
  'risk.max_drawdown': 'max drawdown',
  'risk.risk_free_rate': 'risk-free rate',
  'risk.hhi': 'concentration index',
  'risk.effective_n': 'effective holdings',
  'risk.top5_concentration': 'top 5 weight',
  'risk.observations': 'trading days',
  'risk.trading_days': 'trading days',
  'param.var_confidence': 'confidence level',
  'param.top_n': 'top 5',
  'count.holdings': 'holding count',
  'count.sectors': 'sector count',
  'rank.1.weight': 'largest holding',
  'sector_rank.1.weight': 'largest sector',
};

/** A readable name for a metric key such as `risk.volatility` or `weight.TCS`. */
export function metricLabel(key: string): string {
  const known = METRIC_LABELS[key];
  if (known) return known;
  const [group, ...rest] = key.split('.');
  const name = rest.join('.');
  if (group === 'weight') return `${name} weight`;
  if (group === 'sector') return `${name} sector`;
  if (group === 'volatility') return `${name} volatility`;
  return key;
}

export const RISK_HELP = {
  volatility:
    'How much the portfolio value typically swings, per year. Higher means a bumpier ride. About two thirds of years should land within this much of the average.',
  beta: 'How strongly the portfolio moves with its benchmark. 1 moves in step, above 1 swings more than the market, below 1 swings less.',
  sharpe:
    'Return earned above a risk-free rate for each unit of volatility. Higher is better; below 0 means it earned less than the risk-free rate.',
  var95:
    'A rough one-day loss size. On 95 out of 100 past days the portfolio lost less than this; on the worst 5 it lost at least this much.',
  maxDrawdown:
    'The biggest peak-to-trough fall in the period, before any recovery. It shows how painful the worst stretch was.',
} as const;
