import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiError } from './api/client';
import { csvFile, renderApp } from './test/helpers';
import * as fx from './test/fixtures';

describe('error states', () => {
  it('shows a friendly message for a market data failure and retries', async () => {
    const user = userEvent.setup();
    const analyze = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(502, 'bad_gateway', 'No price data for benchmark ^NSEI.'))
      .mockResolvedValueOnce(fx.analysis);
    renderApp({ analyze });

    await user.click(screen.getByRole('button', { name: /Try sample portfolio: India/ }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Market data is unavailable');
    expect(alert).toHaveTextContent('No price data for benchmark ^NSEI.');
    expect(alert).not.toHaveTextContent(/502|bad_gateway|Error:/);

    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('heading', { name: 'Risk' })).toBeInTheDocument();
    expect(analyze).toHaveBeenCalledTimes(2);
  });

  it('explains a network failure without technical detail', async () => {
    const user = userEvent.setup();
    renderApp({ parse: vi.fn().mockRejectedValue(new ApiError(0, 'network_error', 'x')) });

    await user.upload(screen.getByLabelText('Upload a holdings file'), csvFile());

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent("Can't reach the server");
    expect(alert).toHaveTextContent(/internet connection/);
    expect(
      screen.getByRole('heading', { name: /See the risk in your portfolio/ }),
    ).toBeInTheDocument();
  });

  it('shows the backend message for a file it rejects, with no retry button', async () => {
    const user = userEvent.setup();
    renderApp({
      parse: vi.fn().mockRejectedValue(new ApiError(400, 'bad_request', 'The file is empty.')),
    });

    await user.upload(screen.getByLabelText('Upload a holdings file'), csvFile());

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent("We couldn't use that");
    expect(alert).toHaveTextContent('The file is empty.');
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('keeps the dashboard when a currency change fails', async () => {
    const user = userEvent.setup();
    const analyze = vi
      .fn()
      .mockResolvedValueOnce(fx.analysis)
      .mockRejectedValueOnce(
        new ApiError(503, 'bad_gateway', 'USD/INR exchange rates are unavailable.'),
      );
    renderApp({ analyze });
    await user.click(screen.getByRole('button', { name: /Try sample portfolio: India/ }));
    await screen.findByRole('heading', { name: 'Risk' });

    await user.click(screen.getByLabelText('USD'));

    expect(await screen.findByRole('alert')).toHaveTextContent(/exchange rates are unavailable/);
    expect(screen.getByRole('heading', { name: 'Risk' })).toBeInTheDocument();
  });

  it('shows an insights error inside the panel and retries it', async () => {
    const user = userEvent.setup();
    const insights = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(502, 'ai_error', 'x'))
      .mockResolvedValueOnce(fx.insightsLlm);
    renderApp({ insights });
    await user.click(screen.getByRole('button', { name: /Try sample portfolio: India/ }));

    const panel = (await screen.findByRole('heading', { name: 'Insights' })).closest('section');
    expect(await screen.findByText(/Please try again in a moment/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Risk' })).toBeInTheDocument(); // the rest still works

    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText(/largest holding is AAPL/)).toBeInTheDocument();
    expect(panel).toHaveTextContent('AI-written');
  });

  it('explains a missing configuration instead of calling a made-up URL', async () => {
    const { ConfigError } = await import('./components/ConfigError');
    const { render } = await import('@testing-library/react');
    render(<ConfigError />);
    expect(screen.getByRole('alert')).toHaveTextContent('VITE_API_URL');
  });
});

describe('server wake-up banner', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('appears when /health takes longer than 3 seconds and goes away when it answers', async () => {
    let answer: (h: typeof fx.health) => void = () => undefined;
    const health = vi.fn(
      () =>
        new Promise<typeof fx.health>((resolve) => {
          answer = resolve;
        }),
    );
    renderApp({ health });

    expect(screen.queryByText(/Waking up the server/)).not.toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2900);
    });
    expect(screen.queryByText(/Waking up the server/)).not.toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    expect(screen.getByText(/Waking up the server/)).toBeInTheDocument();

    await act(async () => {
      answer(fx.health);
      await vi.advanceTimersByTimeAsync(10);
    });
    await waitFor(() => {
      expect(screen.queryByText(/Waking up the server/)).not.toBeInTheDocument();
    });
  });

  it('keeps retrying while the server is asleep and then clears', async () => {
    const health = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(0, 'network_error', 'x'))
      .mockRejectedValueOnce(new ApiError(0, 'network_error', 'x'))
      .mockResolvedValue(fx.health);
    renderApp({ health });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(screen.getByText(/Waking up the server/)).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(7000);
    });
    await waitFor(() => {
      expect(screen.queryByText(/Waking up the server/)).not.toBeInTheDocument();
    });
    expect(health).toHaveBeenCalledTimes(3);
  });

  it('does not show the banner when the server answers quickly', async () => {
    renderApp();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(screen.queryByText(/Waking up the server/)).not.toBeInTheDocument();
  });
});

describe('AI unavailable', () => {
  it('disables chat but keeps the dashboard and template insights', async () => {
    const user = userEvent.setup();
    renderApp({
      health: vi.fn().mockResolvedValue({ ...fx.health, ai_available: false }),
      insights: vi.fn().mockResolvedValue(fx.insightsTemplate),
    });
    await user.click(screen.getByRole('button', { name: /Try sample portfolio: India/ }));

    const chat = await screen.findByRole('button', { name: 'AI chat unavailable' });
    expect(chat).toBeDisabled();
    expect(await screen.findByText('Generated from your numbers')).toBeInTheDocument();
    expect(screen.getByText(/AI unavailable; showing template insights/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Risk' })).toBeInTheDocument();
  });
});
