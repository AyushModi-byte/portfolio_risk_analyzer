import type { AnalyzeRequest, Currency } from '../api/types';
import { benchmarkName, BENCHMARKS } from '../lib/labels';
import { SelectField } from './SelectField';

const CURRENCIES: Currency[] = ['INR', 'USD'];

interface ControlsProps {
  request: AnalyzeRequest;
  /** The benchmark the backend actually used, shown when the choice is "Automatic". */
  usedBenchmark: string;
  disabled: boolean;
  onChange: (change: { base_currency?: Currency; benchmark?: string | null }) => void;
}

export function Controls({ request, usedBenchmark, disabled, onChange }: ControlsProps) {
  const selected = request.benchmark ?? '';
  return (
    <div className="controls">
      <fieldset className="segmented" disabled={disabled}>
        <legend>Base currency</legend>
        <div className="segmented-options">
          {CURRENCIES.map((currency) => (
            <label
              key={currency}
              className={request.base_currency === currency ? 'is-selected' : ''}
            >
              <input
                type="radio"
                name="base-currency"
                value={currency}
                checked={request.base_currency === currency}
                onChange={() => {
                  onChange({ base_currency: currency });
                }}
              />
              <span>{currency}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <SelectField
        className="control-select"
        label="Benchmark"
        value={BENCHMARKS.some((b) => b.value === selected) ? selected : ''}
        options={BENCHMARKS.map((b) => ({ value: b.value, label: b.label }))}
        disabled={disabled}
        hint={selected === '' ? `Using ${benchmarkName(usedBenchmark)}` : undefined}
        onChange={(value) => {
          onChange({ benchmark: value || null });
        }}
      />
    </div>
  );
}
