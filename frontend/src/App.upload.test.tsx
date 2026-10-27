import { fireEvent, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { csvFile, renderApp } from './test/helpers';
import * as fx from './test/fixtures';

describe('upload screen', () => {
  it('shows file type and size hints and three sample buttons', () => {
    renderApp();
    expect(
      screen.getByText(/CSV, Excel \(\.xlsx\) or JSON · up to 5\.0 MB · up to 500 rows/),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Try sample portfolio: India/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Try sample portfolio: US/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Try sample portfolio: Mixed/ })).toBeInTheDocument();
    expect(screen.getByText(/never stored or logged/)).toBeInTheDocument();
  });

  it('uploads a file, analyzes it and shows the dashboard', async () => {
    const user = userEvent.setup();
    const { api } = renderApp();
    const file = csvFile();

    await user.upload(screen.getByLabelText('Upload a holdings file'), file);

    expect(await screen.findByRole('heading', { name: 'Risk' })).toBeInTheDocument();
    expect(api.parse).toHaveBeenCalledWith(file, undefined);
    expect(api.analyze).toHaveBeenCalledWith({
      holdings: fx.parseOk.holdings,
      base_currency: 'INR',
    });
    expect(api.insights).toHaveBeenCalledWith(fx.analysis);
  });

  it('accepts a dropped file', async () => {
    const { api } = renderApp();
    const file = csvFile();
    const zone = screen.getByText(/Drop your holdings file here/).closest('label');
    expect(zone).not.toBeNull();

    fireEvent.drop(zone as HTMLElement, { dataTransfer: { files: [file] } });

    expect(await screen.findByRole('heading', { name: 'Risk' })).toBeInTheDocument();
    expect(api.parse).toHaveBeenCalledWith(file, undefined);
  });

  it.each([
    ['notes.txt', /not a supported file type/],
    ['macro.xlsm', /Macro-enabled workbooks \(\.xlsm\) are not accepted/],
    ['old.xls', /Old \.xls files are not supported/],
  ])('rejects %s before uploading anything', (name, message) => {
    const { api } = renderApp();
    fireEvent.change(screen.getByLabelText('Upload a holdings file'), {
      target: { files: [csvFile(name)] },
    });
    expect(screen.getByRole('alert')).toHaveTextContent(message);
    expect(api.parse).not.toHaveBeenCalled();
  });

  it('rejects a file over 5 MB and an empty file', () => {
    const { api } = renderApp();
    const big = csvFile('big.csv');
    Object.defineProperty(big, 'size', { value: 6 * 1024 * 1024 });
    fireEvent.change(screen.getByLabelText('Upload a holdings file'), { target: { files: [big] } });
    expect(screen.getByRole('alert')).toHaveTextContent(/6\.0 MB\. The limit is 5\.0 MB/);

    fireEvent.change(screen.getByLabelText('Upload a holdings file'), {
      target: { files: [csvFile('empty.csv', '')] },
    });
    expect(screen.getByRole('alert')).toHaveTextContent(/is empty/);
    expect(api.parse).not.toHaveBeenCalled();
  });

  it.each([
    ['India', 'INR', '^NSEI', 'india'],
    ['US', 'USD', '^GSPC', 'us'],
    ['Mixed', 'INR', '^NSEI', 'mixed'],
  ])('sample portfolio %s runs a full analysis', async (label, currency, benchmark) => {
    const user = userEvent.setup();
    const { api } = renderApp();

    await user.click(
      screen.getByRole('button', { name: new RegExp(`Try sample portfolio: ${label}`) }),
    );

    expect(await screen.findByRole('heading', { name: 'Risk' })).toBeInTheDocument();
    expect(api.analyze).toHaveBeenCalledWith(
      expect.objectContaining({ base_currency: currency, benchmark }),
    );
    expect(screen.getByRole('heading', { name: 'Sector exposure' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Drawdown' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Correlation' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Holdings' })).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Insights' })).toBeInTheDocument();
  });

  it('shows a loading skeleton while the analysis runs', async () => {
    const user = userEvent.setup();
    let release: (value: typeof fx.analysis) => void = () => undefined;
    const analyze = vi.fn(
      () =>
        new Promise<typeof fx.analysis>((resolve) => {
          release = resolve;
        }),
    );
    renderApp({ analyze });

    await user.click(screen.getByRole('button', { name: /Try sample portfolio: India/ }));
    expect(
      await screen.findByRole('status', { name: 'Loading your analysis' }),
    ).toBeInTheDocument();

    release(fx.analysis);
    expect(await screen.findByRole('heading', { name: 'Risk' })).toBeInTheDocument();
  });

  it('starts over from the dashboard', async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('button', { name: /Try sample portfolio: India/ }));
    await screen.findByRole('heading', { name: 'Risk' });

    await user.click(screen.getByRole('button', { name: 'New analysis' }));

    expect(
      screen.getByRole('heading', { name: /See the risk in your portfolio/ }),
    ).toBeInTheDocument();
  });

  it('always shows the disclaimer', () => {
    renderApp();
    expect(screen.getByText(/Analytics only, not financial advice\./)).toBeInTheDocument();
    const footer = screen.getByRole('contentinfo');
    expect(within(footer).getByText(/not financial advice/)).toBeVisible();
  });
});
