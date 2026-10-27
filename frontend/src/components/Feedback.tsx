import type { ReactNode } from 'react';
import type { FriendlyError } from '../lib/errors';

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

export function Spinner({ label }: { label: string }) {
  return (
    <span className="spinner-wrap" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

interface ErrorMessageProps {
  error: FriendlyError;
  onRetry?: () => void;
  onDismiss?: () => void;
}

export function ErrorMessage({ error, onRetry, onDismiss }: ErrorMessageProps) {
  return (
    <div className="banner banner-error" role="alert">
      <div className="banner-body">
        <strong>{error.title}</strong>
        <span>{error.message}</span>
      </div>
      <div className="banner-actions">
        {error.retryable && onRetry && (
          <button type="button" className="btn btn-small" onClick={onRetry}>
            Try again
          </button>
        )}
        {onDismiss && (
          <button type="button" className="btn btn-small btn-ghost" onClick={onDismiss}>
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
}

export function WakeBanner({ down }: { down: boolean }) {
  if (down) {
    return (
      <div className="banner banner-error" role="alert">
        <div className="banner-body">
          <strong>The server isn’t responding</strong>
          <span>It may be down or starting slowly. Reload the page in a minute and try again.</span>
        </div>
      </div>
    );
  }
  return (
    <div className="banner banner-info" role="status">
      <span className="spinner" aria-hidden="true" />
      <div className="banner-body">
        <strong>Waking up the server…</strong>
        <span>
          The free host puts the app to sleep when it’s idle. This can take up to a minute; you can
          start anyway.
        </span>
      </div>
    </div>
  );
}

export function Notice({ children }: { children: ReactNode }) {
  return (
    <div className="banner banner-info" role="status">
      <div className="banner-body">{children}</div>
    </div>
  );
}

export function Footer() {
  return (
    <footer className="footer">
      <p>
        <strong>Analytics only, not financial advice.</strong> Figures describe how today’s holdings
        would have behaved over the past window, using daily prices from Yahoo Finance. They are not
        a forecast and not a record of what you earned.
      </p>
    </footer>
  );
}
