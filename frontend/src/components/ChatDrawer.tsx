import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { useApi } from '../api/context';
import type { AnalysisResult, AnalyzeRequest, ChatMessage, ToolRecord } from '../api/types';
import { ApiError } from '../api/client';
import { friendlyError } from '../lib/errors';
import { plainText } from '../lib/text';
import { Spinner } from './Feedback';
import { ToolsUsed } from './ToolsUsed';

const MAX_HISTORY = 20;
const MAX_CHARS = 2000;
const SUGGESTIONS = [
  'What is my biggest holding?',
  'Which sector am I most exposed to?',
  'Which holding contributes the most risk?',
];

interface Entry extends ChatMessage {
  tools?: ToolRecord[];
  unverified?: boolean;
  isError?: boolean;
}

interface ChatDrawerProps {
  analysis: AnalysisResult;
  request: AnalyzeRequest | null;
  aiAvailable: boolean;
  onClose: () => void;
  onAiUnavailable: () => void;
}

export function ChatDrawer({
  analysis,
  request,
  aiAvailable,
  onClose,
  onAiUnavailable,
}: ChatDrawerProps) {
  const api = useApi();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);
  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [entries, busy]);

  const send = async (text: string) => {
    const question = text.trim().slice(0, MAX_CHARS);
    if (!question || busy) return;
    const prior: ChatMessage[] = entries
      .filter((e) => !e.isError)
      .map(({ role, content }) => ({ role, content }));
    const history = [...prior, { role: 'user' as const, content: question }]
      .slice(-MAX_HISTORY)
      .map((m): ChatMessage => ({ role: m.role, content: m.content.slice(0, MAX_CHARS) }));
    setEntries((e) => [...e, { role: 'user', content: question }]);
    setDraft('');
    setBusy(true);
    try {
      const result = await api.chat({ analysis, messages: history, request });
      setEntries((e) => [
        ...e,
        {
          role: 'assistant',
          content: result.answer,
          tools: result.tool_calls,
          unverified: !result.verified,
        },
      ]);
    } catch (error) {
      if (error instanceof ApiError && error.code === 'ai_unavailable') onAiUnavailable();
      setEntries((e) => [
        ...e,
        { role: 'assistant', content: friendlyError(error).message, isError: true },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void send(draft);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void send(draft);
    }
  };

  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <aside
      className="drawer"
      role="dialog"
      aria-label="Ask about this portfolio"
      onKeyDown={(event) => {
        if (event.key === 'Escape') onClose();
      }}
    >
      <header className="drawer-header">
        <h2>Ask about this portfolio</h2>
        <button type="button" className="btn btn-small btn-ghost" onClick={onClose}>
          Close
        </button>
      </header>

      <div className="drawer-body" ref={listRef} aria-live="polite">
        {!aiAvailable && (
          <p className="muted">
            AI is unavailable on this server, so chat is switched off. Everything else on the
            dashboard still works.
          </p>
        )}
        {aiAvailable && entries.length === 0 && (
          <div>
            <p className="muted">
              Answers use only numbers computed by the analytics engine, and the tools used are
              shown under each answer. I can’t give buy or sell advice.
            </p>
            <ul className="suggestions">
              {SUGGESTIONS.map((s) => (
                <li key={s}>
                  <button type="button" className="chip" onClick={() => void send(s)}>
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {entries.map((entry, i) => (
          <div
            key={i}
            className={`bubble bubble-${entry.role}${entry.isError ? ' bubble-error' : ''}`}
          >
            <p>{entry.role === 'assistant' ? plainText(entry.content) : entry.content}</p>
            {entry.unverified && (
              <p className="muted">I couldn’t verify the numbers for this question.</p>
            )}
            {entry.tools && <ToolsUsed tools={entry.tools} />}
          </div>
        ))}
        {busy && <Spinner label="Thinking…" />}
      </div>

      <form className="drawer-form" onSubmit={onSubmit}>
        <label className="visually-hidden" htmlFor="chat-input">
          Your question
        </label>
        <textarea
          id="chat-input"
          ref={inputRef}
          rows={2}
          maxLength={MAX_CHARS}
          value={draft}
          placeholder={aiAvailable ? 'Ask a question…' : 'AI is unavailable'}
          disabled={!aiAvailable || busy}
          onChange={(event) => {
            setDraft(event.target.value);
          }}
          onKeyDown={onKeyDown}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!aiAvailable || busy || !draft.trim()}
        >
          Send
        </button>
      </form>
    </aside>
  );
}
