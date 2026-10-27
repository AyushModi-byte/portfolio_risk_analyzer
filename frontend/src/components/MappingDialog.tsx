import { useState } from 'react';
import type { ColumnField, ColumnMapping, MappingResult, ParseResponse } from '../api/types';
import { FIELD_LABELS } from '../lib/labels';
import { Modal } from './Modal';
import { SelectField } from './SelectField';

const FIELDS: { field: ColumnField; required: boolean }[] = [
  { field: 'symbol', required: true },
  { field: 'quantity', required: true },
  { field: 'avg_buy_price', required: false },
];

type Choices = Partial<Record<ColumnField, string>>;

interface MappingDialogProps {
  parse: ParseResponse;
  error: string | null;
  aiAvailable: boolean;
  onSuggest: (headers: string[], rows: Record<string, string>[]) => Promise<MappingResult>;
  onConfirm: (mapping: ColumnMapping) => void;
  onCancel: () => void;
}

function initialChoices(parse: ParseResponse): Choices {
  const choices: Choices = {};
  for (const { field } of FIELDS) {
    const detected = parse.detected[field];
    if (detected && parse.columns.includes(detected)) choices[field] = detected;
  }
  return choices;
}

export function MappingDialog(props: MappingDialogProps) {
  const { parse, error, aiAvailable, onSuggest, onConfirm, onCancel } = props;
  const [choices, setChoices] = useState<Choices>(() => initialChoices(parse));
  const [suggestion, setSuggestion] = useState<{ busy: boolean; message: string | null }>({
    busy: false,
    message: null,
  });

  const chosen = FIELDS.map(({ field }) => choices[field]).filter((c): c is string => !!c);
  const duplicate = new Set(chosen).size !== chosen.length;
  const complete = FIELDS.filter((f) => f.required).every((f) => !!choices[f.field]);
  const valid = complete && !duplicate;
  const missing = FIELDS.filter((f) => f.required && !parse.detected[f.field]).map((f) =>
    FIELD_LABELS[f.field].toLowerCase(),
  );

  const suggest = async () => {
    setSuggestion({ busy: true, message: null });
    try {
      const result = await onSuggest(parse.columns, parse.sample_rows);
      if (result.mapping) {
        const next: Choices = {};
        for (const { field } of FIELDS) {
          const column = result.mapping[field];
          if (column && parse.columns.includes(column)) next[field] = column;
        }
        setChoices(next);
        setSuggestion({
          busy: false,
          message: 'AI suggestion applied. Please check it before continuing.',
        });
      } else {
        setSuggestion({
          busy: false,
          message: 'The AI could not suggest columns. Please choose them yourself.',
        });
      }
    } catch {
      setSuggestion({
        busy: false,
        message: 'The AI suggestion is unavailable right now. Please choose the columns yourself.',
      });
    }
  };

  const submit = () => {
    const mapping: ColumnMapping = {};
    for (const { field } of FIELDS) {
      const column = choices[field];
      if (column) mapping[field] = column;
    }
    onConfirm(mapping);
  };

  return (
    <Modal title="Match your columns" onClose={onCancel}>
      <p>
        We couldn’t find the {missing.length > 0 ? missing.join(' or ') : 'required'} column
        automatically. Choose which column in your file holds each value.
      </p>

      <div className="field-grid">
        {FIELDS.map(({ field, required }) => (
          <SelectField
            key={field}
            label={`${FIELD_LABELS[field]} ${required ? '(required)' : '(optional)'}`}
            value={choices[field] ?? ''}
            options={[
              { value: '', label: required ? 'Choose a column' : 'None' },
              ...parse.columns.map((column) => ({ value: column, label: column })),
            ]}
            onChange={(value) => {
              setChoices((c) => ({ ...c, [field]: value || undefined }));
            }}
          />
        ))}
      </div>

      {parse.sample_rows.length > 0 && (
        <div
          className="table-scroll"
          tabIndex={0}
          role="region"
          aria-label="First rows of your file"
        >
          <table className="data-table preview">
            <caption>First rows of your file</caption>
            <thead>
              <tr>
                {parse.columns.map((c) => (
                  <th key={c} scope="col">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {parse.sample_rows.map((row, i) => (
                <tr key={i}>
                  {parse.columns.map((c) => (
                    <td key={c}>{row[c] ?? ''}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {aiAvailable && (
        <p>
          <button
            type="button"
            className="btn btn-small"
            onClick={() => void suggest()}
            disabled={suggestion.busy}
          >
            {suggestion.busy ? 'Asking the AI…' : 'Suggest columns with AI'}
          </button>
        </p>
      )}
      {suggestion.message && <p role="status">{suggestion.message}</p>}
      {duplicate && <p role="alert">Each column can be used for only one value.</p>}
      {error && <p role="alert">{error}</p>}

      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="btn btn-primary" onClick={submit} disabled={!valid}>
          Use these columns
        </button>
      </div>
    </Modal>
  );
}
