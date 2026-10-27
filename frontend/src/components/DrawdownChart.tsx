import type { DrawdownPoint } from '../api/types';
import { formatPercent } from '../lib/format';
import { Chart } from './Chart';

export function DrawdownChart({ series }: { series: DrawdownPoint[] }) {
  const worst = series.reduce<DrawdownPoint | null>(
    (min, p) => (min === null || p.drawdown < min.drawdown ? p : min),
    null,
  );
  const label = worst
    ? `Area chart of drawdown over time. The deepest fall was ${formatPercent(worst.drawdown, 1)} on ${worst.date}.`
    : 'Area chart of drawdown over time.';

  return (
    <section className="card" aria-labelledby="drawdown-heading">
      <h2 id="drawdown-heading">Drawdown</h2>
      <p className="muted">How far the portfolio sat below its previous high on each day.</p>
      <Chart
        label={label}
        height={280}
        build={(theme) => ({
          data: [
            {
              type: 'scatter',
              mode: 'lines',
              x: series.map((p) => p.date),
              y: series.map((p) => p.drawdown * 100),
              fill: 'tozeroy',
              fillcolor: `${theme.danger}33`,
              line: { color: theme.danger, width: 1.5 },
              hovertemplate: '%{x|%d %b %Y}: %{y:.2f}%<extra></extra>',
            },
          ],
          layout: {
            yaxis: { ticksuffix: '%', gridcolor: theme.grid, zeroline: false },
            xaxis: { gridcolor: theme.grid, type: 'date' },
          },
        })}
      />
    </section>
  );
}
