import { useMemo, useState } from 'react';
import type { Currency, WeightItem } from '../api/types';
import { formatMoney, formatPercent } from '../lib/format';

type SortKey = 'symbol' | 'weight' | 'market_value' | 'volatility';
type Direction = 'asc' | 'desc';

interface Column {
  key: SortKey;
  label: string;
  numeric: boolean;
}

const COLUMNS: Column[] = [
  { key: 'symbol', label: 'Symbol', numeric: false },
  { key: 'weight', label: 'Weight', numeric: true },
  { key: 'market_value', label: 'Market value', numeric: true },
  { key: 'volatility', label: 'Volatility', numeric: true },
];

function compare(a: WeightItem, b: WeightItem, key: SortKey): number {
  if (key === 'symbol') return a.symbol.localeCompare(b.symbol);
  // A missing volatility counts as the lowest value.
  return (a[key] ?? -Infinity) - (b[key] ?? -Infinity);
}

interface HoldingsTableProps {
  weights: WeightItem[];
  currency: Currency;
}

export function HoldingsTable({ weights, currency }: HoldingsTableProps) {
  const [sort, setSort] = useState<{ key: SortKey; dir: Direction }>({
    key: 'weight',
    dir: 'desc',
  });

  const rows = useMemo(() => {
    const sorted = [...weights].sort((a, b) => compare(a, b, sort.key));
    return sort.dir === 'desc' ? sorted.reverse() : sorted;
  }, [weights, sort]);
  const maxWeight = Math.max(...weights.map((w) => w.weight), 0.0001);

  const toggle = (key: SortKey) => {
    setSort((s) =>
      s.key === key
        ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: key === 'symbol' ? 'asc' : 'desc' },
    );
  };

  return (
    <section className="card" aria-labelledby="holdings-heading">
      <h2 id="holdings-heading">Holdings</h2>
      <div
        className="table-scroll table-tall"
        tabIndex={0}
        role="region"
        aria-label="Holdings table"
      >
        <table className="data-table holdings">
          <caption className="visually-hidden">
            Holdings with weight, market value and volatility. Use the column buttons to sort.
          </caption>
          <thead>
            <tr>
              {COLUMNS.map((col) => {
                const active = sort.key === col.key;
                return (
                  <th
                    key={col.key}
                    scope="col"
                    className={col.numeric ? 'num' : undefined}
                    aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    <button
                      type="button"
                      className="sort-button"
                      onClick={() => {
                        toggle(col.key);
                      }}
                    >
                      {col.label}
                      <span aria-hidden="true">
                        {active ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}
                      </span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((w) => (
              <tr key={w.symbol}>
                <th scope="row">{w.symbol}</th>
                <td className="num">
                  <span className="weight-cell">
                    <span className="weight-bar" aria-hidden="true">
                      <span style={{ width: `${(w.weight / maxWeight) * 100}%` }} />
                    </span>
                    {formatPercent(w.weight)}
                  </span>
                </td>
                <td className="num">{formatMoney(w.market_value, currency)}</td>
                <td className="num">{formatPercent(w.volatility)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
