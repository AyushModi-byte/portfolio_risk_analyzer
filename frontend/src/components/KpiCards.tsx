import type { Summary } from '../api/types';
import { formatMoney, formatSignedMoney, formatSignedPercent } from '../lib/format';

function direction(value: number | null): 'up' | 'down' | 'flat' {
  if (value === null || value === 0) return 'flat';
  return value > 0 ? 'up' : 'down';
}

const ARROWS = { up: '▲', down: '▼', flat: '' } as const;

export function KpiCards({ summary }: { summary: Summary }) {
  const { base_currency: cur } = summary;
  const pnlDir = direction(summary.invested > 0 ? summary.pnl : null);
  const pctDir = direction(summary.pnl_pct);
  const hasCost = summary.invested > 0;

  return (
    <section aria-label="Portfolio summary">
      <dl className="kpi-grid">
        <div className="kpi">
          <dt>Current value</dt>
          <dd>{formatMoney(summary.value, cur)}</dd>
        </div>
        <div className="kpi">
          <dt>Invested</dt>
          <dd>{hasCost ? formatMoney(summary.invested, cur) : 'n/a'}</dd>
        </div>
        <div className={`kpi kpi-${pnlDir}`}>
          <dt>Profit and loss</dt>
          <dd>
            {hasCost ? (
              <>
                <span aria-hidden="true">{ARROWS[pnlDir]} </span>
                {formatSignedMoney(summary.pnl, cur)}
              </>
            ) : (
              'n/a'
            )}
          </dd>
        </div>
        <div className={`kpi kpi-${pctDir}`}>
          <dt>Return</dt>
          <dd>
            <span aria-hidden="true">{ARROWS[pctDir]} </span>
            {formatSignedPercent(summary.pnl_pct)}
          </dd>
        </div>
      </dl>
      {!hasCost && (
        <p className="muted">
          Profit and loss needs an average price for each holding, which this file did not include.
        </p>
      )}
    </section>
  );
}
