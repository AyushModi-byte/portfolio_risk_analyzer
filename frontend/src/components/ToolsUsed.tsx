import type { ToolRecord } from '../api/types';

const MAX_OUTPUT_CHARS = 1500;

function formatArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args);
  if (entries.length === 0) return '()';
  return `(${entries.map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(', ')})`;
}

function formatOutput(output: Record<string, unknown>): string {
  const text = JSON.stringify(output, null, 2);
  return text.length > MAX_OUTPUT_CHARS ? `${text.slice(0, MAX_OUTPUT_CHARS)}\n…` : text;
}

/** Shows which analytics tools the assistant called, so every answer can be traced. */
export function ToolsUsed({ tools }: { tools: ToolRecord[] }) {
  if (tools.length === 0) return null;
  return (
    <details className="tools-used">
      <summary>
        Tools used ({tools.length}): {tools.map((t) => t.name).join(', ')}
      </summary>
      <ol>
        {tools.map((tool, index) => (
          <li key={index}>
            <code>
              {tool.name}
              {formatArgs(tool.args)}
            </code>
            <details>
              <summary>Result</summary>
              <pre>{formatOutput(tool.output)}</pre>
            </details>
          </li>
        ))}
      </ol>
    </details>
  );
}
