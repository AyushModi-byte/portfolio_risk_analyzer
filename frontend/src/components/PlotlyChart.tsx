import type { Data, Layout } from 'plotly.js';
import Plotly from 'plotly.js-basic-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';

// The basic bundle covers bar and scatter charts, which is all the dashboard needs.
const Plot = createPlotlyComponent(Plotly);

interface PlotlyChartProps {
  data: Data[];
  layout: Partial<Layout>;
}

export default function PlotlyChart({ data, layout }: PlotlyChartProps) {
  return (
    <Plot
      data={data}
      layout={layout}
      config={{ displayModeBar: false, responsive: true }}
      useResizeHandler
      style={{ width: '100%', height: '100%' }}
    />
  );
}
