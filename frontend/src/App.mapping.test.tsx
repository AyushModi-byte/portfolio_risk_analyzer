import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { csvFile, renderApp } from './test/helpers';
import * as fx from './test/fixtures';

async function uploadUnreadable(user: ReturnType<typeof userEvent.setup>) {
  const file = csvFile('weird.csv');
  await user.upload(screen.getByLabelText('Upload a holdings file'), file);
  return file;
}

describe('column mapping dialog', () => {
  it('appears only when the parser needs a mapping', async () => {
    const user = userEvent.setup();
    renderApp();
    await user.upload(screen.getByLabelText('Upload a holdings file'), csvFile());
    await screen.findByRole('heading', { name: 'Risk' });
    expect(screen.queryByRole('dialog', { name: 'Match your columns' })).not.toBeInTheDocument();
  });

  it('shows detected columns and sample rows, then re-parses with the chosen mapping', async () => {
    const user = userEvent.setup();
    const parse = vi
      .fn()
      .mockResolvedValueOnce(fx.parseNeedsMapping)
      .mockResolvedValueOnce(fx.parseOk);
    const { api } = renderApp({ parse });
    const file = await uploadUnreadable(user);

    const dialog = await screen.findByRole('dialog', { name: 'Match your columns' });
    expect(dialog).toHaveTextContent(/couldn’t find the symbol or quantity column/);
    expect(
      within(dialog).getByRole('table', { name: 'First rows of your file' }),
    ).toBeInTheDocument();
    expect(within(dialog).getByText('Holding Qty', { selector: 'th' })).toBeInTheDocument();

    // The price column was detected and pre-selected; symbol and quantity are not chosen yet.
    expect(within(dialog).getByLabelText(/Average price/)).toHaveValue('Cost');
    const submit = within(dialog).getByRole('button', { name: 'Use these columns' });
    expect(submit).toBeDisabled();

    await user.selectOptions(within(dialog).getByLabelText(/Symbol/), 'Scrip Name');
    expect(submit).toBeDisabled();
    await user.selectOptions(within(dialog).getByLabelText(/Quantity/), 'Holding Qty');
    expect(submit).toBeEnabled();
    await user.click(submit);

    expect(await screen.findByRole('heading', { name: 'Risk' })).toBeInTheDocument();
    expect(parse).toHaveBeenLastCalledWith(file, {
      symbol: 'Scrip Name',
      quantity: 'Holding Qty',
      avg_buy_price: 'Cost',
    });
    expect(api.analyze).toHaveBeenCalledTimes(1);
  });

  it('refuses to use one column for two values', async () => {
    const user = userEvent.setup();
    renderApp({ parse: vi.fn().mockResolvedValue(fx.parseNeedsMapping) });
    await uploadUnreadable(user);
    const dialog = await screen.findByRole('dialog', { name: 'Match your columns' });

    await user.selectOptions(within(dialog).getByLabelText(/Symbol/), 'Scrip Name');
    await user.selectOptions(within(dialog).getByLabelText(/Quantity/), 'Scrip Name');

    expect(within(dialog).getByRole('alert')).toHaveTextContent(/only one value/);
    expect(within(dialog).getByRole('button', { name: 'Use these columns' })).toBeDisabled();
  });

  it('can be cancelled with the button or Escape', async () => {
    const user = userEvent.setup();
    renderApp({ parse: vi.fn().mockResolvedValue(fx.parseNeedsMapping) });
    await uploadUnreadable(user);
    await screen.findByRole('dialog', { name: 'Match your columns' });

    await user.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /See the risk in your portfolio/ }),
    ).toBeInTheDocument();
  });

  it('reports a mapping that still does not work', async () => {
    const user = userEvent.setup();
    renderApp({ parse: vi.fn().mockResolvedValue(fx.parseNeedsMapping) });
    await uploadUnreadable(user);
    const dialog = await screen.findByRole('dialog', { name: 'Match your columns' });
    await user.selectOptions(within(dialog).getByLabelText(/Symbol/), 'Scrip Name');
    await user.selectOptions(within(dialog).getByLabelText(/Quantity/), 'Notes');

    await user.click(within(dialog).getByRole('button', { name: 'Use these columns' }));

    expect(await screen.findByText(/still could not be read/)).toBeInTheDocument();
  });

  it('hides the AI suggestion button when AI is unavailable', async () => {
    const user = userEvent.setup();
    renderApp({
      health: vi.fn().mockResolvedValue({ ...fx.health, ai_available: false }),
      parse: vi.fn().mockResolvedValue(fx.parseNeedsMapping),
    });
    await uploadUnreadable(user);
    await screen.findByRole('dialog', { name: 'Match your columns' });
    expect(
      screen.queryByRole('button', { name: /Suggest columns with AI/ }),
    ).not.toBeInTheDocument();
  });

  it('applies an AI suggestion for the user to confirm', async () => {
    const user = userEvent.setup();
    const suggestMapping = vi.fn().mockResolvedValue({
      mapping: { symbol: 'Scrip Name', quantity: 'Holding Qty', avg_buy_price: 'Cost' },
      source: 'llm',
      error: null,
    });
    renderApp({ parse: vi.fn().mockResolvedValue(fx.parseNeedsMapping), suggestMapping });
    await uploadUnreadable(user);
    const dialog = await screen.findByRole('dialog', { name: 'Match your columns' });

    await user.click(
      await within(dialog).findByRole('button', { name: /Suggest columns with AI/ }),
    );

    expect(suggestMapping).toHaveBeenCalledWith(
      fx.parseNeedsMapping.columns,
      fx.parseNeedsMapping.sample_rows,
    );
    expect(await within(dialog).findByText(/check it before continuing/)).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/Symbol/)).toHaveValue('Scrip Name');
    expect(within(dialog).getByRole('button', { name: 'Use these columns' })).toBeEnabled();
  });
});

describe('unresolved symbols', () => {
  const unresolved = { ...fx.parseOk, unresolved_symbols: ['FOO', 'BAR'] };

  it('lists them and lets the user fix or ignore each one', async () => {
    const user = userEvent.setup();
    const parse = vi.fn().mockResolvedValue({
      ...unresolved,
      holdings: [
        { symbol: 'TCS', quantity: 1 },
        { symbol: 'FOO', quantity: 2 },
        { symbol: 'BAR', quantity: 3 },
      ],
    });
    const { api } = renderApp({ parse });
    await user.upload(screen.getByLabelText('Upload a holdings file'), csvFile());

    expect(
      await screen.findByRole('heading', { name: /2 symbols were not recognised/ }),
    ).toBeInTheDocument();
    await user.type(screen.getByLabelText('Replacement ticker for FOO'), 'FOO.NS');
    await user.click(screen.getByLabelText('Ignore BAR'));
    expect(screen.getByText(/1 to fix · 1 will be ignored/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Continue with analysis' }));

    expect(await screen.findByRole('heading', { name: 'Risk' })).toBeInTheDocument();
    expect(api.analyze).toHaveBeenCalledWith({
      holdings: [
        { symbol: 'TCS', quantity: 1 },
        { symbol: 'FOO.NS', quantity: 2 },
      ],
      base_currency: 'INR',
    });
    expect(screen.getByText('1 symbol ignored.')).toBeInTheDocument();
  });

  it('treats a symbol with no replacement as ignored', async () => {
    const user = userEvent.setup();
    const parse = vi.fn().mockResolvedValue({
      ...unresolved,
      unresolved_symbols: ['FOO'],
      holdings: [
        { symbol: 'TCS', quantity: 1 },
        { symbol: 'FOO', quantity: 2 },
      ],
    });
    const { api } = renderApp({ parse });
    await user.upload(screen.getByLabelText('Upload a holdings file'), csvFile());
    await screen.findByRole('heading', { name: /1 symbol was not recognised/ });

    await user.click(screen.getByRole('button', { name: 'Continue with analysis' }));

    await screen.findByRole('heading', { name: 'Risk' });
    expect(api.analyze).toHaveBeenCalledWith(
      expect.objectContaining({ holdings: [{ symbol: 'TCS', quantity: 1 }] }),
    );
  });

  it('will not continue when every symbol is ignored', async () => {
    const user = userEvent.setup();
    const parse = vi.fn().mockResolvedValue({
      ...unresolved,
      unresolved_symbols: ['FOO'],
      holdings: [{ symbol: 'FOO', quantity: 2 }],
    });
    const { api } = renderApp({ parse });
    await user.upload(screen.getByLabelText('Upload a holdings file'), csvFile());
    await screen.findByRole('heading', { name: /not recognised/ });

    await user.click(screen.getByRole('button', { name: 'Continue with analysis' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/Every symbol was ignored/);
    expect(api.analyze).not.toHaveBeenCalled();
  });
});
