import type { CorrelationMatrix, WeightItem } from '../api/types';
import { cellStyle } from '../lib/heatmap';

const MAX_SYMBOLS = 20;
interface HeatmapProps {
  correlation: CorrelationMatrix;
  weights: WeightItem[];
}

export function CorrelationHeatmap({ correlation, weights }: HeatmapProps) {
  const weightOf = new Map(weights.map((w) => [w.symbol, w.weight]));
  const indices = correlation.symbols
    .map((symbol, index) => ({ symbol, index }))
    .sort((a, b) => (weightOf.get(b.symbol) ?? 0) - (weightOf.get(a.symbol) ?? 0))
    .slice(0, MAX_SYMBOLS);
  const trimmed = correlation.symbols.length > indices.length;

  return (
    <section className="card" aria-labelledby="corr-heading">
      <h2 id="corr-heading">Correlation</h2>
      <p className="muted">
        How closely holdings move together, from −1 (opposite) to +1 (in step). Holdings that are
        highly correlated give less diversification.
        {trimmed && ` Showing the ${MAX_SYMBOLS} largest holdings.`}
      </p>
      {indices.length < 2 ? (
        <p>At least two holdings are needed to show correlations.</p>
      ) : (
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Correlation heatmap">
          <table className="heatmap">
            <caption className="visually-hidden">
              Correlation between holdings’ daily returns
            </caption>
            <thead>
              <tr>
                <td />
                {indices.map(({ symbol }) => (
                  <th key={symbol} scope="col" className="heatmap-col">
                    <span>{symbol}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {indices.map(({ symbol, index: row }) => (
                <tr key={symbol}>
                  <th scope="row">{symbol}</th>
                  {indices.map(({ symbol: other, index: col }) => {
                    const value = correlation.values[row]?.[col] ?? 0;
                    return (
                      <td
                        key={other}
                        style={cellStyle(value)}
                        title={`${symbol} and ${other}: ${value.toFixed(2)}`}
                      >
                        {value.toFixed(2)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
