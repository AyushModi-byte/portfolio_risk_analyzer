import type { InsightsState } from '../hooks/useFlow';
import { metricLabel } from '../lib/labels';
import { Skeleton } from './Feedback';

interface InsightsPanelProps {
  state: InsightsState;
  onRetry: () => void;
}

export function InsightsPanel({ state, onRetry }: InsightsPanelProps) {
  return (
    <section
      className="card"
      aria-labelledby="insights-heading"
      aria-busy={state.status === 'loading'}
    >
      <h2 id="insights-heading">Insights</h2>

      {(state.status === 'idle' || state.status === 'loading') && (
        <div role="status">
          <span className="visually-hidden">Writing insights…</span>
          <Skeleton className="line" />
          <Skeleton className="line" />
          <Skeleton className="line short" />
        </div>
      )}

      {state.status === 'error' && (
        <div role="alert">
          <p>{state.error.message}</p>
          <button type="button" className="btn btn-small" onClick={onRetry}>
            Try again
          </button>
        </div>
      )}

      {state.status === 'ready' && (
        <>
          <p className="badge-row">
            {state.result.source === 'llm' ? (
              <span className="badge badge-ai">
                AI-written · every number checked against your analysis
              </span>
            ) : (
              <span className="badge">Generated from your numbers</span>
            )}
          </p>
          {state.result.note && <p className="muted">{state.result.note}</p>}
          <ul className="insight-list">
            {state.result.insights.map((insight) => (
              <li key={insight.text}>
                <p>{insight.text}</p>
                <p className="insight-basis">
                  Based on: {insight.metric_keys.map(metricLabel).join(', ')}
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
