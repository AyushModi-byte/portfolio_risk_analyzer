// Shapes returned by the FastAPI backend (see docs/ARCHITECTURE.md and backend/app/schemas.py).

export type Currency = 'INR' | 'USD';

export interface Holding {
  symbol: string;
  name?: string | null;
  quantity: number;
  avg_buy_price?: number | null;
  currency?: string | null;
  exchange?: string | null;
}

export interface Health {
  status: string;
  version: string;
  git_sha: string;
  ai_available: boolean;
}

export interface SampleInfo {
  name: string;
  base_currency: Currency;
  benchmark: string;
  holdings: Holding[];
}

export type ColumnField =
  'symbol' | 'quantity' | 'avg_buy_price' | 'name' | 'exchange' | 'currency';
export type ColumnMapping = Partial<Record<ColumnField, string>>;

export interface ParseResponse {
  status: 'ok' | 'needs_mapping';
  broker: string | null;
  holdings: Holding[];
  columns: string[];
  detected: ColumnMapping;
  missing: string[];
  sample_rows: Record<string, string>[];
  warnings: string[];
  unresolved_symbols: string[];
}

export interface AnalyzeRequest {
  holdings: Holding[];
  base_currency: Currency;
  benchmark?: string | null;
  lookback_years?: number;
}

export interface Summary {
  value: number;
  invested: number;
  pnl: number;
  pnl_pct: number | null;
  base_currency: Currency;
}

export interface WeightItem {
  symbol: string;
  weight: number;
  market_value: number;
  volatility: number | null;
}

export interface SectorExposure {
  sector: string;
  weight: number;
}

export interface RiskMetrics {
  volatility: number;
  beta: number | null;
  sharpe: number | null;
  var_95: number;
  max_drawdown: number;
  risk_free_rate: number;
  benchmark: string;
  trading_days: number;
  observations: number;
  hhi: number;
  effective_n: number;
  top5_concentration: number;
}

export interface DrawdownPoint {
  date: string;
  drawdown: number;
}

export interface CorrelationMatrix {
  symbols: string[];
  values: number[][];
}

export interface AnalysisResult {
  summary: Summary;
  weights: WeightItem[];
  sector_exposure: SectorExposure[];
  risk: RiskMetrics;
  drawdown_series: DrawdownPoint[];
  correlation: CorrelationMatrix;
  warnings: string[];
  disclaimer: string;
}

export interface Insight {
  text: string;
  metric_keys: string[];
}

export interface InsightsResult {
  insights: Insight[];
  source: 'llm' | 'template';
  attempts: number;
  note: string | null;
  disclaimer: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ToolRecord {
  name: string;
  args: Record<string, unknown>;
  output: Record<string, unknown>;
}

export interface ChatResult {
  answer: string;
  tool_calls: ToolRecord[];
  verified: boolean;
  note: string | null;
  disclaimer: string;
}

export interface MappingResult {
  mapping: ColumnMapping | null;
  source: 'llm' | 'none';
  error: string | null;
}

export interface ChatRequest {
  analysis: AnalysisResult;
  messages: ChatMessage[];
  request: AnalyzeRequest | null;
}
