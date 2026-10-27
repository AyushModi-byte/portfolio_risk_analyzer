import type { AnalysisResult, AnalyzeRequest, Currency } from '../api/types';
import type { InsightsState } from '../hooks/useFlow';
import { Controls } from './Controls';
import { CorrelationHeatmap } from './CorrelationHeatmap';
import { DrawdownChart } from './DrawdownChart';
import { HoldingsTable } from './HoldingsTable';
import { InsightsPanel } from './InsightsPanel';
import { KpiCards } from './KpiCards';
import { RiskCards } from './RiskCards';
import { SectorChart } from './SectorChart';

interface DashboardProps {
  analysis: AnalysisResult;
  request: AnalyzeRequest;
  reloading: boolean;
  insights: InsightsState;
  aiAvailable: boolean;
  onChange: (change: { base_currency?: Currency; benchmark?: string | null }) => void;
  onRetryInsights: () => void;
  onOpenChat: () => void;
}

export function Dashboard(props: DashboardProps) {
  const { analysis, request, reloading, insights, aiAvailable } = props;
  return (
    <div className={`dashboard${reloading ? ' is-reloading' : ''}`} aria-busy={reloading}>
      <div className="dashboard-bar">
        <Controls
          request={request}
          usedBenchmark={analysis.risk.benchmark}
          disabled={reloading}
          onChange={props.onChange}
        />
        <div className="dashboard-bar-actions">
          {reloading && (
            <span className="muted" role="status">
              Updating…
            </span>
          )}
          <button
            type="button"
            className="btn btn-primary"
            onClick={props.onOpenChat}
            disabled={!aiAvailable}
            title={aiAvailable ? undefined : 'AI is unavailable on this server'}
          >
            {aiAvailable ? 'Ask about this portfolio' : 'AI chat unavailable'}
          </button>
        </div>
      </div>

      {analysis.warnings.length > 0 && (
        <details className="banner banner-warn">
          <summary>
            {analysis.warnings.length} note{analysis.warnings.length === 1 ? '' : 's'} about this
            analysis
          </summary>
          <ul>
            {analysis.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </details>
      )}

      <KpiCards summary={analysis.summary} />
      <RiskCards risk={analysis.risk} />
      <InsightsPanel state={insights} onRetry={props.onRetryInsights} />

      <div className="two-col">
        <HoldingsTable weights={analysis.weights} currency={analysis.summary.base_currency} />
        <SectorChart sectors={analysis.sector_exposure} />
      </div>
      <div className="two-col">
        <DrawdownChart series={analysis.drawdown_series} />
        <CorrelationHeatmap correlation={analysis.correlation} weights={analysis.weights} />
      </div>
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="dashboard" role="status" aria-label="Loading your analysis">
      <span className="visually-hidden">Analyzing your portfolio…</span>
      <div className="kpi-grid" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton skeleton-kpi" />
        ))}
      </div>
      <div className="skeleton skeleton-block" aria-hidden="true" />
      <div className="two-col" aria-hidden="true">
        <div className="skeleton skeleton-block tall" />
        <div className="skeleton skeleton-block tall" />
      </div>
    </div>
  );
}
