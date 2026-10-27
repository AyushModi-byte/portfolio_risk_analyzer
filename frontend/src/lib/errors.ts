import { ApiError } from '../api/client';

export interface FriendlyError {
  title: string;
  message: string;
  /** True when trying the same thing again may work. */
  retryable: boolean;
}

const UNEXPECTED: FriendlyError = {
  title: 'Something went wrong',
  message: 'An unexpected error occurred. Please try again.',
  retryable: true,
};

function byCode(error: ApiError): FriendlyError | null {
  switch (error.code) {
    case 'network_error':
      return {
        title: "Can't reach the server",
        message:
          'Check your internet connection. If the server was asleep it may need a minute to wake up, so try again shortly.',
        retryable: true,
      };
    case 'unsupported_media_type':
      return { title: 'Unsupported file type', message: error.message, retryable: false };
    case 'payload_too_large':
      return { title: 'File too large', message: error.message, retryable: false };
    case 'rate_limited':
    case 'ai_rate_limited':
      return {
        title: 'Too many requests',
        message: error.retryAfter
          ? `Please wait about ${error.retryAfter} seconds and try again.`
          : 'Please wait a moment and try again.',
        retryable: true,
      };
    case 'ai_unavailable':
      return {
        title: 'AI is unavailable',
        message:
          'The AI features are switched off on this server. The rest of the dashboard still works.',
        retryable: false,
      };
    case 'ai_error':
      return {
        title: 'The AI assistant had a problem',
        message: 'Please try again in a moment.',
        retryable: true,
      };
    default:
      return null;
  }
}

/** Turns any thrown value into text a non-technical user can act on. */
export function friendlyError(error: unknown): FriendlyError {
  if (!(error instanceof ApiError)) return UNEXPECTED;
  const known = byCode(error);
  if (known) return known;
  if (error.status === 422 || error.status === 400 || error.status === 411) {
    return { title: "We couldn't use that", message: error.message, retryable: false };
  }
  if (error.status === 502 || error.status === 503 || error.status === 504) {
    return {
      title: 'Market data is unavailable',
      message: error.message || 'The data provider did not respond. Please try again shortly.',
      retryable: true,
    };
  }
  return {
    title: 'Something went wrong',
    message: error.message || 'The server returned an error. Please try again.',
    retryable: true,
  };
}
