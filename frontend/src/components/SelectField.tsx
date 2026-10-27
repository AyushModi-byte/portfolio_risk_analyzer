import { useId } from 'react';

interface SelectFieldProps {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
  /** Extra text that describes the field; announced after the label, not part of it. */
  hint?: string;
  className?: string;
}

/** A labelled select. The label is tied by id so its accessible name is just the label text. */
export function SelectField({
  label,
  value,
  options,
  onChange,
  disabled = false,
  hint,
  className = '',
}: SelectFieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  return (
    <div className={`field ${className}`}>
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        value={value}
        disabled={disabled}
        aria-describedby={hint ? hintId : undefined}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint && (
        <small id={hintId} className="muted">
          {hint}
        </small>
      )}
    </div>
  );
}
