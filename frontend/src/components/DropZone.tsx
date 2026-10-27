import { useId, useState, type ChangeEvent, type DragEvent } from 'react';
import { ACCEPT_ATTRIBUTE, MAX_ROWS, MAX_UPLOAD_BYTES } from '../lib/files';
import { formatBytes } from '../lib/format';

interface DropZoneProps {
  onFile: (file: File) => void;
  disabled?: boolean;
}

export function DropZone({ onFile, disabled = false }: DropZoneProps) {
  const [dragging, setDragging] = useState(false);
  const hintId = useId();

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    const file = event.dataTransfer.files[0];
    if (file) onFile(file);
  };

  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) onFile(file);
    event.target.value = ''; // allow choosing the same file again after fixing it
  };

  return (
    <label
      className={`dropzone${dragging ? ' dropzone-active' : ''}${disabled ? ' dropzone-disabled' : ''}`}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => {
        setDragging(false);
      }}
      onDrop={onDrop}
    >
      <input
        type="file"
        className="visually-hidden"
        accept={ACCEPT_ATTRIBUTE}
        onChange={onChange}
        disabled={disabled}
        aria-describedby={hintId}
        aria-label="Upload a holdings file"
      />
      <span className="dropzone-icon" aria-hidden="true">
        ⬆
      </span>
      <span className="dropzone-title">Drop your holdings file here, or click to browse</span>
      <span className="dropzone-hint" id={hintId}>
        CSV, Excel (.xlsx) or JSON · up to {formatBytes(MAX_UPLOAD_BYTES)} · up to {MAX_ROWS} rows
      </span>
    </label>
  );
}
