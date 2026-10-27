import '@testing-library/jest-dom/vitest';
import { createElement } from 'react';
import { vi } from 'vitest';

// jsdom cannot run Plotly (no canvas or WebGL), so charts are replaced by a stand-in that exposes
// the traces it was given.
vi.mock('../components/PlotlyChart', () => ({
  default: ({ data }: { data: unknown }) =>
    createElement('div', { 'data-testid': 'plot', 'data-traces': JSON.stringify(data) }),
}));
