import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AnalysisResult, AnalyzeRequest } from '../api/types';
import * as fx from '../test/fixtures';
import { Dashboard } from './Dashboard';

const request: AnalyzeRequest = {
  holdings: fx.parseOk.holdings,
  base_currency: 'INR',
  benchmark: null,
};

function setup(overrides: Partial<Parameters<typeof Dashboard>[0]> = {}) {
  const props = {
    analysis: fx.analysis,
    request,
    reloading: false,
    insights: { status: 'ready', result: fx.insightsLlm } as const,
    aiAvailable: true,
    onChange: vi.fn(),
    onRetryInsights: vi.fn(),
    onOpenChat: vi.fn(),
    ...overrides,
  };
  render(<Dashboard {...props} />);
  return props;
}

describe('dashboard with a mocked analysis result', () => {
  it('renders the KPI cards with currency formatting and signed P&L', () => {
    setup();
    const kpis = screen.getByRole('region', { name: 'Portfolio summary' });
    expect(within(kpis).getByText('Current value').nextElementSibling).toHaveTextContent(
      '₹45,38,931',
    );
    expect(within(kpis).getByText('Invested').nextElementSibling).toHaveTextContent('₹25,35,556');
    expect(within(kpis).getByText('Profit and loss').nextElementSibling).toHaveTextContent(
      '+₹20,03,375',
    );
    expect(within(kpis).getByText('Return').nextElementSibling).toHaveTextContent('+79.01%');
  });

  it('shows a loss with a minus sign and a down arrow, not colour alone', () => {
    const losing: AnalysisResult = {
      ...fx.analysis,
      summary: { ...fx.analysis.summary, pnl: -50000, pnl_pct: -0.0197 },
    };
    setup({ analysis: losing });
    expect(screen.getByText('Profit and loss').nextElementSibling).toHaveTextContent('▼ −₹50,000');
    expect(screen.getByText('Return').nextElementSibling).toHaveTextContent('−1.97%');
  });

  it('explains missing P&L when no average prices were supplied', () => {
    setup({
      analysis: {
        ...fx.analysis,
        summary: { ...fx.analysis.summary, invested: 0, pnl: 0, pnl_pct: null },
      },
    });
    expect(screen.getByText('Return').nextElementSibling).toHaveTextContent('n/a');
    expect(screen.getByText(/needs an average price/)).toBeInTheDocument();
  });

  it('shows each risk metric with a tooltip and the assumption note', async () => {
    const user = userEvent.setup();
    setup();
    const risk = screen.getByRole('heading', { name: 'Risk' }).closest('section') as HTMLElement;
    expect(within(risk).getByText('15.41%')).toBeInTheDocument();
    expect(within(risk).getByText('0.75')).toBeInTheDocument();
    expect(within(risk).getByText('1.01')).toBeInTheDocument();
    expect(within(risk).getByText('1.33%')).toBeInTheDocument();
    expect(within(risk).getByText('-18.12%')).toBeInTheDocument();
    expect(within(risk).getByText('vs Nifty 50')).toBeInTheDocument();
    expect(within(risk).getByRole('note')).toHaveTextContent(
      /how today’s holdings would have behaved over the past 2\.1 years.*not what you actually earned/,
    );

    const tip = within(risk).getByRole('button', { name: 'What is volatility?' });
    const bubble = within(risk).getByText(/How much the portfolio value typically swings/);
    expect(bubble).not.toBeVisible();
    await user.click(tip);
    expect(bubble).toBeVisible();
    expect(tip).toHaveAttribute('aria-describedby', bubble.id);
    await user.keyboard('{Escape}');
    expect(bubble).not.toBeVisible();
    expect(within(risk).getAllByRole('button', { name: /^What is / })).toHaveLength(5);
  });

  it('sorts the holdings table by clicking a column', async () => {
    const user = userEvent.setup();
    setup();
    const table = screen.getByRole('table', { name: /Holdings with weight/ });
    const symbols = () =>
      within(table)
        .getAllByRole('row')
        .slice(1)
        .map((row) => within(row).getAllByRole('rowheader')[0]?.textContent);

    expect(symbols()).toEqual(['AAPL', 'TCS', 'ITC', 'LT']); // weight, descending by default
    expect(within(table).getByRole('columnheader', { name: /Weight/ })).toHaveAttribute(
      'aria-sort',
      'descending',
    );

    await user.click(within(table).getByRole('button', { name: /Symbol/ }));
    expect(symbols()).toEqual(['AAPL', 'ITC', 'LT', 'TCS']);
    expect(within(table).getByRole('columnheader', { name: /Symbol/ })).toHaveAttribute(
      'aria-sort',
      'ascending',
    );

    await user.click(within(table).getByRole('button', { name: /Symbol/ }));
    expect(symbols()).toEqual(['TCS', 'LT', 'ITC', 'AAPL']);

    await user.click(within(table).getByRole('button', { name: /Volatility/ }));
    expect(symbols()).toEqual(['AAPL', 'TCS', 'ITC', 'LT']); // LT has no volatility, so it is last
    expect(within(table).getByText('40.00%')).toBeInTheDocument();
    expect(within(table).getByText('n/a')).toBeInTheDocument();
  });

  it('draws the sector chart, drawdown chart and an accessible heatmap', () => {
    setup();
    const plots = screen.getAllByTestId('plot');
    expect(plots).toHaveLength(2);
    const [sector, drawdown] = plots.map(
      (p) => JSON.parse(p.dataset.traces ?? '[]') as Record<string, unknown>[],
    );
    expect(sector?.[0]?.type).toBe('bar');
    expect(sector?.[0]?.y).toEqual(['Industrials', 'Consumer Defensive', 'Technology']); // largest on top
    expect(drawdown?.[0]?.fill).toBe('tozeroy');
    expect(drawdown?.[0]?.y).toEqual([0, -5, -18.116, -10, 0]);

    expect(
      screen.getByRole('img', { name: /largest sector is Technology at 70\.0%/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('img', { name: /deepest fall was -18\.1% on 2024-01-03/ }),
    ).toBeInTheDocument();

    const heatmap = screen.getByRole('table', { name: /Correlation between holdings/ });
    expect(within(heatmap).getAllByRole('row')).toHaveLength(5);
    expect(within(heatmap).getAllByText('1.00')).toHaveLength(4);
    expect(within(heatmap).getByTitle('AAPL and TCS: 0.80')).toHaveTextContent('0.80');
    expect(within(heatmap).getByTitle('AAPL and ITC: -0.20')).toHaveTextContent('-0.20');
  });

  it('offers the sector data as a table', async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByText('View as table'));
    const table = screen.getByRole('table', { name: 'Sector exposure' });
    expect(within(table).getByRole('rowheader', { name: 'Technology' })).toBeInTheDocument();
    expect(within(table).getByText('70.00%')).toBeInTheDocument();
  });

  it('changes base currency and benchmark through the controls', async () => {
    const user = userEvent.setup();
    const props = setup();
    expect(screen.getByLabelText('INR')).toBeChecked();
    expect(screen.getByText('Using Nifty 50')).toBeInTheDocument();

    await user.click(screen.getByLabelText('USD'));
    expect(props.onChange).toHaveBeenLastCalledWith({ base_currency: 'USD' });

    await user.selectOptions(screen.getByLabelText('Benchmark'), '^GSPC');
    expect(props.onChange).toHaveBeenLastCalledWith({ benchmark: '^GSPC' });
    await user.selectOptions(screen.getByLabelText('Benchmark'), 'Automatic');
    expect(props.onChange).toHaveBeenLastCalledWith({ benchmark: null });
  });

  it('disables the controls and dims the page while re-analyzing', () => {
    setup({ reloading: true });
    expect(screen.getByLabelText('USD')).toBeDisabled();
    expect(screen.getByLabelText('Benchmark')).toBeDisabled();
    expect(screen.getByText('Updating…')).toBeInTheDocument();
  });

  it('lists the analysis warnings', async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByText(/1 note about this analysis/));
    expect(screen.getByText(/using the bundled price snapshot for: AAPL/)).toBeVisible();
  });

  it('shows AI insights with a verified badge and what each is based on', () => {
    setup();
    expect(screen.getByText(/AI-written · every number checked/)).toBeInTheDocument();
    expect(screen.getByText(/largest holding is AAPL at 40\.00%/)).toBeInTheDocument();
    expect(screen.getByText('Based on: AAPL weight, top 5')).toBeInTheDocument();
    expect(screen.getByText('Based on: volatility')).toBeInTheDocument();
  });

  it('shows template insights with their note, and a skeleton while loading', () => {
    setup({ insights: { status: 'ready', result: fx.insightsTemplate } });
    expect(screen.getByText('Generated from your numbers')).toBeInTheDocument();
    expect(screen.getByText(/AI unavailable; showing template insights/)).toBeInTheDocument();
  });

  it('shows a loading state for insights', () => {
    setup({ insights: { status: 'loading' } });
    expect(screen.getByText('Writing insights…')).toBeInTheDocument();
  });

  it('opens the chat from the dashboard', async () => {
    const user = userEvent.setup();
    const props = setup();
    await user.click(screen.getByRole('button', { name: 'Ask about this portfolio' }));
    expect(props.onOpenChat).toHaveBeenCalled();
  });
});
