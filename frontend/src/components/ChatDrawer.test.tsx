import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiError } from '../api/client';
import type { Api } from '../api/client';
import type { AnalyzeRequest } from '../api/types';
import { makeApi, renderWithApi } from '../test/helpers';
import * as fx from '../test/fixtures';
import { ChatDrawer } from './ChatDrawer';

const request: AnalyzeRequest = { holdings: fx.parseOk.holdings, base_currency: 'INR' };

function setup(api: Api, aiAvailable = true) {
  const onClose = vi.fn();
  const onAiUnavailable = vi.fn();
  renderWithApi(
    <ChatDrawer
      analysis={fx.analysis}
      request={request}
      aiAvailable={aiAvailable}
      onClose={onClose}
      onAiUnavailable={onAiUnavailable}
    />,
    api,
  );
  return { onClose, onAiUnavailable };
}

describe('chat drawer', () => {
  it('sends the analysis, history and original request, and shows the tools used', async () => {
    const user = userEvent.setup();
    const api = makeApi();
    setup(api);

    await user.type(screen.getByLabelText('Your question'), 'What is my biggest holding?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText(/biggest holding is AAPL/)).toBeInTheDocument();
    expect(api.chat).toHaveBeenCalledWith({
      analysis: fx.analysis,
      messages: [{ role: 'user', content: 'What is my biggest holding?' }],
      request,
    });
    const summary = screen.getByText(/Tools used \(1\): get_top_holdings/);
    await user.click(summary);
    expect(screen.getByText('get_top_holdings(n: 1)')).toBeVisible();
    await user.click(screen.getByText('Result'));
    expect(screen.getByText(/"weight_percent": 40/)).toBeVisible();
    expect(screen.getByLabelText('Your question')).toHaveValue('');
  });

  it('keeps the conversation as history for the next question', async () => {
    const user = userEvent.setup();
    const api = makeApi();
    setup(api);
    await user.click(screen.getByRole('button', { name: 'What is my biggest holding?' }));
    await screen.findByText(/biggest holding is AAPL/);

    await user.type(screen.getByLabelText('Your question'), 'And the next?{Enter}');

    await screen.findAllByText(/biggest holding is AAPL/);
    expect(api.chat).toHaveBeenLastCalledWith(
      expect.objectContaining({
        messages: [
          { role: 'user', content: 'What is my biggest holding?' },
          { role: 'assistant', content: fx.chatResult.answer },
          { role: 'user', content: 'And the next?' },
        ],
      }),
    );
  });

  it('notes when an answer could not be verified', async () => {
    const user = userEvent.setup();
    const chat = vi.fn().mockResolvedValue({ ...fx.chatResult, tool_calls: [], verified: false });
    setup(makeApi({ chat }));
    await user.type(screen.getByLabelText('Your question'), 'hello{Enter}');
    expect(await screen.findByText(/couldn’t verify the numbers/)).toBeInTheDocument();
    expect(screen.queryByText(/Tools used/)).not.toBeInTheDocument();
  });

  it('shows a friendly message when the rate limit is hit', async () => {
    const user = userEvent.setup();
    const chat = vi.fn().mockRejectedValue(new ApiError(429, 'rate_limited', 'x', 42));
    setup(makeApi({ chat }));
    await user.type(screen.getByLabelText('Your question'), 'hello{Enter}');
    expect(await screen.findByText(/wait about 42 seconds/)).toBeInTheDocument();
  });

  it('switches itself off when the server reports AI unavailable', async () => {
    const user = userEvent.setup();
    const chat = vi.fn().mockRejectedValue(new ApiError(503, 'ai_unavailable', 'x'));
    const { onAiUnavailable } = setup(makeApi({ chat }));
    await user.type(screen.getByLabelText('Your question'), 'hello{Enter}');
    await screen.findByText(/switched off on this server/);
    expect(onAiUnavailable).toHaveBeenCalled();
  });

  it('is disabled with an explanation when AI is unavailable', () => {
    const api = makeApi();
    setup(api, false);
    expect(screen.getByLabelText('Your question')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
    expect(screen.getByText(/AI is unavailable on this server/)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'What is my biggest holding?' }),
    ).not.toBeInTheDocument();
  });

  it('closes with the button and with Escape', async () => {
    const user = userEvent.setup();
    const { onClose } = setup(makeApi());
    await user.click(screen.getByRole('button', { name: 'Close' }));
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('is a labelled dialog with focus in the question box', () => {
    setup(makeApi());
    const drawer = screen.getByRole('dialog', { name: 'Ask about this portfolio' });
    expect(within(drawer).getByLabelText('Your question')).toHaveFocus();
  });
});
