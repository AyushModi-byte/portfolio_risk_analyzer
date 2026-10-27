import { formatBytes } from './format';

export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
export const MAX_ROWS = 500;
export const ACCEPTED_EXTENSIONS = ['.csv', '.xlsx', '.json'] as const;
export const ACCEPT_ATTRIBUTE = ACCEPTED_EXTENSIONS.join(',');

const EXTENSION_HINTS: Record<string, string> = {
  '.xlsm':
    'Macro-enabled workbooks (.xlsm) are not accepted. Save the file as .xlsx and try again.',
  '.xls': 'Old .xls files are not supported. Save the file as .xlsx or .csv and try again.',
};

/** Client-side check so obvious problems are reported before anything is uploaded. */
export function validateFile(file: File): string | null {
  const dot = file.name.lastIndexOf('.');
  const extension = dot >= 0 ? file.name.slice(dot).toLowerCase() : '';
  if (!(ACCEPTED_EXTENSIONS as readonly string[]).includes(extension)) {
    return (
      EXTENSION_HINTS[extension] ??
      `“${file.name}” is not a supported file type. Upload a .csv, .xlsx or .json file.`
    );
  }
  if (file.size === 0) return `“${file.name}” is empty.`;
  if (file.size > MAX_UPLOAD_BYTES) {
    return `“${file.name}” is ${formatBytes(file.size)}. The limit is ${formatBytes(MAX_UPLOAD_BYTES)}.`;
  }
  return null;
}
