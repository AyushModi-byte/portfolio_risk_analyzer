import type {
  AnalysisResult,
  ChatResult,
  Health,
  InsightsResult,
  ParseResponse,
  SampleInfo,
} from '../api/types';

export const health: Health = {
  status: 'ok',
  version: '0.1.0',
  git_sha: 'abc',
  ai_available: true,
};

export const analysis: AnalysisResult = {
  summary: {
    value: 4538931,
    invested: 2535556,
    pnl: 2003375,
    pnl_pct: 0.79011,
    base_currency: 'INR',
  },
  weights: [
    { symbol: 'AAPL', weight: 0.4, market_value: 1815572, volatility: 0.25 },
    { symbol: 'TCS', weight: 0.3, market_value: 1361679, volatility: 0.21 },
    { symbol: 'ITC', weight: 0.2, market_value: 907786, volatility: 0.18 },
    { symbol: 'LT', weight: 0.1, market_value: 453893, volatility: null },
  ],
  sector_exposure: [
    { sector: 'Technology', weight: 0.7 },
    { sector: 'Consumer Defensive', weight: 0.2 },
    { sector: 'Industrials', weight: 0.1 },
  ],
  risk: {
    volatility: 0.15414,
    beta: 0.7463,
    sharpe: 1.0059,
    var_95: 0.01334,
    max_drawdown: -0.18116,
    risk_free_rate: 0.07,
    benchmark: '^NSEI',
    trading_days: 252,
    observations: 517,
    hhi: 0.3,
    effective_n: 3.33,
    top5_concentration: 1,
  },
  drawdown_series: [
    { date: '2024-01-01', drawdown: 0 },
    { date: '2024-01-02', drawdown: -0.05 },
    { date: '2024-01-03', drawdown: -0.18116 },
    { date: '2024-01-04', drawdown: -0.1 },
    { date: '2024-01-05', drawdown: 0 },
  ],
  correlation: {
    symbols: ['AAPL', 'TCS', 'ITC', 'LT'],
    values: [
      [1, 0.8, -0.2, 0.1],
      [0.8, 1, 0.0, 0.3],
      [-0.2, 0.0, 1, 0.5],
      [0.1, 0.3, 0.5, 1],
    ],
  },
  warnings: ['Live prices unavailable; using the bundled price snapshot for: AAPL'],
  disclaimer: 'Analytics only, not financial advice.',
};

export const sampleInfo: SampleInfo = {
  name: 'india',
  base_currency: 'INR',
  benchmark: '^NSEI',
  holdings: [
    { symbol: 'TCS', quantity: 10, avg_buy_price: 3000 },
    { symbol: 'ITC', quantity: 100, avg_buy_price: 400 },
  ],
};

export const samples: SampleInfo[] = [
  sampleInfo,
  { ...sampleInfo, name: 'us', base_currency: 'USD', benchmark: '^GSPC' },
  { ...sampleInfo, name: 'mixed' },
];

export const parseOk: ParseResponse = {
  status: 'ok',
  broker: 'Zerodha',
  holdings: [
    { symbol: 'TCS', quantity: 10, avg_buy_price: 3000 },
    { symbol: 'ITC', quantity: 100, avg_buy_price: 400 },
  ],
  columns: [],
  detected: {},
  missing: [],
  sample_rows: [],
  warnings: [],
  unresolved_symbols: [],
};

export const parseNeedsMapping: ParseResponse = {
  status: 'needs_mapping',
  broker: null,
  holdings: [],
  columns: ['Scrip Name', 'Holding Qty', 'Cost', 'Notes'],
  detected: { avg_buy_price: 'Cost' },
  missing: ['symbol', 'quantity'],
  sample_rows: [{ 'Scrip Name': 'TCS', 'Holding Qty': '10', Cost: '3000', Notes: 'x' }],
  warnings: ['Could not detect all required columns; please map them.'],
  unresolved_symbols: [],
};

export const insightsLlm: InsightsResult = {
  insights: [
    {
      text: 'The largest holding is AAPL at 40.00% of the portfolio.',
      metric_keys: ['weight.AAPL', 'param.top_n'],
    },
    { text: 'Annualized volatility is 15.41%.', metric_keys: ['risk.volatility'] },
  ],
  source: 'llm',
  attempts: 1,
  note: null,
  disclaimer: 'Analytics only, not financial advice.',
};

export const insightsTemplate: InsightsResult = {
  ...insightsLlm,
  source: 'template',
  note: 'AI unavailable; showing template insights.',
};

export const chatResult: ChatResult = {
  answer: 'Your biggest holding is AAPL, which represents 40% of your portfolio.',
  tool_calls: [
    {
      name: 'get_top_holdings',
      args: { n: 1 },
      output: { n: 1, holdings: [{ symbol: 'AAPL', weight_percent: 40 }] },
    },
  ],
  verified: true,
  note: null,
  disclaimer: 'Analytics only, not financial advice.',
};
