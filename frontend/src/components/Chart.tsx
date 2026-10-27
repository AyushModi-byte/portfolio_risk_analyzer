import type { Data, Layout } from 'plotly.js';
import { lazy, Suspense } from 'react';
import { useColorScheme } from '../hooks/useColorScheme';
import { THEMES, type ChartTheme } from '../lib/chartTheme';
import { Skeleton } from './Feedback';

// Plotly is large, so it loads on demand and the upload screen stays fast.
const PlotlyChart = lazy(() => import('./PlotlyChart'));

interface ChartProps {
  /** Builds the traces for the current colour theme. */
  build: (theme: ChartTheme) => { data: Data[]; layout?: Partial<Layout> };
  height: number;
  /** A text description for screen readers, since the chart itself is a picture. */
  label: string;
}

export function Chart({ build, height, label }: ChartProps) {
  const theme = THEMES[useColorScheme()];
  const { data, layout } = build(theme);
  const base: Partial<Layout> = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: theme.text, family: 'system-ui, sans-serif', size: 13 },
    margin: { l: 48, r: 24, t: 12, b: 40 },
    autosize: true,
    xaxis: { gridcolor: theme.grid, zerolinecolor: theme.grid },
    yaxis: { gridcolor: theme.grid, zerolinecolor: theme.grid },
  };
  return (
    <div className="chart" role="img" aria-label={label} style={{ height }}>
      <Suspense fallback={<Skeleton className="chart-skeleton" />}>
        <PlotlyChart data={data} layout={{ ...base, ...layout }} />
      </Suspense>
    </div>
  );
}
