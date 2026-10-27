import type { SectorExposure } from '../api/types';
import { formatPercent } from '../lib/format';
import { Chart } from './Chart';

export function SectorChart({ sectors }: { sectors: SectorExposure[] }) {
  const ordered = [...sectors].sort((a, b) => b.weight - a.weight);
  const top = ordered[0];
  const label = top
    ? `Bar chart of sector exposure. The largest sector is ${top.sector} at ${formatPercent(top.weight, 1)}.`
    : 'Bar chart of sector exposure.';

  return (
    <section className="card" aria-labelledby="sector-heading">
      <h2 id="sector-heading">Sector exposure</h2>
      <Chart
        label={label}
        height={Math.max(180, ordered.length * 34 + 40)}
        build={(theme) => {
          const reversed = [...ordered].reverse(); // Plotly draws the first bar at the bottom
          return {
            data: [
              {
                type: 'bar',
                orientation: 'h',
                x: reversed.map((s) => s.weight * 100),
                y: reversed.map((s) => s.sector),
                text: reversed.map((s) => formatPercent(s.weight, 1)),
                textposition: 'outside',
                cliponaxis: false,
                marker: { color: theme.accent },
                hovertemplate: '%{y}: %{x:.2f}%<extra></extra>',
              },
            ],
            layout: {
              margin: { l: 150, r: 56, t: 8, b: 32 },
              xaxis: { ticksuffix: '%', gridcolor: theme.grid, rangemode: 'tozero' },
              yaxis: { automargin: true },
            },
          };
        }}
      />
      <details className="data-details">
        <summary>View as table</summary>
        <table className="data-table">
          <caption className="visually-hidden">Sector exposure</caption>
          <thead>
            <tr>
              <th scope="col">Sector</th>
              <th scope="col" className="num">
                Weight
              </th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((s) => (
              <tr key={s.sector}>
                <th scope="row">{s.sector}</th>
                <td className="num">{formatPercent(s.weight)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}
