import { useState } from 'react';

interface UnresolvedPanelProps {
  symbols: string[];
  onContinue: (fixes: Record<string, string | null>) => void;
  onCancel: () => void;
}

interface Row {
  replacement: string;
  ignore: boolean;
}

export function UnresolvedPanel({ symbols, onContinue, onCancel }: UnresolvedPanelProps) {
  const [rows, setRows] = useState<Record<string, Row>>(() =>
    Object.fromEntries(symbols.map((s) => [s, { replacement: '', ignore: false }])),
  );

  const update = (symbol: string, change: Partial<Row>) => {
    setRows((r) => ({
      ...r,
      [symbol]: { ...(r[symbol] ?? { replacement: '', ignore: false }), ...change },
    }));
  };

  const fixes = (): Record<string, string | null> =>
    Object.fromEntries(
      symbols.map((s) => {
        const row = rows[s];
        const replacement = row?.replacement.trim() ?? '';
        return [s, row?.ignore || !replacement ? null : replacement];
      }),
    );
  const ignoredCount = Object.values(fixes()).filter((v) => v === null).length;

  return (
    <section className="panel" aria-labelledby="unresolved-heading">
      <h2 id="unresolved-heading">
        {symbols.length === 1 ? '1 symbol was' : `${symbols.length} symbols were`} not recognised
      </h2>
      <p>
        We couldn’t match these to a stock on Yahoo Finance. For each one, type the correct ticker
        (for example <code>TCS.NS</code> for an NSE stock or <code>AAPL</code> for a US stock), or
        ignore it and analyze the rest.
      </p>
      <ul className="unresolved-list">
        {symbols.map((symbol) => (
          <li key={symbol} className="unresolved-row">
            <code className="unresolved-symbol">{symbol}</code>
            <label className="field">
              <span className="visually-hidden">Replacement ticker for {symbol}</span>
              <input
                type="text"
                placeholder="Replacement ticker"
                value={rows[symbol]?.replacement ?? ''}
                disabled={rows[symbol]?.ignore}
                maxLength={32}
                onChange={(event) => {
                  update(symbol, { replacement: event.target.value });
                }}
              />
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={rows[symbol]?.ignore ?? false}
                onChange={(event) => {
                  update(symbol, { ignore: event.target.checked });
                }}
              />
              <span>Ignore {symbol}</span>
            </label>
          </li>
        ))}
      </ul>
      <p className="muted">
        {symbols.length - ignoredCount} to fix · {ignoredCount} will be ignored
      </p>
      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Start over
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            onContinue(fixes());
          }}
        >
          Continue with analysis
        </button>
      </div>
    </section>
  );
}
